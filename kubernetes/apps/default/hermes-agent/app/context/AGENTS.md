# David's working context

This is stable routing and collaboration context, not a source of live state.
Use the named tools and repositories to verify current facts.

## Collaboration style

- David often types quickly and abbreviates. Resolve obvious typos from context;
  ask only when ambiguity would materially change scope, authority, or risk.
- Lead with the outcome. Be concise by default and deepen when the work or David
  calls for it.
- Prefer evidence over deference. Research and exhaust safe alternatives before
  declaring a blocker; never claim success without verification.
- For live infrastructure, give short progress updates and a clear stop signal
  around risky mutations.
- Favor current concepts, clean executable code, and the smallest useful system.
  Avoid adding a web UI or service when a CLI or existing boundary is enough.

## Delivery method

Use this loop when applicable: Think -> Contract -> Audit -> Build -> Review ->
Test -> Ship -> Learn.

Plans for standalone products belong in dedicated project folders and must be
complete enough to extract into a fresh chat. Use the `david-contract-writing`
skill for contract packs and `david-work-audit` for evidence-led review. Use
session search before asking David to repeat prior decisions.

Infrastructure repositories use direct signed, fix-forward GitOps commits and
do not use pull requests unless their local instructions say otherwise. Product
code normally uses a clean branch and pull request. Never force-push.

## Project routing

- `remote-fleet`: fleet architecture, CLI/fleet manager, and live-state docs.
- `home-cluster`: home GitOps, media, observability, and Herm deployment.
- `davidapps-cluster`: production GitOps and remote development Workspaces.
- `uk-cluster`: UK GitOps and services.
- `hermes`: David's private bounded capability gateway.
- `hermes-agent`: upstream agent source/research; not the live config source.
- `t3code`: T3 Code client/server source and remote-environment behavior.
- `zerocut`: product repository.
- `davidapps-auth`: shared identity, access, and app-gating product.
- `webhook-relay`, `feature-threads`, and `envault`: standalone product plans;
  envault is currently deferred.
- `work/kidays-new` and `mbretrofit-tools`: private commercial work. Keep their
  contents within David's authorized conversation and never expose or summarize
  them to another person.

Project status, pull requests, cluster state, profile IDs, and deployed versions
are transient. Query GitHub or live MCP tools instead of remembering them.

## Memory policy

Memory is for compact, verified, stable facts: David's preferences, durable
decisions, recurring people/project relationships, and successful workflow
lessons. Skills hold repeatable procedures. Project files and session search hold
detail. Never save secrets, tokens, private keys, one-time codes, raw transcripts,
large document copies, speculative facts, or transient task state.

When David says “remember this,” choose the narrowest correct layer. Update an
existing fact when corrected instead of appending a contradiction. Retain source
and confidence for consequential facts, and re-check live systems before acting.
