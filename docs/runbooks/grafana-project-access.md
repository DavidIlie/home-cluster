# Grafana project access from a DavidApps prompt

This runbook lets an agent turn a natural-language request such as

> give the Bostan team Editor on the Bostan Analytics folder, and read-only
> on the Ops folder

into applied Grafana access, with DavidApps (`id.davidapps.dev`) as the
identity authority and audit trail. No human clicks in Grafana.

DavidApps is never bypassed: a person reaches Grafana only through a DavidApps
grant, and their org-wide Grafana role is minted from DavidApps token claims.
This runbook adds the second, finer layer — per-project folders scoped to
DavidApps groups — on top of that.

## Two layers of access

| Layer | Question it answers | Where it is decided | How it is applied |
| --- | --- | --- | --- |
| Org role | Can you sign in, and are you Viewer / Editor / Admin org-wide? | DavidApps grant + `role_attribute_path` in `grafana` HelmRelease | Automatically on every SSO login |
| Folder RBAC | What can you do inside a specific project folder? | DavidApps group grant (this runbook) | Imperatively via Grafana HTTP API + this runbook |

Layer 1 already ships in
`kubernetes/apps/observability/grafana/app/helmrelease.yaml`. The claim shape
comes from `apps/web/src/server/platform-idp/oidc-claims.ts` in
`davidapps-auth`:

- `o.rol` — org role: `owner | admin | member`
- `app_role` — app role: `visitor | member | reader | writer | admin`

The mapping (JMESPath) is:

```
o.rol == 'owner' && 'GrafanaAdmin'
  || app_role == 'admin' && 'Admin'
  || contains(['writer','reader'], app_role) && 'Editor'
  || 'Viewer'
```

Keep a project team at the **lowest** org-wide role (`member` → Viewer) and give
it elevated access **only inside its folders** through Layer 2. If you instead
grant `reader`/`writer`, the team becomes Editor across the whole instance,
which defeats project isolation.

## Design decision (why this blend)

- **Org role via `role_attribute_path`** works today with the existing claims —
  no DavidApps change, no new claim, and it re-syncs on every login.
- **Folder RBAC via the Grafana API** is imperative because Grafana has no
  concept of "folder permission from an OIDC claim." Folders, teams, and folder
  permissions are Grafana-native objects the agent actuates.
- **DavidApps groups are the unit of project access.** One DavidApps group maps
  to one Grafana team; the team gets a permission level on the project folder.
- Grafana **team membership** is the one piece that is not yet declarative (see
  Gaps). Until a `groups` claim exists, this runbook reconciles membership
  imperatively.

## Prerequisites

- Grafana admin credentials (basic auth is enabled as break-glass):

  ```sh
  cd ~/dev/home-cluster
  GU=$(KUBECONFIG=./kubeconfig kubectl get secret grafana-admin-secret -n observability -o jsonpath='{.data.admin-user}' | base64 -d)
  GP=$(KUBECONFIG=./kubeconfig kubectl get secret grafana-admin-secret -n observability -o jsonpath='{.data.admin-password}' | base64 -d)
  B="https://monitoring.davidapps.dev"
  ```

  Never echo `$GP`, put it in a URL, or paste it into a prompt. Prefer a
  short-lived Grafana service-account token over the admin password for
  automation:

  ```sh
  TOKEN=$(curl -s -u "$GU:$GP" -H 'Content-Type: application/json' -X POST \
    "$B/api/serviceaccounts" -d '{"name":"sa-project-access","role":"Admin"}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  # then POST /api/serviceaccounts/$TOKEN/tokens and use: -H "Authorization: Bearer <token>"
  ```

- DavidApps MCP (`davidapps-mcp`) configured with an API key that has at least
  `apps:write` (for `grant_access`) and, for the audit step, `audit:read`.

## The recipe

Parameters for one request:

- `GROUP` — DavidApps group name, e.g. `Bostan Enterprise Employees`
- `FOLDER_TITLE` — human folder title, e.g. `Bostan Analytics`
- `FOLDER_UID` — stable slug, e.g. `bostan-analytics` (lowercase, hyphens)
- `LEVEL` — `view | edit | admin` (Grafana permission 1 / 2 / 4)

### Step 1 — DavidApps: record the intent (authoritative + audited)

Grant the group access to the `grafana` app. Keep the org role at `member`
(Viewer baseline) and encode the folder intent in `enabledModules` so the grant
is self-describing and shows up in `read_audit`. Module tokens must match
`^[a-z][a-z0-9_]*$` (≤32 chars), so use `graf_<folder_uid_underscored>_<lvl>`:

MCP call:

```
grant_access(
  appId       = "slug:grafana",
  subjectType = "group",
  subjectId   = "name:Bostan Enterprise Employees",
  effect      = "allow",
  role        = "member",                       # -> Grafana Viewer org-wide
  enabledModules = ["graf_bostan_analytics_edit"]
)
```

Verify the grant resolves for a member:

```
resolve_access(appId="slug:grafana", userId="email:maximilian@bostanenterprise.com")
# decision=allowed, role=member, reasons[].kind=group
```

> `enabledModules` is recorded on the grant and is visible through
> `read_audit`; it is **not** emitted into the Grafana OIDC token today (the
> token carries only `o`, `app_role`, and profile claims). It is the auditable
> declaration of intent; Grafana access is actuated in Steps 2-4.

### Step 2 — Resolve the group's people (DavidApps → emails)

The MCP surface does not currently list group members directly, so read them
from the identity DB (read-only):

```sh
P() { KUBECONFIG=/Users/david/dev/davidapps-cluster/kubeconfig \
  kubectl exec -n auth davidapps-auth-postgres-1 -c postgres -- \
  psql -U postgres -d davidapps_auth -tAc "$1"; }

# group id by name (org scoped to the grafana app's org)
GID=$(P "SELECT t.id FROM team t JOIN application a ON a.org_id=t.organization_id
         WHERE a.slug='grafana' AND t.name='Bostan Enterprise Employees';")

# member emails
P "SELECT u.email FROM team_member tm JOIN \"user\" u ON u.id=tm.user_id
   WHERE tm.team_id='$GID';"
```

Carry both the DavidApps group id (`$GID`) and the member emails forward.

### Step 3 — Grafana: ensure folder, team, and folder permission

```sh
# 3a. folder (idempotent: 409/"already exists" is fine)
curl -s "${AUTH[@]}" -H 'Content-Type: application/json' -X POST "$B/api/folders" \
  -d '{"uid":"bostan-analytics","title":"Bostan Analytics"}'

# 3b. team, keyed by the DavidApps group id in the email field for traceability
TID=$(curl -s "${AUTH[@]}" "$B/api/teams/search?name=Bostan%20Enterprise%20Employees" \
  | python3 -c 'import sys,json;t=json.load(sys.stdin).get("teams") or [];print(t[0]["id"] if t else "")')
[ -z "$TID" ] && TID=$(curl -s "${AUTH[@]}" -H 'Content-Type: application/json' -X POST "$B/api/teams" \
  -d "{\"name\":\"Bostan Enterprise Employees\",\"email\":\"$GID@groups.davidapps\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["teamId"])')

# 3c. folder permission (1=View 2=Edit 4=Admin). This POST REPLACES the folder's
#     permission set, which removes the default org-role access and isolates the
#     folder to this team (+ Grafana admins). Include every team/role you want.
curl -s "${AUTH[@]}" -H 'Content-Type: application/json' \
  -X POST "$B/api/folders/bostan-analytics/permissions" \
  -d "{\"items\":[{\"teamId\":$TID,\"permission\":2}]}"
```

`AUTH` is `(-u "$GU:$GP")` or `(-H "Authorization: Bearer <sa-token>")`.

For a second folder at a different level (e.g. read-only on Ops), repeat 3a/3c
with that folder's uid and `permission:1`, reusing the same `$TID`.

### Step 4 — Reconcile team membership

A DavidApps person becomes a Grafana user only after their first SSO login.
For each member email, look up the OAuth-provisioned Grafana user and add it to
the team; users who have not logged in yet are skipped and picked up on a later
reconcile (or their first login, once the `groups` claim lands — see Gaps).

```sh
for EMAIL in $(P "SELECT u.email FROM team_member tm JOIN \"user\" u ON u.id=tm.user_id WHERE tm.team_id='$GID';"); do
  UID=$(curl -s "${AUTH[@]}" "$B/api/users/lookup?loginOrEmail=$EMAIL" \
    | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("id") or "")')
  [ -n "$UID" ] && curl -s "${AUTH[@]}" -H 'Content-Type: application/json' \
    -X POST "$B/api/teams/$TID/members" -d "{\"userId\":$UID}" >/dev/null \
    && echo "added $EMAIL" || echo "pending first login: $EMAIL"
done
```

Only ever add OAuth-provisioned accounts to a project team. Do not add the
local `admin`/`david` recovery account; Grafana auto-adds the team creator, so
remove user id `1` if it appears (`DELETE /api/teams/$TID/members/1`).

## Verify

```sh
# folder is isolated to the team (should show only the team + inherited admin)
curl -s "${AUTH[@]}" "$B/api/folders/bostan-analytics/permissions"
# team membership reflects logged-in group members
curl -s "${AUTH[@]}" "$B/api/teams/$TID/members"
```

A correct end state:

- `resolve_access` → `allowed`, `role=member` for each group member (Layer 1).
- Folder `bostan-analytics` permissions list shows **only** the team at `Edit`
  (no default Viewer/Editor role rows) → the folder is private to the project.
- The team contains the OAuth logins of members who have signed in.

On a member's next login, `role_attribute_path` mints Viewer org-wide, and the
team grants Edit inside Bostan Analytics — nowhere else.

## Audit and visibility

- **DavidApps side:** every `grant_access` is recorded. Read it with
  `read_audit(appId="slug:grafana")` (needs an `audit:read` API key). The
  `enabledModules` token (`graf_<folder>_<lvl>`) is the human-readable
  declaration of what folder access the grant was meant to produce.
- **Grafana side:** enable/consult Grafana's own audit logs for folder
  permission and team-membership changes. Team `email` is set to
  `<davidapps-group-id>@groups.davidapps`, so a Grafana team is always
  traceable back to its DavidApps group.

To revoke: `grant_access(..., effect="deny")` or remove the grant in DavidApps
(cuts login/role), then delete the Grafana folder permission row and/or team
membership. Layer 1 revocation alone drops the user to no-access on next token
mint.

## Gaps / upgrade path

1. **Team membership is not declarative.** Grafana teams are populated only by
   this reconcile loop, and only for users who have already logged in. The clean
   fix is a bounded `groups` claim in DavidApps + `groups_attribute_path` in the
   Grafana HelmRelease, which makes Grafana create/sync team membership on every
   login. A precise spec for that DavidApps change is proposed separately (file
   `apps/web/src/server/platform-idp/oidc-claims.ts`); it is **not** enabled
   here yet. When it lands, add to the HelmRelease under `auth.generic_oauth`:

   ```yaml
   groups_attribute_path: groups   # array of DavidApps group ids
   team_ids_attribute_path: ...    # optional, if mapping ids directly
   ```

   and drop Step 4's reconcile loop.

2. **`enabledModules` does not reach Grafana.** It is intent + audit only. The
   actuator (this runbook) is the bridge. If the token later carried folder
   intent, a sidecar could self-reconcile folders without the DB read in Step 2.
3. **Group-member enumeration uses a DB read**, not MCP. A `list_group_members`
   MCP tool would remove the `kubectl exec` dependency.
4. **Folder permission POST is destructive** (replaces the whole set). Always
   send the complete desired permission list for a folder, or GET-merge-POST.
