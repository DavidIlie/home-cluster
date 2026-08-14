# Portainer: DavidApps OAuth

Portainer stores external-authentication settings in its own database, not in
GitOps. The home-cluster change first converts the Portainer Service from the
chart's default `NodePort` to `ClusterIP`, so the internal ingress is the only
published HTTP path. This does not alter Portainer Agent connections.

Do not enable OAuth until the ClusterIP change is rendered and deployed. Keep
the initial Portainer administrator: Portainer allows that one account to use
internal authentication alongside external auth.

## Provision the client

Create a dedicated OIDC-mode DavidApps application:

- name: `Portainer home`
- hostname: `portainer.davidhome.ro`
- exact redirect URI: `https://portainer.davidhome.ro`
- signup policy: `closed`
- compatibility: `legacy_confidential`

Portainer Custom OAuth does not send PKCE. `legacy_confidential` is the narrow
DavidApps exception for an older confidential server client: authorization
code only, no refresh or client-credentials grant, and only `openid profile
email`. Do not provision Portainer as a standard client and do not reuse this
exception for applications that support PKCE.

Enter the one-time secret directly into Portainer. It belongs in the encrypted
Portainer database/backup, not a Kubernetes Secret or this public repository.

## Configure Portainer

While signed in as the initial administrator, open **Settings →
Authentication**, select **OAuth**, choose **Custom**, and enter:

| Field | Value |
| --- | --- |
| Client ID | dedicated Portainer client ID |
| Client secret | one-time Portainer client secret |
| Authorization URL | `https://id.davidapps.dev/api/auth/oauth2/authorize` |
| Access token URL | `https://id.davidapps.dev/api/auth/oauth2/token` |
| Resource URL | `https://id.davidapps.dev/api/auth/oauth2/userinfo` |
| Redirect URL | `https://portainer.davidhome.ro` |
| Logout URL | `https://id.davidapps.dev/api/auth/oauth2/end-session` |
| User identifier | `sub` |
| Scopes | `openid profile email` |
| Auth Style | credentials in the authorization header |

Enable **Use SSO** and **Automatic user provisioning**. Leave **Hide internal
authentication prompt** off. Leave automatic team membership and automatic
administrator assignment off because DavidApps does not issue Portainer team
claims. Grant app admission in DavidApps, then assign Portainer environment and
team permissions locally.

The identifier must remain `sub`. DavidApps subjects are pairwise and opaque;
email is display/contact data, not the durable Portainer identity key.

## Validate and roll back

1. Confirm the rendered Service type is `ClusterIP` and no Portainer NodePort
   remains.
2. In a private window, sign in as a granted account and confirm Portainer
   creates a non-admin user with no unintended environment access.
3. Confirm an ungranted DavidApps account is rejected before provisioning.
4. Grant the new Portainer user only the intended environments or teams.
5. Confirm the initial administrator can still use internal authentication.
6. Confirm the home and UK Portainer Agents remain connected.

If the OAuth round trip fails, return to the initial administrator session and
select internal authentication or correct the custom provider settings. Do not
hide the internal prompt until recovery has been tested from a second browser.
