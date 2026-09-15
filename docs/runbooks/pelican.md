# Pelican operations

The panel runs at `https://panel.davidapps.dev` in the `default` namespace.
Wings runs as a systemd service on `192.168.100.163`; its public API is
`https://pelican.davidhome.ro`. An unauthenticated API request returns 401.

## Storage and upgrades

The `pelican` PVC holds `/pelican-data`, including `.env`, uploads, and plugins.
The same PVC's `plugins` directory is mounted at `/var/www/html/plugins` because
the panel image does not link that directory into its data volume. The active
database is PostgreSQL database `pelican` on `postgres17`, not the legacy SQLite
file in the PVC. Back up PostgreSQL separately from VolSync.

Before upgrading, save a PostgreSQL custom-format dump and an archive of
`/pelican-data`. On the Wings host, back up `/var/lib/pelican`, `/etc/pelican`,
the service unit, and the Wings binary. Preserve the panel's APP_KEY. Never
regenerate it during an upgrade: provider credentials in PostgreSQL need it.

The HelmRelease uses `Recreate` so different panel versions do not run against
the same database during migrations. Its image is pinned by tag and digest.
The startup script installs the selected plugins' PHP dependencies and rebuilds
theme assets before invoking the image entrypoint. Startup therefore requires
package-registry access and can take several minutes. When adding a plugin
with PHP dependencies, update `app/config/start.sh` and test a new pod.

## DavidApps login

The provider ID is `davidapps`, the issuer is `https://id.davidapps.dev`, and
the callback is `https://panel.davidapps.dev/auth/oauth/callback/davidapps`.
PKCE and JWT verification are enabled. New-account creation is disabled;
verified email links returning users to their existing Pelican accounts.
Password login remains available as a recovery path.

`app/config/GenericOIDCProvider.php` adds issuer, audience, authorized-party,
subject, and verified-email checks to the official generic OIDC provider.
It is mounted read-only over the plugin's provider class. Keep this overlay
when updating the plugin, and compare it with upstream changes. An updater
that replaces this mounted file must be handled through GitOps instead.

Credentials are encrypted by Pelican in PostgreSQL. Do not place them in
ConfigMaps or runbooks. DavidApps grants control panel admission; Pelican's
existing account roles and server ownership control access inside the panel.
Wings itself continues to use Pelican's node tokens and SFTP authentication.

## Plugins

- Generic OIDC Providers 1.2.0 and Player Counter 1.1.0 come from
  `pelican/plugins` commit `75e9f623d6c498b2a6ab6cecbdaf1fe3922104d7`.
- Nord 1.0.0 comes from the same commit. It is installed but disabled.
- Hairline 0.1.1 is the active theme, from `WisdomIT/pelican-hairline`
  commit `b7cf5f4e469d722762ceba2518c5f8f951c15e86`.
- Concierge 1.7.1 comes from `WisdomIT/pelican-concierge`
  commit `89b9211e1013222562965d8b9236db7ca1496db9`.

Enable only one of Hairline and Nord at a time in Admin → Plugins. Both support
light and dark modes. Theme assets are regenerated at startup.

Minecraft Player Counter uses the node's routable LAN allocation addresses
rather than `0.0.0.0`, retaining the existing aliases and ports. Its ping
fallback works without modifying game files. Stopped servers have no live
player count. Hytale counting additionally requires the game-side Source Query
plugin; it is not installed by this configuration.

Concierge uses the existing in-cluster CLIProxy OpenAI-compatible endpoint.
Its model credential is stored in Pelican's encrypted plugin settings. Keep
its confirmation cards enabled and preserve existing user permissions.
