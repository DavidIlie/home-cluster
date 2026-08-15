# Executable contract method

This method is distilled from David's feature-threads contract pack and project
audit briefs. It preserves the writing system without copying private product
content.

## Suggested pack

Adapt the list to the project; do not create empty ceremony.

1. `00-stack-and-conventions.md`: runtime, libraries, repository layout, naming,
   IDs, time, money, errors, pagination, testing, and frozen decisions.
2. `01-terminology-and-states.md`: canonical nouns, enums, state machines,
   transitions, actors, and forbidden aliases.
3. Data and tenancy: entities, fields, constraints, indexes, ownership,
   invariants, retention, migrations, and legal write paths.
4. API and MCP: exact request/response shapes, scopes, errors, pagination,
   idempotency, versioning, and approval boundaries.
5. Events and integrations: names, payloads, producers, consumers, ordering,
   deduplication, retries, signatures, replay, and dead-letter behavior.
6. Runtime and operations: deployment, secrets, observability, SLOs, backup,
   recovery, rollout, rollback, and capacity.
7. UX and commercial contracts when relevant: view states, accessibility,
   entitlements, billing, cancellation, export, and deletion.
8. Acceptance matrix: vertical slices, negative cases, fixtures, commands, and
   evidence required before release.

## Rules

- One owner per contract. Other documents reference it rather than redefining it.
- Every contract starts with purpose, authority, dependencies, and source
  provenance, then ends with non-goals, open questions, and acceptance tests.
- Use exact examples and schemas where ambiguity is expensive.
- Distinguish current fact, frozen decision, proposed decision, and open question.
- Version breaking changes deliberately; never let two wire meanings share a
  name or one meaning drift across multiple names.
- Make unsafe or illegal states unrepresentable where practical, then test the
  remaining guards.
