# Changelog

## 0.1.0 (2026-10-22, pilot)

First version, built from plan Phases 0–3 plus the Phase 4 pilot kit.

- Brand folder (`brand.yaml`, `reports/`, `data/`, `notes/`) with schema validation; credentials in
  `~/.funnelwise/credentials/<brand>/`.
- Own read-only MCP servers on standard-library Python 3.9: core, GA4, Search Console (with
  `gsc_opportunities`), Spotify, TikTok (terminal-free sign-in). Every server enforces the account
  from `brand.yaml`.
- Launcher for pinned third-party YouTube, Instagram and Facebook servers, with a help stub when
  they can't run.
- Hooks: session scope summary; write guard (read-only + account scope) for all marketing connectors.
- Skills: onboarding, start, connection-check, media-kit, seo-opportunities, content-performance.
- Reference: metrics dictionary, skill catalog with role hints, metric → tool map, connector
  guides, gotchas, report conventions.
- Phase 0 spike notes and the pilot kit.
