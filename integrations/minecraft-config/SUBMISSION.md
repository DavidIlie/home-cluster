# Submission Information

**Name:** Minecraft Server Config

**Plugin ID:** `minecraft-config`

**Author:** N3rdMade

**Version:** 0.2.0

**Category:** Plugin

**Panels:** Server

**Short description:** Adds an all-in-one Minecraft configuration page to Pelican for `server.properties`, whitelist management, and editable custom/modpack-specific settings.

## Summary

Minecraft Server Config adds a tabbed configuration page directly to the Pelican server sidebar. It is intended to make day-to-day Minecraft server configuration possible without opening and manually editing configuration files.

The plugin reads the current server settings, presents common properties as toggles, dropdowns, validated inputs, and grouped sections, and keeps unrecognized or modpack-specific properties available through the Advanced tab.

Version 0.2.0 also adds full whitelist editing through `whitelist.json`, including username-based additions, UUID preservation, online/offline mode UUID handling, and live whitelist reloads where possible.

## Tested use case

The plugin has been used on a modded Minecraft server under Pelican with Forge and standard `server.properties` / `whitelist.json` files.

## Installation package

Package the plugin as `minecraft-config-v0.2.0.zip` with a `minecraft-config/` root directory matching the plugin ID, then import it through Pelican's plugin importer.

## License

MIT
