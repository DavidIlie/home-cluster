---
name: david-work-audit
description: Audit plans, implementations, pull requests, releases, and completed work using David's evidence-first protocol. Use when David asks to audit, review, reconcile, verify, rate, inspect what changed, check completeness, deepen a plan, or decide whether work is genuinely done.
---

# David Work Audit

Audit for truth and execution readiness, not reassurance. Read
`references/audit-protocol.md` before starting a substantial audit.

## Operating mode

1. Establish scope, canonical requirements, repository rules, and whether the
   request is audit-only or explicitly permits fixes.
2. Reconstruct the actual change from files, Git history, receipts, live state,
   tests, and user-visible behavior. Do not trust a summary by itself.
3. Inspect the relevant implementation deeply enough to follow data, authority,
   failure, and lifecycle paths end to end.
4. Test or query live state in proportion to risk. Record exact commands,
   affected files, observations, and limitations.
5. Challenge weak, contradictory, or evidence-free claims. Investigate before
   declaring a blocker.
6. Report findings by severity with evidence, impact, recommended fix, and a
   concrete verification step.

## Boundaries

- Audit-only is read-only unless David explicitly authorizes fixes.
- Never describe planned work as deployed or an untested change as working.
- Separate fact, inference, and recommendation.
- Treat authentication, authorization, tenancy, PII, retries, idempotency,
  payments, timezones, locking, notifications, state transitions, and audit
  history as first-class edge cases whenever applicable.
- Do not copy project contents or private work artifacts into persistent memory.
  Memory may retain only a compact stable preference or reusable method.

## Deliverable

Lead with the verdict. Then list findings ordered by severity, the evidence for
each, and the smallest correct fix. Close with verification performed, residual
risks, and an explicit ready/not-ready judgment.
