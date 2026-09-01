---
name: david-invoice-writing
description: Create, revise, verify, upload, and deliver David's invoices. Use when David asks for an invoice, bill, billing statement, recurring Kidays billing, line items, invoice numbering, or an update to an existing invoice.
---

# David Invoice Writing

Create invoices from the private owner profile and durable invoice ledger. Read
`references/invoice-method.md` before the first invoice operation in a session.

## Fixed paths

- Engine: `/etc/hermes-skills/david-invoice-writing/scripts/invoice_engine.py`
- Private profile: `/etc/hermes-invoice-private/profile.json`
- Durable state and output: `/opt/data/workspace/invoices`

Never copy issuer, bank, or client details into chat, memory, another skill, a
Fleet Task, or a public-server profile. Those details may appear only in the
private request file, ledger, HTML, PDF, and Seedyn upload that David requested.

## Workflow

1. Inspect safe history and known client keys:

   ```bash
   python /etc/hermes-skills/david-invoice-writing/scripts/invoice_engine.py \
     status \
     --profile /etc/hermes-invoice-private/profile.json \
     --state-dir /opt/data/workspace/invoices
   ```

2. Resolve the client, invoice date, billing period, due date, currency, and
   line items from David's request. Use the accepted recurring defaults only
   when he omits an amount for a known item. Ask one focused question when a
   new client's legal details or another material value is missing.
3. Write a JSON request under `/tmp`. Do not include issuer or bank fields; the
   engine reads those from the private profile. Use the schema in the reference.
4. Create the invoice. The engine holds an exclusive lock, allocates the next
   number, escapes user text, renders A4 HTML and PDF, produces a PNG preview,
   rejects page overflow, writes checksums, and commits the ledger atomically.
5. If the engine reports `duplicate_billing_period`, show the conflicting
   invoice number and ask whether David intentionally wants another invoice for
   that period. Retry only with his short reason in `overlap_reason`.
6. If the engine reports a contract-price warning, keep David's explicit amount
   and mention the mismatch once after generation. It is a warning, not a block.
7. Inspect the PNG preview with vision. Reject clipped, overlapping, illegible,
   or visibly unbalanced output. Shorten descriptions and retry without changing
   monetary meaning. Do not claim success until the PDF has the requested page
   count and the preview is clean.
8. Follow the `seedyn-delivery` skill: read current Seedyn docs when needed,
   upload the PDF through the bounded broker, require an allowed HTTPS URL, and
   verify it. Reply with the verified URL and the native attachment:

   ```text
   MEDIA:/opt/data/workspace/invoices/<client>/<invoice>.pdf
   ```

   If Seedyn fails but the PDF exists, state that once and still attach the PDF.
9. Do not email, message, or otherwise send an invoice to its client unless
   David separately names the destination and explicitly asks for delivery.

## Revisions

Creating a new invoice is the default. Replace an existing invoice only when
David explicitly asks to update that invoice. Set `replace_invoice_number` and
`replacement_reason`; the engine preserves its number, increments its revision,
and replaces the HTML, PDF, preview, manifest, and ledger entry atomically.

Delete no prior invoice. Do not renumber history. Do not fabricate tax or legal
details. Do not treat a draft, failed render, or unverified upload as complete.
