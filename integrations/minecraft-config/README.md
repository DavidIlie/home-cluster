# Minecraft Server Config for Pelican

A Pelican Panel plugin that adds a **Minecraft Config** page to the server sidebar, giving server owners a single GUI for editing `server.properties`, managing the whitelist, and accessing custom or modpack-specific properties without manually editing files.

## Features

### Server settings

- General, Gameplay, Whitelist, World, Network, RCON / Query, Performance, Resource Pack, and Advanced tabs
- Toggles for boolean options instead of manually entering `true` / `false`
- Dropdowns for game mode, difficulty, permission levels, and common world types
- Validation for ports, player limits, distances, timeouts, and other numeric values
- RCON password field
- Reads the server's existing `server.properties` values on load
- Preserves existing formatting and comments where possible when saving
- Keeps unknown and modpack-specific properties editable through the Advanced tab

### Whitelist management

- Dedicated Whitelist tab
- Enable or disable the whitelist
- Enable or disable `enforce-whitelist`
- Add and remove players by username
- Reads and writes the existing `whitelist.json`
- Preserves UUIDs for existing entries
- Checks `usercache.json` before looking up a UUID
- Resolves UUIDs for newly added online-mode players
- Generates standard offline-mode UUIDs when Online Mode is disabled
- Attempts to reload and apply whitelist changes immediately when the server is running

### Newer Java Edition settings

- Server Management API settings used by newer Minecraft versions
- TLS and browser-origin controls where those properties exist
- Server Code of Conduct setting
- Editor for `codeofconduct/en_us.txt`

## Compatibility

Designed for modern Minecraft Java Edition servers using Pelican's server panel. The page detects common Minecraft eggs including:

- Vanilla
- Forge
- NeoForge
- Fabric
- Quilt
- Paper
- Purpur
- Spigot
- Bukkit-style servers

Unknown `server.properties` keys remain available in the Advanced tab, so modpack-specific or future properties are not discarded.

The plugin is currently owner-only.

## Installation

Import the packaged release ZIP from:

**Pelican Admin -> Plugins -> Import**

Then install **Minecraft Server Config**, open a Minecraft server, and select **Minecraft Config** from the server sidebar.

The plugin ID is `minecraft-config`, and the install package contains a root folder with the same name as required by Pelican.

## Notes

- Most `server.properties` changes require a Minecraft server restart.
- `server-port` should normally match the Pelican allocation.
- `server-ip` should normally remain blank.
- Changing `level-name` points Minecraft at a different world directory; it does not delete the previous world.
- Whitelist changes are saved to `whitelist.json` and are applied live when possible.
- Operator lists, bans, IP bans, and game rules are stored outside `server.properties` and are not managed in v0.2.0.

## Current scope

| Area | Managed |
| --- | --- |
| `server.properties` | Yes |
| Unknown/modpack-specific properties | Yes |
| `whitelist.json` | Yes |
| `codeofconduct/en_us.txt` | Yes |
| Operators (`ops.json`) | Not yet |
| Player bans (`banned-players.json`) | Not yet |
| IP bans (`banned-ips.json`) | Not yet |
| Game rules stored in the world | Not yet |

## Version history

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT License. See [LICENSE](LICENSE).
