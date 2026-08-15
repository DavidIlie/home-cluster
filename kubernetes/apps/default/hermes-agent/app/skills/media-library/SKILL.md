---
name: media-library
description: Manage David's Radarr, Sonarr, Bazarr, and Plex library safely through the live media MCP tools. Use for adding a movie or show, choosing or changing quality profiles, searching or redownloading episodes, repairing or downloading subtitles, checking recent Plex media, or learning the live media configuration.
---

# Media Library

Use observer tools to discover live state and exact IDs. Use action tools only
after David makes the required choice; each action produces its own Discord
approval button.

## Add a movie or show

1. Resolve the exact title using `radarr_lookup_movies` or
   `sonarr_lookup_series`. If results are ambiguous, use `clarify` so Discord
   shows native choice buttons.
2. Query the live quality profiles and root folders every time. Never rely on a
   remembered numeric ID or silently apply a default.
3. Present two to four useful named choices with `clarify` buttons. If there are
   more, summarize the shortlist and allow another named choice.
4. Confirm title/year, profile, root folder, monitoring behavior, and whether to
   search now.
5. Call `radarr_add_movie` or `sonarr_add_series`. David must still press the
   separate approval button.
6. Verify the result with an observer tool before reporting success.

## Quality profile changes

Resolve the exact existing item, fetch current live profiles, show named
`clarify` choices, then call the matching profile action and verify. A learned
preference may guide which choices are shown first, but may never bypass David's
explicit choice for a new movie or show.

## Episodes

- Use `sonarr_episodes` to resolve exact series, season, and episode IDs.
- Use `sonarr_search_episodes` for a missing episode search.
- Before `sonarr_redownload_episode`, warn that the current file is deleted
  before replacement search and the episode may be temporarily fileless. Wait
  for an explicit answer, then the action approval button, and finally verify.

## Subtitles

1. Resolve the exact Radarr movie or Sonarr episode and inspect Bazarr's live
   language profiles.
2. Ask what language is wanted and whether it must be forced or
   hearing-impaired. Use `clarify` buttons for bounded choices.
3. If changing a title's Bazarr profile, show the live profile names first and
   call the matching set-profile action.
4. For a repair/download, call the exact movie or episode subtitle action with
   the chosen language flags. Explain that Bazarr selects the best matching
   available subtitle; do not claim a provider result before verification.
5. Verify after approval and report the exact item and language handled.

## Learning

After a successful workflow, offer to remember a stable preference such as
preferred languages or which profile names David usually considers. Never store
API keys, numeric service IDs, temporary availability, or a quality choice as an
automatic default. Live configuration remains authoritative.
