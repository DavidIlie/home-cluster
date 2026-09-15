# Additional Pelican plugins

Installed 2026-09-15 on panel beta38. `versions.json` records the downloaded
archives. Hub download IDs: Egg Images 159, Player Heatmap 136, Deepfield 273,
Voidwave 230, StarryNight 74. Fluffy 1.0.0 and Neobrutalism 1.0.0 come from
pelican-dev/plugins commit 75e9f623 (the official plugin collection).

The vendor distributions remain on the persistent panel volume rather than
being redistributed here. After extracting an exact pinned archive, apply its
patch from the directory containing the plugin folder with `patch -p1`.
Preserve existing `plugin.json` metadata when copying updates into a live panel.
Do not enable vendor themes globally: the Appearance plugin selects them per
account. Restart the panel after adding theme assets so startup builds them
before serving requests.

`player-heatmap-ll.patch` adds the beta38 settings method and checks Wings power
state before log ingestion and count estimation. `voidwave-theme.patch` requires
authentication on preference writes in addition to session middleware.

Run `tests/heatmap.php` with PHP inside the panel. It uses a database transaction
and mocked Wings responses; all test rows are rolled back. Appearance's separate
test verifies user preference isolation and built Vite assets.
