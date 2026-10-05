# Bostan developer Grafana

Prepared, inactive GitOps configuration for Libertos operational dashboards.
`ks.yaml` is suspended and is not referenced by the observability aggregate.
There is no tunnel route, DNS record, access grant, or secret in this change.
The approved production hostname is `monitoring.bostanenterprise.com`.

## Authorization and data access

Use a dedicated closed DavidApps OIDC application, slug `grafana-bostan`, with
callback `https://monitoring.bostanenterprise.com/login/generic_oauth`. The existing recorded
group is `Bostan Enterprise Employees`; see
`docs/runbooks/grafana-project-access.md`. Read-only access/audit catalog calls
returned insufficient scope during preparation, and Grafana's Viewer service
account could not read teams. The live group ID, membership, org placement,
domain-sync policy, and grants remain unverified. No membership is inferred
from `bostanenterprise.com`, and no group or grant has been changed.

Before activation, an authorized operator must resolve the existing group and
its current org, verify the intended verified `bostanenterprise.com` accounts,
and grant that group access to the dedicated app. Do not create a replacement
group, enroll an entire email domain, or copy a personal account list. If the
organization split has happened, use the supported cross-org OIDC grant. Prove
one intended member is allowed and one non-member is denied. These are
activation checks, not claims that they have already passed.

Everyone gets the Grafana Viewer role, including the owner. This copies the
Kidays OIDC settings, with login/basic/anonymous auth, Explore, editing,
alerting, snapshots, public dashboards, and Live disabled. The 10-minute
absolute session lifetime bounds reauthorization; revocation is not enforced
on every request. OIDC uses pairwise `sub`, PKCE, and signed ID-token validation.
There is no email account auto-linking or Grafana admin role from a claim.

The only datasource endpoint is `bostan-query-gateway`. It accepts exact
reviewed query templates from the same files Grafana provisions, with bounded
time/interval substitutions. Network policies restrict Grafana to that gateway,
DNS, and HTTPS to the identity/plugin hosts. The gateway can reach the two
Prometheus instances and VictoriaLogs. MB Retrofit is not part of Bostan's
allowlist. It remains in shared administrator Grafana.

The Bostan folder UID is `apps-bostan`, matching shared Grafana. The dedicated
copies preserve canonical queries and remove shared administrator Explore
navigation. They are not editable. There is no Tempo datasource in this
instance because the current query gateway does not support it. A team member
can give an operator a `trace_id`; operators can follow trace/log links in the
shared instance. Do not add a direct Tempo datasource to bypass this boundary.

## Secret and activation dependencies

The approved non-model mover in `davidapps-auth`,
`scripts/davidapps-sops-import.mjs`, currently allowlists only Kidays. A separate
reviewed auth change must add Bostan's exact registered app/client IDs and
approved hostname. Its output must be these encrypted files:

| File | Secret name | Keys |
| --- | --- | --- |
| `app/oidc-secret.sops.yaml` | `grafana-bostan-oidc-secret` | `client-id`, `client-secret` |
| `app/admin-secret.sops.yaml` | `grafana-bostan-admin-secret` | `admin-user`, `admin-password` |
| `app/gateway-secret.sops.yaml` | `bostan-query-gateway-secret` | `bearer.token` |

No plaintext placeholders or copied Kidays ciphertext are committed. These
files are intentionally absent from `app/kustomization.yaml` until the mover
creates them. A future activation PR must add those resources, add the home
cloudflared route and DNS target for `monitoring.bostanenterprise.com`, add a
Homepage entry, unsuspend `ks.yaml`, and reference it in the
observability aggregate. Do not activate only part of that configuration.

Application telemetry and public ingest live in separate repository PRs.
Libertos server services are `libertos-web` and `libertos-convex` with project
and namespace `libertos`. Browser `libertos-browser` remains disabled pending
the application owner's consent decision. Empty browser panels are expected.
Full deployed SHA links refer to `BostanEnterprise/libertos`.

## Validation

Render `app` with Kustomize and the pinned Grafana chart `10.5.15`. Run the
pinned query gateway with `--check --config=app/gateway/config.json
--dashboards=app/dashboards`. It must accept every target and refuse a dashboard
that replaces a Libertos selector with a foreign project or an unscoped query.
Refresh the dedicated copies when shared queries change; never hand-maintain a
second query contract. Helm rendering does not prove login or live policy
behavior. After an authorized deployment, test the OIDC round trip, member and
non-member access, session expiry, backend isolation, and plugin readiness.

Grafana auth reference:
https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/generic-oauth/

Default error rows contain only timestamps, workload and trace metadata. Raw
messages are deliberately omitted because historical and dependency logs have
not been proven safe for team-wide display.
