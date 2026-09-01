#!/usr/bin/env python3
"""Deterministic, owner-only invoice renderer for Hermes.

The private profile supplies issuer, bank, known-client, and bootstrap history
data. The public engine never logs those values. All durable writes live on the
Hermes owner PVC and use an advisory lock plus atomic replacement.
"""

from __future__ import annotations

import argparse
import calendar
import fcntl
import hashlib
import html
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MONEY = Decimal("0.01")
INVOICE_NUMBER = re.compile(r"^INV-(\d{4})-(\d{3})$")
PERIOD = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SAFE_ITEM_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_ITEMS = 12
PRIVATE_DIRECTORY_MODE = 0o2770
PRIVATE_FILE_MODE = 0o660


class InvoiceError(RuntimeError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _ensure_mode(path: Path, mode: int) -> None:
    if stat.S_IMODE(path.stat().st_mode) == mode:
        return
    try:
        os.chmod(path, mode)
    except PermissionError as error:
        raise InvoiceError(
            "state_permissions",
            f"invoice state permissions could not be normalized: {path}",
        ) from error


def _prepare_private_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
        _ensure_mode(path, PRIVATE_DIRECTORY_MODE)
    except PermissionError as error:
        raise InvoiceError(
            "state_permissions",
            f"invoice state directory is not accessible: {path}",
        ) from error


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InvoiceError("missing_file", f"required file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise InvoiceError("invalid_json", f"invalid JSON in {path}: {error}") from error
    if not isinstance(raw, dict):
        raise InvoiceError("invalid_json", f"JSON root must be an object: {path}")
    return raw


def _required(mapping: dict[str, Any], key: str, *, where: str) -> Any:
    value = mapping.get(key)
    if value in (None, "", [], {}):
        raise InvoiceError("missing_field", f"{where}.{key} is required")
    return value


def _bounded_text(value: Any, *, field: str, maximum: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise InvoiceError("missing_field", f"{field} is required")
    if len(text) > maximum:
        raise InvoiceError("invalid_field", f"{field} exceeds {maximum} characters")
    return text


def _decimal(value: Any, *, field: str, positive: bool = False) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise InvoiceError("invalid_money", f"{field} must be a decimal string") from error
    if not number.is_finite() or (positive and number <= 0) or number < 0:
        raise InvoiceError("invalid_money", f"{field} is outside the accepted range")
    return number


def _money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _quantity(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _currency(value: Decimal, code: str) -> str:
    symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
    amount = f"{value.quantize(MONEY, rounding=ROUND_HALF_UP):,.2f}"
    symbol = symbols.get(code)
    return f"{symbol}{amount}" if symbol else f"{code} {amount}"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _prepare_private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, PRIVATE_FILE_MODE)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise InvoiceError("profile_version", "unsupported private profile version")
    issuer = _required(profile, "issuer", where="profile")
    bank = _required(profile, "bank", where="profile")
    clients = _required(profile, "clients", where="profile")
    if not isinstance(issuer, dict) or not isinstance(bank, dict) or not isinstance(clients, dict):
        raise InvoiceError("invalid_profile", "profile issuer, bank, and clients must be objects")
    for key in ("legal_name", "legal_status", "email", "website", "address_lines"):
        _required(issuer, key, where="profile.issuer")
    for key in ("beneficiary", "name", "country", "currency", "iban", "swift"):
        _required(bank, key, where="profile.bank")
    for key, client in clients.items():
        if not SAFE_KEY.fullmatch(key) or not isinstance(client, dict):
            raise InvoiceError("invalid_profile", f"invalid client profile key: {key}")
        _required(client, "legal_name", where=f"profile.clients.{key}")


def _bootstrap_ledger(profile: dict[str, Any]) -> dict[str, Any]:
    history = deepcopy(profile.get("history", []))
    if not isinstance(history, list):
        raise InvoiceError("invalid_profile", "profile history must be a list")
    seen: set[str] = set()
    for record in history:
        if not isinstance(record, dict):
            raise InvoiceError("invalid_profile", "profile history entries must be objects")
        number = _required(record, "invoice_number", where="profile.history")
        if not INVOICE_NUMBER.fullmatch(str(number)) or number in seen:
            raise InvoiceError("invalid_profile", f"invalid or duplicate history number: {number}")
        seen.add(str(number))
        record.setdefault("revision", 1)
        record.setdefault("source", "bootstrap")
    return {"schema_version": SCHEMA_VERSION, "invoices": history}


def _load_ledger(path: Path, profile: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return _bootstrap_ledger(profile)
    ledger = _load_json(path)
    if ledger.get("schema_version") != SCHEMA_VERSION or not isinstance(ledger.get("invoices"), list):
        raise InvoiceError("ledger_version", "unsupported or invalid invoice ledger")
    return ledger


def _parse_period(value: Any) -> tuple[str | None, str | None]:
    if value in (None, ""):
        return None, None
    raw = _bounded_text(value, field="billing_period", maximum=7)
    match = PERIOD.fullmatch(raw)
    if not match:
        raise InvoiceError("invalid_period", "billing_period must use YYYY-MM")
    year, month = int(match.group(1)), int(match.group(2))
    return raw, f"{calendar.month_name[month]} {year}"


def _parse_date(value: Any, *, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise InvoiceError("invalid_date", f"{field} must use YYYY-MM-DD") from error


def _display_date(value: date) -> str:
    return f"{value.day} {calendar.month_name[value.month]} {value.year}"


def _inferred_invoice_date(period: str, client: dict[str, Any]) -> date:
    rule = client.get("billing_rule")
    if rule != "arrears_first_day":
        raise InvoiceError("missing_field", "invoice_date is required for this client")
    year, month = (int(part) for part in period.split("-"))
    return date(year + (month == 12), 1 if month == 12 else month + 1, 1)


def _client_from_request(request: dict[str, Any], profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    key = _bounded_text(request.get("client_key"), field="client_key", maximum=64)
    if not SAFE_KEY.fullmatch(key):
        raise InvoiceError("invalid_client", "client_key must be lowercase letters, numbers, or hyphens")
    known = profile["clients"].get(key)
    inline = request.get("client")
    if known is not None:
        if inline not in (None, {}):
            raise InvoiceError("invalid_client", "known client details cannot be overridden inline")
        return key, deepcopy(known)
    if not isinstance(inline, dict):
        raise InvoiceError("unknown_client", f"client_key '{key}' needs an inline client object")
    client = {
        "legal_name": _bounded_text(inline.get("legal_name"), field="client.legal_name", maximum=160),
        "email": _bounded_text(inline.get("email"), field="client.email", maximum=254, required=False),
        "country": _bounded_text(inline.get("country"), field="client.country", maximum=120),
        "address_lines": inline.get("address_lines", []),
        "file_stem": _bounded_text(inline.get("file_stem", key.title()), field="client.file_stem", maximum=80),
        "default_due_date": _bounded_text(inline.get("default_due_date", "Upon Receipt"), field="client.default_due_date", maximum=80),
    }
    if not isinstance(client["address_lines"], list) or len(client["address_lines"]) > 4:
        raise InvoiceError("invalid_client", "client.address_lines must be a list of at most four lines")
    client["address_lines"] = [
        _bounded_text(line, field="client.address_lines", maximum=160) for line in client["address_lines"]
    ]
    return key, client


def _line_items(
    request: dict[str, Any], client: dict[str, Any], billing_period_display: str | None
) -> tuple[list[dict[str, str]], list[str]]:
    requested = request.get("items")
    if not isinstance(requested, list) or not requested:
        raise InvoiceError("missing_field", "items must be a non-empty list")
    if len(requested) > MAX_ITEMS:
        raise InvoiceError("too_many_items", f"at most {MAX_ITEMS} line items are supported")
    defaults = client.get("line_item_defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise InvoiceError("invalid_profile", "client line_item_defaults must be an object")
    result: list[dict[str, str]] = []
    warnings: list[str] = []
    for index, supplied in enumerate(requested):
        if not isinstance(supplied, dict):
            raise InvoiceError("invalid_item", f"items[{index}] must be an object")
        key = str(supplied.get("key", "")).strip()
        base: dict[str, Any] = {}
        if key:
            if not SAFE_ITEM_KEY.fullmatch(key) or key not in defaults:
                raise InvoiceError("unknown_item", f"unknown line-item key: {key}")
            base = deepcopy(defaults[key])
        item = {**base, **supplied}
        title = _bounded_text(item.get("title"), field=f"items[{index}].title", maximum=120)
        description = _bounded_text(
            item.get("description", ""), field=f"items[{index}].description", maximum=320, required=False
        )
        if "{billing_period}" in title or "{billing_period}" in description:
            if billing_period_display is None:
                raise InvoiceError(
                    "missing_field",
                    f"items[{index}] requires billing_period for its description",
                )
            title = title.replace("{billing_period}", billing_period_display)
            description = description.replace("{billing_period}", billing_period_display)
        quantity = _decimal(item.get("quantity", "1"), field=f"items[{index}].quantity", positive=True)
        if quantity > Decimal("100000"):
            raise InvoiceError("invalid_item", f"items[{index}].quantity is too large")
        if "amount" in item:
            if "quantity" in supplied and quantity != Decimal("1"):
                raise InvoiceError("invalid_item", f"items[{index}].amount requires quantity 1")
            quantity = Decimal("1")
            unit_price = _decimal(item["amount"], field=f"items[{index}].amount")
        else:
            unit_price = _decimal(item.get("unit_price"), field=f"items[{index}].unit_price")
        amount = (quantity * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        contract_price = item.get("contract_unit_price")
        if contract_price not in (None, ""):
            contract = _decimal(contract_price, field=f"items[{index}].contract_unit_price")
            if unit_price.quantize(MONEY) != contract.quantize(MONEY):
                warnings.append(
                    f"{title}: invoiced {_money(unit_price)}; contract reference {_money(contract)}"
                )
        result.append(
            {
                "key": key,
                "title": title,
                "description": description,
                "quantity": _quantity(quantity),
                "unit_price": _money(unit_price),
                "amount": _money(amount),
            }
        )
    return result, warnings


def _find_invoice(ledger: dict[str, Any], number: str) -> tuple[int, dict[str, Any]]:
    for index, record in enumerate(ledger["invoices"]):
        if record.get("invoice_number") == number:
            return index, record
    raise InvoiceError("unknown_invoice", f"invoice does not exist: {number}")


def _next_number(ledger: dict[str, Any], year: int) -> str:
    sequence = 0
    for record in ledger["invoices"]:
        match = INVOICE_NUMBER.fullmatch(str(record.get("invoice_number", "")))
        if match and int(match.group(1)) == year:
            sequence = max(sequence, int(match.group(2)))
    if sequence >= 999:
        raise InvoiceError("number_exhausted", f"invoice sequence is exhausted for {year}")
    return f"INV-{year}-{sequence + 1:03d}"


def _resolve(request: dict[str, Any], profile: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    replace_number = str(request.get("replace_invoice_number", "")).strip()
    replacement_index: int | None = None
    previous: dict[str, Any] | None = None
    if replace_number:
        if not INVOICE_NUMBER.fullmatch(replace_number):
            raise InvoiceError("invalid_invoice", "replace_invoice_number is invalid")
        reason = _bounded_text(
            request.get("replacement_reason"), field="replacement_reason", maximum=300
        )
        replacement_index, previous = _find_invoice(ledger, replace_number)
        merged = deepcopy(previous.get("request", {}))
        merged.update(request)
        request = merged
        request["replace_invoice_number"] = replace_number
        request["replacement_reason"] = reason

    client_key, client = _client_from_request(request, profile)
    period, period_display = _parse_period(request.get("billing_period"))
    raw_date = request.get("invoice_date")
    if raw_date in (None, ""):
        if period is None:
            raise InvoiceError("missing_field", "invoice_date is required without a billing period")
        invoice_date = _inferred_invoice_date(period, client)
    else:
        invoice_date = _parse_date(raw_date, field="invoice_date")
    invoice_number = replace_number or _next_number(ledger, invoice_date.year)

    if replace_number and previous is not None:
        match = INVOICE_NUMBER.fullmatch(replace_number)
        assert match is not None
        if int(match.group(1)) != invoice_date.year:
            raise InvoiceError("invalid_date", "a revision cannot move an invoice into another year")

    overlapping = [
        record["invoice_number"]
        for record in ledger["invoices"]
        if period
        and record.get("client_key") == client_key
        and record.get("billing_period") == period
        and record.get("invoice_number") != replace_number
    ]
    overlap_reason = str(request.get("overlap_reason", "")).strip()
    if overlapping and not overlap_reason:
        raise InvoiceError(
            "duplicate_billing_period",
            f"{client['legal_name']} already has invoice(s) for {period_display}",
            conflicting_invoices=overlapping,
            client_key=client_key,
            billing_period=period,
        )
    if overlap_reason:
        overlap_reason = _bounded_text(overlap_reason, field="overlap_reason", maximum=300)

    currency = _bounded_text(
        request.get("currency", client.get("currency", profile["bank"]["currency"])),
        field="currency",
        maximum=3,
    ).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise InvoiceError("invalid_currency", "currency must be a three-letter code")
    due_date = _bounded_text(
        request.get("due_date", client.get("default_due_date", "Upon Receipt")),
        field="due_date",
        maximum=80,
    )
    tax_rate = _decimal(request.get("tax_rate", "0"), field="tax_rate")
    if tax_rate > Decimal("100"):
        raise InvoiceError("invalid_money", "tax_rate cannot exceed 100")
    items, warnings = _line_items(request, client, period_display)
    subtotal = sum((Decimal(item["amount"]) for item in items), Decimal("0"))
    tax = (subtotal * tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    total = (subtotal + tax).quantize(MONEY, rounding=ROUND_HALF_UP)
    max_pages = request.get("max_pages", 1)
    if not isinstance(max_pages, int) or not 1 <= max_pages <= 5:
        raise InvoiceError("invalid_field", "max_pages must be an integer from 1 to 5")

    clean_request = {
        "client_key": client_key,
        "invoice_date": invoice_date.isoformat(),
        "billing_period": period,
        "currency": currency,
        "due_date": due_date,
        "items": items,
        "tax_rate": _money(tax_rate),
        "notes": _bounded_text(request.get("notes", ""), field="notes", maximum=1200, required=False),
        "max_pages": max_pages,
        "overlap_reason": overlap_reason,
    }
    if client_key not in profile["clients"]:
        clean_request["client"] = deepcopy(client)
    if replace_number:
        clean_request["replace_invoice_number"] = replace_number
        clean_request["replacement_reason"] = request["replacement_reason"]

    return {
        "invoice_number": invoice_number,
        "client_key": client_key,
        "client": client,
        "invoice_date": invoice_date.isoformat(),
        "invoice_date_display": _display_date(invoice_date),
        "billing_period": period,
        "billing_period_display": period_display,
        "due_date": due_date,
        "currency": currency,
        "tax_rate": _money(tax_rate),
        "items": items,
        "subtotal": _money(subtotal),
        "tax": _money(tax),
        "total": _money(total),
        "notes": clean_request["notes"],
        "max_pages": max_pages,
        "overlap_reason": overlap_reason,
        "warnings": warnings,
        "request": clean_request,
        "replacement_index": replacement_index,
        "previous": previous,
    }


def _lines(values: list[str]) -> str:
    return "<br>".join(html.escape(value) for value in values if value)


def _render_html(invoice: dict[str, Any], profile: dict[str, Any]) -> str:
    issuer = profile["issuer"]
    bank = profile["bank"]
    client = invoice["client"]
    currency = invoice["currency"]
    item_rows = []
    for item in invoice["items"]:
        description = (
            f'<div class="item-desc">{html.escape(item["description"])}</div>'
            if item["description"]
            else ""
        )
        item_rows.append(
            "<tr>"
            f'<td><strong>{html.escape(item["title"])}</strong>{description}</td>'
            f'<td>{html.escape(item["quantity"])}</td>'
            f'<td>{html.escape(_currency(Decimal(item["unit_price"]), currency))}</td>'
            f'<td>{html.escape(_currency(Decimal(item["amount"]), currency))}</td>'
            "</tr>"
        )
    billing = ""
    if invoice["billing_period_display"]:
        billing = (
            '<div><div class="meta-label">Billing Period</div>'
            f'<div class="meta-value">{html.escape(invoice["billing_period_display"])}</div></div>'
        )
    notes = ""
    if invoice["notes"]:
        notes = (
            '<div class="scope"><div class="scope-title">Notes</div>'
            f'<div class="scope-text">{html.escape(invoice["notes"])}</div></div>'
        )
    client_lines = []
    if client.get("email"):
        client_lines.append(str(client["email"]))
    client_lines.extend(str(line) for line in client.get("address_lines", []))
    if client.get("country") and str(client["country"]) not in client_lines:
        client_lines.append(str(client["country"]))
    issuer_lines = list(issuer["address_lines"])
    issuer_lines.extend([issuer["email"], issuer.get("phone", "")])
    item_count = len(invoice["items"])
    density = "dense" if item_count >= 8 else "compact" if item_count >= 5 else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Invoice {html.escape(invoice['invoice_number'])} - {html.escape(issuer['legal_name'])}</title>
<style>
  @page {{ size: A4; margin: 14mm 16mm; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ background: #fff; }}
  @media screen {{ body {{ width: 210mm; min-height: 297mm; padding: 14mm 16mm; }} }}
  body {{ font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1a1a1a; font-size: 10pt; line-height: 1.45; }}
  .header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; }}
  .brand {{ font-size:18pt; font-weight:700; color:#0a2540; letter-spacing:-0.5px; }}
  .brand-sub {{ font-size:9pt; color:#6b7280; margin-top:2px; }}
  .invoice-label {{ text-align:right; }}
  .invoice-label h1 {{ font-size:22pt; font-weight:300; color:#0a2540; letter-spacing:-1px; }}
  .invoice-number {{ font-size:9pt; color:#6b7280; margin-top:4px; }}
  .parties {{ display:flex; justify-content:space-between; gap:32px; margin-bottom:12px; }}
  .party {{ flex:1; min-width:0; }}
  .party-label, .meta-label, .scope-title, .bi-label {{ font-size:8pt; font-weight:600; text-transform:uppercase; letter-spacing:0.8px; color:#6b7280; }}
  .party-label {{ margin-bottom:8px; }}
  .party-name {{ font-weight:600; font-size:11pt; color:#0a2540; margin-bottom:4px; }}
  .party-detail {{ font-size:9.5pt; color:#4b5563; line-height:1.55; overflow-wrap:anywhere; }}
  .bank-inline {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:12px 16px; margin-bottom:18px; display:flex; flex-wrap:wrap; gap:10px 20px; font-size:9pt; }}
  .bank-inline > div {{ min-width:105px; }}
  .bi-label {{ font-size:7.5pt; margin-bottom:2px; }}
  .bi-value {{ color:#0a2540; font-weight:600; }}
  .iban {{ font-family:"SF Mono", Consolas, monospace; font-size:9pt; letter-spacing:0.2px; }}
  .meta-row {{ display:flex; gap:44px; margin-bottom:14px; }}
  .meta-label {{ margin-bottom:4px; }}
  .meta-value {{ font-size:10pt; font-weight:500; color:#0a2540; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:16px; table-layout:fixed; }}
  thead th {{ font-size:8pt; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:#6b7280; text-align:left; padding:8px 0; border-bottom:2px solid #e5e7eb; }}
  thead th:nth-child(1) {{ width:58%; }}
  thead th:nth-child(2) {{ width:9%; }}
  thead th:nth-child(3) {{ width:15%; }}
  thead th:nth-child(4) {{ width:18%; text-align:right; }}
  tbody td {{ padding:9px 0; border-bottom:1px solid #f3f4f6; color:#1a1a1a; font-size:9.5pt; vertical-align:top; overflow-wrap:anywhere; }}
  tbody td:last-child {{ text-align:right; font-weight:500; font-variant-numeric:tabular-nums; }}
  .item-desc {{ font-size:8.5pt; color:#6b7280; margin-top:2px; padding-right:12px; }}
  .totals {{ display:flex; justify-content:flex-end; margin-bottom:16px; }}
  .totals-box {{ width:280px; }}
  .total-row {{ display:flex; justify-content:space-between; padding:7px 0; font-size:10pt; color:#4b5563; }}
  .total-row.grand {{ padding:11px 0; margin-top:6px; border-top:2px solid #0a2540; font-size:14pt; font-weight:700; color:#0a2540; }}
  .scope {{ margin-bottom:14px; }}
  .scope-title {{ margin-bottom:7px; }}
  .scope-text {{ font-size:9pt; color:#4b5563; line-height:1.55; white-space:pre-line; }}
  .footer {{ padding-top:12px; border-top:1px solid #e5e7eb; font-size:8.3pt; color:#9ca3af; text-align:center; }}
  .compact .header {{ margin-bottom:14px; }} .compact .bank-inline {{ margin-bottom:14px; padding:10px 14px; }}
  .compact tbody td {{ padding:6px 0; }} .compact .totals {{ margin-bottom:12px; }}
  .dense .header {{ margin-bottom:10px; }} .dense .parties {{ margin-bottom:8px; }}
  .dense .bank-inline {{ margin-bottom:10px; padding:8px 12px; gap:6px 16px; }}
  .dense .meta-row {{ margin-bottom:8px; }} .dense tbody td {{ padding:4px 0; font-size:8.8pt; }}
  .dense .item-desc {{ font-size:8pt; }} .dense table {{ margin-bottom:8px; }}
  .dense .total-row {{ padding:4px 0; }} .dense .totals {{ margin-bottom:8px; }}
</style>
</head>
<body class="{density}">
<div class="header">
  <div><div class="brand">{html.escape(issuer['legal_name'])}</div><div class="brand-sub">{html.escape(issuer['legal_status'])} · {html.escape(issuer.get('business_label', 'Software Development'))}</div></div>
  <div class="invoice-label"><h1>Invoice</h1><div class="invoice-number">{html.escape(invoice['invoice_number'])} · {html.escape(invoice['invoice_date_display'])}</div></div>
</div>
<div class="parties">
  <div class="party"><div class="party-label">From</div><div class="party-name">{html.escape(issuer['legal_name'])}</div><div class="party-detail">{html.escape(issuer['legal_status'])}<br>{_lines(issuer_lines)}</div></div>
  <div class="party"><div class="party-label">Bill To</div><div class="party-name">{html.escape(client['legal_name'])}</div><div class="party-detail">{_lines(client_lines)}</div></div>
</div>
<div class="bank-inline">
  <div><div class="bi-label">Beneficiary</div><div class="bi-value">{html.escape(bank['beneficiary'])}</div></div>
  <div><div class="bi-label">Bank</div><div class="bi-value">{html.escape(bank['name'])}</div></div>
  <div><div class="bi-label">Country</div><div class="bi-value">{html.escape(bank['country'])}</div></div>
  <div><div class="bi-label">Currency</div><div class="bi-value">{html.escape(currency)}</div></div>
  <div><div class="bi-label">IBAN</div><div class="bi-value iban">{html.escape(bank['iban'])}</div></div>
  <div><div class="bi-label">BIC/SWIFT</div><div class="bi-value">{html.escape(bank['swift'])}</div></div>
</div>
<div class="meta-row">
  <div><div class="meta-label">Invoice Date</div><div class="meta-value">{html.escape(invoice['invoice_date_display'])}</div></div>
  {billing}
  <div><div class="meta-label">Due Date</div><div class="meta-value">{html.escape(invoice['due_date'])}</div></div>
  <div><div class="meta-label">Currency</div><div class="meta-value">{html.escape(currency)}</div></div>
</div>
<table><thead><tr><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead><tbody>{''.join(item_rows)}</tbody></table>
<div class="totals"><div class="totals-box">
  <div class="total-row"><span>Subtotal</span><span>{html.escape(_currency(Decimal(invoice['subtotal']), currency))}</span></div>
  <div class="total-row"><span>Tax ({html.escape(invoice['tax_rate'])}%)</span><span>{html.escape(_currency(Decimal(invoice['tax']), currency))}</span></div>
  <div class="total-row grand"><span>Total</span><span>{html.escape(_currency(Decimal(invoice['total']), currency))}</span></div>
</div></div>
{notes}
<div class="scope"><div class="scope-title">Payment Details</div><div class="scope-text">Payment by bank transfer to the account above ({html.escape(bank['name'])}, IBAN {html.escape(bank['iban'])}, BIC/SWIFT {html.escape(bank['swift'])}, beneficiary {html.escape(bank['beneficiary'])}). Please reference this invoice number ({html.escape(invoice['invoice_number'])}) in the transfer.</div></div>
<div class="footer">{html.escape(issuer['legal_name'])} · {html.escape(issuer['legal_status'])} · {html.escape(issuer['website'])} · {html.escape(issuer['email'])}</div>
</body>
</html>
"""


def _browser(explicit: str | None) -> Path:
    candidates: list[Path] = []
    for value in (explicit, os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH")):
        if value:
            candidates.append(Path(value))
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome-headless-shell"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend(
        Path.home().glob("Library/Caches/ms-playwright/**/chrome-headless-shell")
    )
    candidates.extend(
        Path.home().glob(".cache/puppeteer/**/chrome-headless-shell")
    )
    candidates.extend(
        [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    )
    candidates.extend(Path("/opt/hermes/.playwright").glob("**/chrome-headless-shell"))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise InvoiceError("browser_missing", "no supported headless Chromium binary was found")


def _run_browser(browser: Path, arguments: list[str], user_data_dir: Path) -> None:
    command = [
        str(browser),
        "--headless",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "--run-all-compositor-stages-before-draw",
        f"--user-data-dir={user_data_dir}",
        *arguments,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        raise InvoiceError("render_timeout", "headless Chromium exceeded 90 seconds") from error
    if process.returncode != 0:
        detail = (stderr or stdout or "unknown browser failure").strip().splitlines()[-1]
        raise InvoiceError("render_failed", f"headless Chromium failed: {detail[:300]}")


def _pdf_page_count(path: Path) -> int:
    raw = path.read_bytes()
    count = len(re.findall(rb"/Type\s*/Page\b", raw))
    if count < 1:
        raise InvoiceError("invalid_pdf", "rendered PDF has no readable page objects")
    return count


def _render(invoice: dict[str, Any], profile: dict[str, Any], state_dir: Path, browser: Path) -> dict[str, Any]:
    client_dir = state_dir / invoice["client_key"]
    _prepare_private_directory(client_dir)
    stem = f"{invoice['client'].get('file_stem', invoice['client_key'].title())}_Invoice_{invoice['invoice_number']}"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", stem):
        raise InvoiceError("invalid_filename", "client file_stem produced an unsafe filename")
    final = {
        "html_path": client_dir / f"{stem}.html",
        "pdf_path": client_dir / f"{stem}.pdf",
        "preview_path": client_dir / f"{stem}.png",
        "manifest_path": client_dir / f"{stem}.json",
    }
    with tempfile.TemporaryDirectory(prefix=".invoice-", dir=client_dir) as temporary:
        temp_dir = Path(temporary)
        html_path = temp_dir / "invoice.html"
        pdf_path = temp_dir / "invoice.pdf"
        preview_path = temp_dir / "invoice.png"
        html_path.write_text(_render_html(invoice, profile), encoding="utf-8")
        os.chmod(html_path, 0o600)
        url = html_path.resolve().as_uri()
        _run_browser(browser, [f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer", url], temp_dir / "chrome-pdf")
        _run_browser(
            browser,
            [f"--screenshot={preview_path}", "--window-size=794,1123", "--force-device-scale-factor=1", url],
            temp_dir / "chrome-preview",
        )
        if not pdf_path.is_file() or pdf_path.stat().st_size < 1024:
            raise InvoiceError("invalid_pdf", "rendered PDF is missing or empty")
        if not preview_path.is_file() or preview_path.stat().st_size < 1024 or preview_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise InvoiceError("invalid_preview", "rendered PNG preview is missing or invalid")
        pages = _pdf_page_count(pdf_path)
        if pages > invoice["max_pages"]:
            raise InvoiceError(
                "layout_overflow",
                f"invoice rendered as {pages} pages; maximum is {invoice['max_pages']}",
                page_count=pages,
            )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "invoice_number": invoice["invoice_number"],
            "client_key": invoice["client_key"],
            "page_count": pages,
            "pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "pdf_bytes": pdf_path.stat().st_size,
            "preview_sha256": hashlib.sha256(preview_path.read_bytes()).hexdigest(),
            "rendered_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = temp_dir / "manifest.json"
        _atomic_json(manifest_path, manifest)
        for key, source in (
            ("html_path", html_path),
            ("pdf_path", pdf_path),
            ("preview_path", preview_path),
            ("manifest_path", manifest_path),
        ):
            os.chmod(source, PRIVATE_FILE_MODE)
            os.replace(source, final[key])
            os.chmod(final[key], PRIVATE_FILE_MODE)
    return {**{key: str(value) for key, value in final.items()}, **manifest}


def _safe_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "invoice_number",
            "revision",
            "client_key",
            "client_name",
            "invoice_date",
            "billing_period",
            "currency",
            "total",
            "page_count",
            "created_at",
            "updated_at",
        )
        if record.get(key) is not None
    }


def status(profile_path: Path, state_dir: Path) -> dict[str, Any]:
    profile = _load_json(profile_path)
    _validate_profile(profile)
    _prepare_private_directory(state_dir)
    ledger = _load_ledger(state_dir / "ledger.json", profile)
    by_year: dict[str, int] = {}
    for record in ledger["invoices"]:
        match = INVOICE_NUMBER.fullmatch(str(record.get("invoice_number", "")))
        if match:
            year, number = match.groups()
            by_year[year] = max(by_year.get(year, 0), int(number))
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "known_clients": [
            {"key": key, "legal_name": client["legal_name"]}
            for key, client in sorted(profile["clients"].items())
        ],
        "latest_sequence_by_year": by_year,
        "invoices": [_safe_record(record) for record in ledger["invoices"]],
    }


def create(profile_path: Path, state_dir: Path, request_path: Path, browser_path: str | None) -> dict[str, Any]:
    profile = _load_json(profile_path)
    _validate_profile(profile)
    request = _load_json(request_path)
    _prepare_private_directory(state_dir)
    lock_path = state_dir / ".ledger.lock"
    lock_path.touch(mode=PRIVATE_FILE_MODE, exist_ok=True)
    _ensure_mode(lock_path, PRIVATE_FILE_MODE)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger_path = state_dir / "ledger.json"
        ledger = _load_ledger(ledger_path, profile)
        invoice = _resolve(request, profile, ledger)
        rendered = _render(invoice, profile, state_dir, _browser(browser_path))
        now = datetime.now(timezone.utc).isoformat()
        previous = invoice["previous"] or {}
        revision = int(previous.get("revision", 0)) + 1
        record = {
            "invoice_number": invoice["invoice_number"],
            "revision": revision,
            "client_key": invoice["client_key"],
            "client_name": invoice["client"]["legal_name"],
            "invoice_date": invoice["invoice_date"],
            "billing_period": invoice["billing_period"],
            "currency": invoice["currency"],
            "subtotal": invoice["subtotal"],
            "tax_rate": invoice["tax_rate"],
            "tax": invoice["tax"],
            "total": invoice["total"],
            "items": invoice["items"],
            "overlap_reason": invoice["overlap_reason"],
            "request": invoice["request"],
            "page_count": rendered["page_count"],
            "pdf_sha256": rendered["pdf_sha256"],
            "paths": {
                key: rendered[key]
                for key in ("html_path", "pdf_path", "preview_path", "manifest_path")
            },
            "created_at": previous.get("created_at", now),
            "updated_at": now,
            "source": "hermes",
        }
        replacement_index = invoice["replacement_index"]
        if replacement_index is None:
            ledger["invoices"].append(record)
        else:
            record["replacement_reason"] = invoice["request"]["replacement_reason"]
            ledger["invoices"][replacement_index] = record
        _atomic_json(ledger_path, ledger)
        return {
            "ok": True,
            **_safe_record(record),
            "warnings": invoice["warnings"],
            **record["paths"],
            "pdf_sha256": record["pdf_sha256"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "create"))
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--browser")
    args = parser.parse_args()
    try:
        if args.command == "status":
            result = status(args.profile, args.state_dir)
        else:
            if args.request is None:
                raise InvoiceError("missing_argument", "--request is required for create")
            result = create(args.profile, args.state_dir, args.request, args.browser)
    except InvoiceError as error:
        print(json.dumps({"ok": False, "code": error.code, "error": str(error), **error.details}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
