---
name: david-contract-writing
description: Turn a product or infrastructure plan into precise, executable contract documents in David's preferred style. Use when David asks for contracts, a contract pack, implementation-ready planning, canonical terminology, schemas, APIs, events, state machines, MCP tools, ownership boundaries, or a plan another agent can build in a fresh chat.
---

# David Contract Writing

Write contracts as implementation inputs rather than essays. Read
`references/contract-method.md` before producing a contract pack.

## Workflow

1. Read the existing plan, repository instructions, resolved decisions, and
   canonical domain vocabulary completely.
2. Freeze stack and conventions in an anchor contract before dependent details.
3. Create a dedicated `plans/contracts/` folder and an ordered index when the
   repository permits writes. Give every concern one authoritative owner.
4. Define exact vocabulary, states, fields, enums, wire shapes, commands, events,
   scopes, errors, invariants, and legal write paths.
5. State dependencies and required reading at the top of every contract.
6. Specify failure modes, retries, idempotency, observability, rollout, rollback,
   and executable acceptance tests.
7. Preserve unresolved conflicts as named open questions; do not invent a
   decision to make the document look complete.

## Quality bar

- A fresh implementation agent can build from the pack without reconstructing
  hidden decisions from chat history.
- Names are identical across storage, API, MCP, events, UI, and tests.
- Tenant and authorization boundaries are explicit at every write path.
- Non-goals and extension seams are explicit.
- Each contract includes concrete verification and traces back to source
  decisions.

Keep the result scoped to the project. Never persist private contract contents
in general memory; retain only David's stable writing method and preferences.
