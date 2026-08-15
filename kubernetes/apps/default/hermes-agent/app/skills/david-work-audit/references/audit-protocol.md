# David's evidence-first audit protocol

This is a durable synthesis of David's local audit briefs and the Kidays
Ultracode thread-run protocol. It captures the method, not private project data.

## Standard

- Deep before done. Optimize for quality, coverage, and evidence rather than
  activity, tokens, or a polished-sounding conclusion.
- The lead auditor must synthesize, resolve contradictions, and redispatch or
  investigate when evidence is thin. Never paste together unchecked findings.
- Every material claim should be traceable to files, line references, commands,
  tests, screenshots, API responses, live state, or clearly marked inference.
- Reconstruct the real work from Git history, receipts, implementation, tests,
  and product behavior before assessing it.
- Compare against canonical requirements and resolved decisions, not memory of
  an earlier plan.

## Coverage map

For a product or system plan, examine as applicable:

1. Product/domain language, workflows, non-goals, and acceptance criteria.
2. Schema, invariants, tenancy, ownership, authorization, lifecycle, and
   migration rules.
3. API, MCP, event, webhook, pagination, versioning, retry, and idempotency
   contracts.
4. Threat model, secrets, privacy, abuse limits, auditability, and permission
   boundaries.
5. Operations: SLOs, observability, capacity, backup, recovery, rollout,
   rollback, and failure containment.
6. UX states: loading, empty, partial, error, retry, destructive confirmation,
   accessibility, and mobile behavior.
7. Commercial rules: entitlements, metering, billing, cancellation, retention,
   export, and deletion when relevant.
8. A vertical slice proving the contracts join cleanly from UI through storage,
   integrations, operations, and tests.

## Finding format

For each finding include:

- Severity and concise title.
- Evidence and exact location.
- Why it matters and who is affected.
- Corrective action that preserves established decisions.
- Verification that would prove closure.
- Confidence and any unresolved assumption.

Preserve conflicts as explicit open questions. Do not silently reconcile them.
