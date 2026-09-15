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

Concierge runs `gpt-5.6-luna` with `low` reasoning, the lowest level accepted by
CLIProxy. The startup patch `app/config/concierge-effort.php` adds the parameter
that its OpenAI-compatible adapter otherwise omits. Recheck this patch when
updating Concierge. Enrico receives server-care tools, without user or role
administration tools.

## Minecraft public addresses

The custom plugin source and relay service are in
`integrations/pelican-forwarder`. The installed plugin is persisted on the
panel PVC as `plugins/davidapps-forwarder`. When updating it, preserve the
installed `plugin.json` metadata; copy code files without replacing that file.
After changing plugin registration, run `php artisan optimize:clear`, restart
PHP-FPM, and restart the queue worker. A fresh installation uses
`php artisan p:plugin:install davidapps-forwarder`.

The path is public TCP 25565 on `mc-forward.davidapps.dev` (79.76.102.151),
through `mc-router` on `ubuntu@mc-forward.davidapps.dev`, over WireGuard to
`192.168.100.163:<primary allocation port>`. This router speaks Minecraft Java;
Hytale and Bedrock are excluded. Eligible eggs have both the `minecraft` tag
and the `java_version` feature, on node 1.

The minute scheduler reconciles server creation, allocation changes, and
server deletion. Existing addresses remain `im.gurt.ing` and `mc.anaxax.tv`.
New servers receive `<uuid_short>.mc-forward.davidapps.dev`. A DNS-only wildcard
CNAME for `*.mc-forward.davidapps.dev` targets `mc-forward.davidapps.dev` in
Cloudflare. Its record ID is `e091960563cc3c477ef4db6976182048`, in zone
`2b2e1259b957d17f81562bd8fb410e0d`. ExternalDNS does not manage this zone here.

The **Public address** server page shows the join hostname, last provisioning
result, DNS status, and CNAME instructions. The owner or a root administrator
can change the hostname after adding the displayed `_pelican.<new-hostname>`
TXT proof. A unique hostname constraint and relay ownership checks prevent
cross-server takeover. Subusers can read the page but cannot change the domain.
A route/DNS check does not claim the game is running.

On the relay, `/root/mc-router/docker-compose.yml` pins the existing router
image digest. `/root/mc-router/data/routes.json` stores routes and owner UUIDs.
The router mounts that directory read-only and reloads with SIGHUP. The Python
service `mc-forwarder` writes the JSON atomically, serializes changes, and only
accepts backend ports 1024–65535 on `192.168.100.163`. It listens on WireGuard
`192.168.2.5:8091`, authenticating with `/etc/mc-forwarder.env`. The matching
panel Secret is SOPS-encrypted in `app/forwarder-secret.sops.yaml`. The router's
own unauthenticated API is bound only to host loopback `127.0.0.1:8092`.

Back up `routes.json`, the compose file, service script/unit and root-only token
file, plus the panel PostgreSQL database. The pre-change compose backup is in
`/var/backups/mc-router-20260915`. Restoring only the old compose returns the
original two environment mappings but disables automatic provisioning.

The tests in `integrations/pelican-forwarder/tests` cover API authentication,
backend restrictions, hostname ownership, transactional server lifecycle,
allocation changes, DNS, and user access. `wireguard-path.py` creates a temporary
route and a bounded listener on port 25599 to check the complete public path;
it leaves game containers stopped. Tests must run against this deployment,
with port 25599 free, and create no retained test servers.

## Minecraft settings editor

Minecraft Server Config 0.2.0 is installed from the Pelican Hub distribution,
with the MIT source retained in `integrations/minecraft-config`. The local
patch rechecks owner access on mount and save, and treats only a genuine 404
as a missing settings/whitelist/Code of Conduct file. Connection failures and
invalid whitelist JSON propagate rather than being treated as empty data.
The plugin is owner-only, matching its upstream policy. No existing game
settings or whitelist entries were changed during installation.

## Per-account appearance

The custom `davidapps-appearance` plugin lives in
`integrations/pelican-appearance`. The user menu's Appearance action selects
Catppuccin Mocha, Hairline, Nord, or Pelican default. Preferences are saved in
`davidapps_theme_preferences` by authenticated user ID. Other users' preferences
cannot be supplied to the save operation. Hairline is the fallback; David's
initial selection is Catppuccin Mocha.

Keep the three vendor theme plugins installed but disabled globally. Appearance
applies exactly one theme for the current account when Filament serves a page.
Hairline's provider is invoked only for Hairline users, including its console
widget and server-card override. Catppuccin Mocha forces dark mode; the other
choices retain Pelican's light/dark controls. All Vite theme entries are built
at container startup, including disabled theme plugins.

Catppuccin Mocha 1.0.0 comes from Pelican Hub download 166. Minecraft Server
Config 0.2.0 comes from download 216. Preserve plugin metadata when copying
updates into the persistent plugin directory. Reapply the Minecraft read-error
patch after upstream updates, and verify the Appearance integration when
updating vendor themes.
