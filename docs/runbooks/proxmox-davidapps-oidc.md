# Proxmox Nucleus: DavidApps OpenID realm

Kubernetes only publishes `https://nucleus.davidhome.ro`; the OpenID realm is
configured on the Proxmox appliance. Do not put an ingress authentication
boundary around Proxmox: API tokens, noVNC/SPICE, websockets, and direct
`:8006` recovery must retain Proxmox authentication.

Keep `root@pam`, the built-in `pve` realm, and direct LAN access throughout the
canary.

## Compatibility preflight

On Nucleus, record `pveversion -v` before making a realm change. Proxmox VE 9's
Trixie OpenID stack uses `proxmox-openid` 1.x with `openidconnect` 4: it sends
PKCE S256 and accepts EdDSA with an Ed25519/OKP JWKS key. If Nucleus reports an
older or locally replaced OpenID stack, stop and test its algorithm support
before creating the client.

Also confirm both discovery and JWKS are reachable from the appliance:

```text
https://id.davidapps.dev/.well-known/openid-configuration
https://id.davidapps.dev/api/auth/jwks
```

Do not disable TLS verification.

## Provision the client

Create a dedicated OIDC-mode DavidApps application:

- name: `Proxmox Nucleus`
- hostname: `nucleus.davidhome.ro`
- exact redirect URI: `https://nucleus.davidhome.ro`
- signup policy: `closed`
- compatibility: `standard`

The client is confidential, requires PKCE S256, and receives a pairwise
subject for this host. Enter the one-time client key directly into the Proxmox
realm form; do not place it in GitOps, a shell argument, or command history.

## Create the realm

In **Datacenter → Permissions → Realms → Add → OpenID Connect Server**, set:

| Field | Value |
| --- | --- |
| Realm | `davidapps` |
| Issuer URL | `https://id.davidapps.dev` |
| Client ID | dedicated Nucleus client ID |
| Client Key | one-time Nucleus client secret |
| Username Claim | `subject` |
| Scopes | `email profile` |
| Autocreate Users | enabled |
| Query userinfo endpoint | enabled |
| Verify TLS certificate | enabled |
| Default realm | disabled during canary |
| Groups Claim / Autocreate Groups | empty / disabled |

Proxmox automatically includes the `openid` scope. `subject` maps DavidApps
pairwise `sub` to an opaque `<subject>@davidapps` user. Do not use email as the
durable username and do not map administrator access from an identity claim.

Autocreation is safe only with the DavidApps application grant in front of it.
After the first successful login, place the created Proxmox user in an
explicit local group and attach the minimum ACL role it needs. A granted friend
can therefore manage only selected VMs or pools without gaining access to the
rest of Nucleus.

## Validate and roll back

1. Open a private browser at `https://nucleus.davidhome.ro`, select the
   `davidapps` realm, and sign in with a granted account.
2. Confirm the request uses PKCE S256 and the returned account is the expected
   opaque subject in the `davidapps` realm.
3. Before assigning an ACL, confirm the new user has no administrative access.
4. Assign a minimal local group/ACL and verify only those resources appear.
5. Confirm an ungranted DavidApps account is rejected.
6. Test console websocket, an existing API token, and the ingress hostname.
7. Sign in through direct `https://<nucleus-lan-ip>:8006` as `root@pam`.

If the new realm fails, keep using `pam`/`pve` and remove or disable only the
`davidapps` realm. The existing users, ACLs, API tokens, and direct recovery
path are independent of it.
