# Home Assistant: Sign in with DavidApps

The Romania Home Assistant instance is an appliance at `192.168.30.10`.
Kubernetes only publishes `https://hass.davidhome.ro`; it cannot install a
custom component or edit the appliance's `/config` directory. Complete this
runbook in Home Assistant after provisioning its dedicated DavidApps client.

Do not add ingress authentication annotations. Home Assistant mobile clients,
websockets, webhooks, and API tokens must continue to reach Home Assistant
directly. The built-in Home Assistant username/password provider stays enabled
as the recovery path.

## 1. Provision the dedicated client

The OIDC-mode DavidApps application is provisioned for the single hostname
`hass.davidhome.ro` with:

- callback: `https://hass.davidhome.ro/auth/oidc/callback`
- compatibility: `standard` (PKCE S256 remains required)
- signup policy: `closed`

Its public client ID is `yLE1m6fYPNo3b6YJZrvdiBbqGFQdqy51`. The one-time
client secret is staged in macOS Keychain service
`dev.davidapps.auth.oidc.home-assistant-home`, under that client ID, until the
appliance configuration is complete. Delete that Keychain item after both the
DavidApps login and built-in recovery login are proven.

Use `oidcRedirectUris` when calling `setup_app`; the usual DavidApps callback
paths alone are not the Home Assistant callback. Transfer the staged one-time
client secret directly into the Home Assistant secret store. Do not reuse the UK
Home Assistant client: DavidApps identity is pairwise, one host per client.

Grant the intended people access to this application in DavidApps before they
try to sign in. The Home Assistant component cannot reliably reject a new user
late in its own account-creation flow, so the DavidApps application grant is
the registration boundary.

## 2. Install the component on the appliance

In HACS, install **OpenID Connect/SSO Authentication** from
`christiaangoossens/hass-oidc-auth`. Select release `v1.1.1` or the exact newer
release that has been reviewed before deployment. Release `v1.1.1` requires
Home Assistant 2025.11 or newer.

If HACS is unavailable, download the `v1.1.1` release asset
`hass-oidc-auth.zip`, verify SHA-256
`9ce9e6153f80c781e360b93e097ff7d87d09235430fc48e7a67d97dda5fc3322`,
and extract its contents to `/config/custom_components/auth_oidc/`.

## 3. Configure Home Assistant

Add the one-time secret to `/config/secrets.yaml` without copying it into Git:

```yaml
davidapps_oidc_client_secret: "<value from DavidApps>"
```

Add this block to `/config/configuration.yaml`:

```yaml
auth_oidc:
  client_id: "<Romania Home Assistant client ID>"
  client_secret: !secret davidapps_oidc_client_secret
  discovery_url: "https://id.davidapps.dev/.well-known/openid-configuration"
  display_name: "DavidApps"
  id_token_signing_alg: "EdDSA"
  additional_scopes:
    - email
  claims:
    display_name: name
    username: email
  features:
    automatic_user_linking: false
    automatic_person_creation: true
    disable_rfc7636: false
    include_groups_scope: false
    force_https: true
    default_redirect: false
```

Do not add an `auth_providers` block that removes `homeassistant`. Do not turn
on automatic user linking: matching an OIDC email to an existing local name can
silently inherit that local account's privileges and bypass its MFA.

## 4. Validate and roll out

1. Run Home Assistant's configuration check, then restart Home Assistant.
2. In a private browser window, confirm both **DavidApps** and the alternative
   built-in login are offered; there must be no forced redirect.
3. Sign in as a person who has the DavidApps application grant. Confirm the
   callback returns to `hass.davidhome.ro` and creates a separate, non-admin
   Home Assistant user.
4. From an existing local administrator session, promote that new Home
   Assistant user only if it actually needs administrator rights.
5. Confirm a signed-in DavidApps account without an application grant is
   refused before Home Assistant creates a user.
6. Test the Home Assistant mobile app, a websocket dashboard, an existing
   webhook, and an existing long-lived API token.
7. Confirm the existing local administrator can still sign in directly.

To roll back, remove the `auth_oidc` block and restart Home Assistant. The
built-in provider remains available throughout; removing the custom component
can wait until after the local login has been verified.
