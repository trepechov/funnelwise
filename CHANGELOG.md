# Changelog

## Unreleased

- Own read-only servers for **YouTube** (Data + Analytics API, terminal-free Google sign-in),
  **Instagram** and **Facebook** (one Meta System User token). Metricool removed as a path.
- Google sign-in in **Testing** mode is detected at sign-in (`refresh_token_expires_in`) and on
  expiry (`invalid_grant`), with the "Publish app" fix.
- Credentials: `fw_prepare_credentials` writes files with `<paste …>` placeholders for the user to
  fill in a text editor; new brands keep them in the brand folder's hidden `.credentials/`, or in
  `~/.funnelwise/credentials/<brand>/` when the folder is cloud-synced. A hook blocks Claude's
  file and shell tools from credential folders.
- Onboarding rewritten as 4 numbered steps (brand, channels, about you, connect + first report);
  `brand.channels` records every channel the brand has.

## 0.1.0 (2026-10-22, pilot)

First version, built from plan Phases 0–3 plus the Phase 4 pilot kit.

- Brand folder (`brand.yaml`, `reports/`, `data/`, `notes/`) with schema validation; credentials in
  `~/.funnelwise/credentials/<brand>/`.
- Own read-only MCP servers on standard-library Python 3.9: core, GA4, Search Console (with
  `gsc_opportunities`), Spotify, TikTok (terminal-free sign-in). Every server enforces the account
  from `brand.yaml`.
- Hooks: session scope summary; write guard (read-only + account scope) for all marketing connectors.
- Skills: onboarding, start, connection-check, media-kit, seo-opportunities, content-performance.
- Reference: metrics dictionary, skill catalog with role hints, metric → tool map, connector
  guides, gotchas, report conventions.
- Phase 0 spike notes and the pilot kit.
