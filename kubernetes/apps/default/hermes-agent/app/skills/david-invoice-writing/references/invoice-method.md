# Invoice method and request contract

This method is recovered from David's invoice protocol and the accepted Kidays
invoice sequence through `INV-2026-007`.

## Settled behavior

- Inspect the ledger before choosing a number or claiming a billing period is
  free.
- Continue `INV-<year>-<three digits>` independently per invoice year.
- Recurring monthly work is billed in arrears on the first day of the following
  month when the client profile says `arrears_first_day`.
- A second invoice for the same client and billing period is blocked until David
  confirms the overlap. The accepted history deliberately contains two June
  2026 Kidays invoices; preserve both.
- David's explicit amount wins over an older contract amount. Report the
  mismatch once, without silently rewriting either value.
- An explicit update preserves the invoice number and revises the existing
  record. Otherwise create a new number.
- Default output is one A4 page, with a clean Stripe-like hierarchy: issuer and
  invoice header, parties, bank details, invoice metadata, line items, totals,
  payment note, footer.
- Store HTML and PDF together. Verify page count and inspect the PNG preview.
- Upload the verified PDF to Seedyn and attach the native PDF in the same Discord
  reply.

## New-invoice request

Amounts and quantities are strings so decimal arithmetic stays exact.

```json
{
  "client_key": "kidays",
  "billing_period": "2026-08",
  "items": [
    {"key": "retainer", "unit_price": "1000.00"},
    {"key": "hosting", "unit_price": "500.00"},
    {
      "title": "Additional coding - medium complexity",
      "description": "Additional development outside the base retainer.",
      "quantity": "1",
      "unit_price": "800.00"
    }
  ],
  "tax_rate": "0",
  "max_pages": 1
}
```

For a known recurring client, `invoice_date`, `currency`, `due_date`, item title,
description, quantity, and accepted recurring amount may come from the private
profile. A supplied field overrides its default. For an unknown client, include:

```json
{
  "client_key": "acme",
  "client": {
    "legal_name": "Acme Example SRL",
    "email": "billing@example.com",
    "country": "Romania",
    "address_lines": ["Optional address line"]
  },
  "invoice_date": "2026-09-01",
  "billing_period": "2026-08",
  "currency": "EUR",
  "due_date": "14 September 2026",
  "items": [
    {
      "title": "Software development",
      "description": "Development services for August 2026.",
      "quantity": "1",
      "unit_price": "1200.00"
    }
  ]
}
```

New client details persist only in the private invoice ledger. Do not add them
to general memory.

## Intentional overlap

After David confirms that a same-period invoice is intentional, add a concise
reason:

```json
{"overlap_reason": "Separate additional-work invoice approved by David"}
```

## Existing-invoice revision

Include the complete corrected line-item list. Do not rely on a conversational
delta alone.

```json
{
  "replace_invoice_number": "INV-2026-006",
  "replacement_reason": "Increase high-complexity work by EUR 500",
  "items": [
    {"key": "retainer", "unit_price": "1000.00"},
    {"key": "hosting", "unit_price": "500.00"},
    {"key": "low_complexity", "unit_price": "200.00"},
    {"key": "medium_complexity", "unit_price": "800.00"},
    {"key": "high_complexity", "unit_price": "1500.00"}
  ]
}
```

## Optional fields

- `invoice_date`: ISO `YYYY-MM-DD`; inferred only for a profiled arrears client.
- `billing_period`: ISO month `YYYY-MM`; omit only for genuinely non-periodic work.
- `notes`: bounded text printed above the footer.
- `max_pages`: defaults to `1`; values above one require David's explicit request.
- `overlap_reason`: required only for an intentional same-period invoice.
- `replace_invoice_number` and `replacement_reason`: required together for a
  revision.

## Delivery response

Keep the response short: invoice number, client, billing period, total, revision
if applicable, any contract-price warning, verified Seedyn URL, and the native
PDF attachment. Do not paste bank details or the full private client record into
Discord text.
