# Home applications: native DavidApps sign-in

This change prepares native OIDC for Grafana, Paperless-ngx, Open WebUI, and
qui. It is not deployable while any OIDC Secret has the annotation
`davidapps.dev/credentials: pending-provisioning`. The encrypted values in
those Secrets are deliberate placeholders, not usable clients.

Each application keeps its existing local login during the canary. Do not add
an ingress authentication boundary to these hosts: the application should own
its local roles, sessions, API keys, and recovery login.

## Dedicated clients

Provision four OIDC applications with `setup_app`. Every application uses
`signupPolicy: closed` and a `standard` confidential client. Grant users access
in DavidApps; a person who merely has a DavidApps account does not gain access.

| Application | Hostname | Exact redirect URI |
| --- | --- | --- |
| Grafana | `monitoring.davidapps.dev` | `https://monitoring.davidapps.dev/login/generic_oauth` |
| Paperless-ngx | `paperless.davidhome.ro` | `https://paperless.davidhome.ro/accounts/oidc/davidapps/login/callback/` |
| Open WebUI | `chat.davidhome.ro` | `https://chat.davidhome.ro/oauth/oidc/callback` |
| qui | `qui.davidhome.ro` | `https://qui.davidhome.ro/api/auth/oidc/callback` |

Use one application and one client per row. Supply the row's URI through
`oidcRedirectUris`; do not reuse a client between hosts. Standard clients use
PKCE S256, `client_secret_basic`, pairwise `sub`, and EdDSA/Ed25519 ID tokens.

Capture each returned client ID and one-time client secret directly into its
encrypted file:

| Application | Encrypted file |
| --- | --- |
| Grafana | `kubernetes/apps/observability/grafana/app/oidc-secret.sops.yaml` |
| Paperless-ngx | `kubernetes/apps/default/paperless/app/oidc-secret.sops.yaml` |
| Open WebUI | `kubernetes/apps/ai/open-webui/app/oidc-secret.sops.yaml` |
| qui | `kubernetes/apps/downloads/qui/app/oidc-secret.sops.yaml` |

Edit with SOPS using the home-cluster age identity. Never decrypt to a tracked
file, paste a secret into a prompt, or put a secret in a shell argument. For
Paperless, replace the client ID and secret inside the encrypted JSON value.
After replacement, change the unencrypted annotation to
`davidapps.dev/credentials: provisioned` and verify there are no remaining
`pending-provisioning` annotations before opening a deployment PR.

## Application behavior

### Grafana

Grafana Generic OAuth requests `openid profile email offline_access`, verifies
the EdDSA ID token against DavidApps JWKS, and uses PKCE S256. The pairwise
`sub` is the login key. A new account starts with Grafana's default Viewer
role; `skip_org_role_sync` preserves later local role changes.

Basic authentication and the login form remain enabled. Keep the existing
admin Secret. Do not enable automatic provider redirect during the canary.

### Paperless-ngx

The unsafe `PAPERLESS_AUTO_LOGIN_USERNAME=admin` setting is removed. The
allauth provider explicitly enables PKCE, uses `sub` as its account ID, and
sends the client secret with HTTP Basic authentication. Regular Paperless
login remains enabled.

Before the first direct DavidApps sign-in, log in as the existing Paperless
administrator, open **My Profile**, and connect the DavidApps provider. This
links the external subject to the existing administrator instead of creating
a second administrator. Later granted users may create minimal, non-admin
Paperless rows through social signup; Paperless continues to own document
permissions and API tokens.

### Open WebUI

Open WebUI uses discovery, explicit PKCE S256, and pairwise `sub`. OAuth
settings stay environment-authoritative. Password authentication and the local
login form remain enabled, automatic redirect stays off, and email-based
account merging stays off.

The existing local administrator is the recovery account. A first OIDC login
does not silently inherit it. Review the new local user's Open WebUI role after
the first login; do not grant administrator through identity claims.

### qui

qui discovers DavidApps from the issuer and automatically adds PKCE S256 when
the provider advertises it. Its exact callback is configured explicitly.
Built-in username/password login stays visible and machine API keys continue
to work.

Before considering removal of built-in login, inspect
`/api/auth/oidc/config` in an authenticated test and confirm the authorization
URL contains both `code_challenge` and `code_challenge_method=S256`.

## Canary and rollback

Roll out one application at a time, beginning with Grafana or qui. For every
host, test:

1. a private-window sign-in by a granted account;
2. refusal of a signed-in DavidApps account without the app grant;
3. a granted friend, if applicable, receiving only the intended local role;
4. logout and a second private-window sign-in;
5. the local recovery administrator;
6. existing API keys, service accounts, mobile clients, or automations.

Do not disable a local login or force OIDC redirect until two independent
private-window sign-ins and the app's machine-client tests pass. Rollback is a
revert of the individual HelmRelease OIDC settings; local accounts and API
credentials remain unchanged.
