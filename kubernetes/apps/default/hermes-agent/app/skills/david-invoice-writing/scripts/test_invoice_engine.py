from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import invoice_engine


def profile() -> dict:
    return {
        "schema_version": 1,
        "issuer": {
            "legal_name": "David Example",
            "legal_status": "individual",
            "business_label": "Software Development",
            "email": "david@example.com",
            "website": "example.com",
            "phone": "+40 000 000 000",
            "address_lines": ["Example Street", "Romania"],
        },
        "bank": {
            "beneficiary": "David Example",
            "name": "Example Bank",
            "country": "Romania",
            "currency": "EUR",
            "iban": "RO00 EXAMPLE",
            "swift": "EXAMPLER0",
        },
        "clients": {
            "kidays": {
                "legal_name": "Kidays SAS",
                "email": "hello@example.com",
                "country": "France",
                "address_lines": [],
                "file_stem": "Kidays",
                "currency": "EUR",
                "billing_rule": "arrears_first_day",
                "default_due_date": "Upon Receipt",
                "line_item_defaults": {
                    "retainer": {
                        "title": "Development retainer",
                        "description": "Monthly development services - {billing_period}.",
                        "quantity": "1",
                        "unit_price": "1000.00",
                    },
                    "hosting": {
                        "title": "Hosting",
                        "description": "Monthly application hosting.",
                        "quantity": "1",
                        "unit_price": "500.00",
                        "contract_unit_price": "250.00",
                    },
                },
            }
        },
        "history": [
            {
                "invoice_number": "INV-2026-007",
                "client_key": "kidays",
                "client_name": "Kidays SAS",
                "invoice_date": "2026-08-01",
                "billing_period": "2026-07",
                "currency": "EUR",
                "total": "1500.00",
                "request": {
                    "client_key": "kidays",
                    "invoice_date": "2026-08-01",
                    "billing_period": "2026-07",
                    "currency": "EUR",
                    "due_date": "Upon Receipt",
                    "items": [
                        {"key": "retainer", "title": "Development retainer", "description": "Monthly development services.", "quantity": "1", "unit_price": "1000.00", "amount": "1000.00"},
                        {"key": "hosting", "title": "Hosting", "description": "Monthly application hosting.", "quantity": "1", "unit_price": "500.00", "amount": "500.00"},
                    ],
                    "tax_rate": "0.00",
                    "notes": "",
                    "max_pages": 1,
                    "overlap_reason": "",
                },
            }
        ],
    }


class InvoiceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = profile()
        self.ledger = invoice_engine._bootstrap_ledger(self.profile)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_next_number_and_arrears_date(self) -> None:
        request = {
            "client_key": "kidays",
            "billing_period": "2026-08",
            "items": [{"key": "retainer"}, {"key": "hosting"}],
        }
        resolved = invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(resolved["invoice_number"], "INV-2026-008")
        self.assertEqual(resolved["invoice_date"], "2026-09-01")
        self.assertEqual(resolved["total"], "1500.00")
        self.assertEqual(
            resolved["items"][0]["description"],
            "Monthly development services - August 2026.",
        )
        self.assertEqual(len(resolved["warnings"]), 1)

    def test_duplicate_period_fails_closed(self) -> None:
        request = {
            "client_key": "kidays",
            "billing_period": "2026-07",
            "items": [{"key": "retainer"}],
        }
        with self.assertRaises(invoice_engine.InvoiceError) as caught:
            invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(caught.exception.code, "duplicate_billing_period")
        self.assertEqual(caught.exception.details["conflicting_invoices"], ["INV-2026-007"])

    def test_explicit_overlap_is_recorded(self) -> None:
        request = {
            "client_key": "kidays",
            "billing_period": "2026-07",
            "overlap_reason": "Separate approved work",
            "items": [{"key": "retainer"}],
        }
        resolved = invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(resolved["overlap_reason"], "Separate approved work")

    def test_revision_preserves_number(self) -> None:
        request = {
            "replace_invoice_number": "INV-2026-007",
            "replacement_reason": "Correct hosting amount",
            "items": [{"key": "retainer"}, {"key": "hosting", "unit_price": "600.00"}],
        }
        resolved = invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(resolved["invoice_number"], "INV-2026-007")
        self.assertEqual(resolved["total"], "1600.00")
        self.assertEqual(resolved["replacement_index"], 0)

    def test_named_additional_work_item_uses_profile_default(self) -> None:
        self.profile["clients"]["kidays"]["line_item_defaults"]["high_complexity"] = {
            "title": "Additional coding - high complexity",
            "description": "Additional development.",
            "quantity": "1",
            "unit_price": "1500.00",
        }
        request = {
            "client_key": "kidays",
            "billing_period": "2026-08",
            "items": [{"key": "high_complexity"}],
        }
        resolved = invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(resolved["items"][0]["unit_price"], "1500.00")

    def test_unknown_client_needs_details(self) -> None:
        request = {"client_key": "new-client", "invoice_date": "2026-09-01", "items": []}
        with self.assertRaises(invoice_engine.InvoiceError) as caught:
            invoice_engine._resolve(request, self.profile, self.ledger)
        self.assertEqual(caught.exception.code, "unknown_client")

    def test_html_escapes_client_controlled_text(self) -> None:
        request = {
            "client_key": "acme",
            "client": {"legal_name": "<Acme>", "country": "Romania"},
            "invoice_date": "2026-09-01",
            "items": [{"title": "Work <script>", "quantity": "1", "unit_price": "10"}],
        }
        resolved = invoice_engine._resolve(request, self.profile, self.ledger)
        rendered = invoice_engine._render_html(resolved, self.profile)
        self.assertIn("&lt;Acme&gt;", rendered)
        self.assertIn("Work &lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_status_never_returns_bank_or_issuer(self) -> None:
        profile_path = self.root / "profile.json"
        profile_path.write_text(json.dumps(self.profile), encoding="utf-8")
        output = invoice_engine.status(profile_path, self.root / "state")
        serialized = json.dumps(output)
        self.assertNotIn("RO00 EXAMPLE", serialized)
        self.assertNotIn("Example Bank", serialized)


if __name__ == "__main__":
    unittest.main()
