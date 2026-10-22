# Funnelwise

Local marketing analytics for your brand, inside Claude. Funnelwise connects your website and
social accounts (Google Analytics 4, Search Console, YouTube, Instagram, Facebook, TikTok, Spotify),
keeps every report and the numbers behind it in a **brand folder on your computer**, and ships
ready-made skills:

| Skill | What you get |
|---|---|
| `media-kit` | A sponsor-facing media kit or one-page pitch built from your real reach and engagement |
| `seo-opportunities` | A prioritised list of page changes from Search Console: queries to push into the top 3, titles to rewrite, pages competing with each other, indexing problems |
| `content-performance` | Which videos and posts work (age-fair, against your own channel median), the patterns behind them, first changes to make |
| `onboarding`, `start`, `connection-check` | Set up a brand, see what you can do, check every connection |

Ask for anything else too: *"make a one-pager for a tyre brand in Bulgarian"*, *"compare this
month with July"*. Reports reuse the saved data.

**Read-only and local.** Funnelwise's servers can only read. A hook blocks posting, replying,
deleting and messaging tools of other connectors too. Each connector is pinned to your brand's own
account from `brand.yaml`. Credentials stay on your computer; nothing is sent to us.

> Status: **0.1.0, pilot**. Built for Claude Desktop (Cowork tasks) on macOS and for Claude Code.
> See `docs/spikes/` for what is verified and what isn't yet.

## Requirements

- **Claude Desktop** (macOS, Cowork tasks) or **Claude Code**.
- **Python 3.9+** as `python3`. Preinstalled on macOS; on a new Mac the first `python3` run may ask
  to install the Command Line Tools (or run `xcode-select --install` once). No packages to install.
- **`openssl`** for the Google key (preinstalled on macOS and Linux).
- Nothing else: no `uv`, Node, `git` or pip packages. PyYAML, Jinja2 and MarkupSafe are vendored.
- Windows is not supported yet.
- Every platform uses the brand's own credentials on Funnelwise's local servers: no third-party
  data service in between. See "How connecting works" below.
- Not yet tested on a completely clean machine; the pilot kit in `docs/pilot/` covers that check.

## Install

1. Install the plugin from GitHub:
   - **Claude Desktop (Mac):** Claude menu → **Settings** → **Plugins** → **Add** → add marketplace →
     enter `trepechov/funnelwise` → find **Funnelwise** → **Install**, and check it is switched on.
   - **Claude Code:**
     ```bash
     claude plugin marketplace add trepechov/funnelwise
     claude plugin install funnelwise@funnelwise
     ```
     (or inside a session: `/plugin marketplace add trepechov/funnelwise`, then `/plugin install funnelwise@funnelwise`).
2. Open a **new** Cowork task (or a Claude Code session) in an empty folder, or in the folder you
   want for the brand.
3. Say **"Set up my brand"** (or run `/funnelwise:onboarding`). The setup asks for the brand name,
   language and your goal, then connects each platform one at a time, and you do every sign-in yourself:
   Google key for GA4 + Search Console, YouTube sign-in, one Meta token for Instagram and Facebook,
   TikTok sign-in, and the Spotify app values. Secrets go into files Funnelwise opens in your text
   editor, never into the chat. Each connection is tested live straight away.
   Skip any platform and come back to it later with *"connect TikTok"*.
4. Check everything at any time with *"check my connections"* (`connection-check`).

Updating: `claude plugin marketplace update funnelwise`, then restart the session (Desktop: Settings →
Plugins shows the update).

## How connecting works

| Platform | Easiest path | Limits to know |
|---|---|---|
| GA4 + Search Console | One Google service-account key (`reference/connector-guides/google.md`) | — |
| YouTube | Own Google sign-in client + one sign-in by the channel owner/manager (`youtube.md`) | Publish the Google app ("In production") or the sign-in ends after 7 days |
| Instagram, Facebook | One Meta System User token, never expires (`meta.md`) | Instagram must be a Business/Creator account linked to the Page |
| TikTok | Own TikTok app in Sandbox + one sign-in, no terminal | Display API: profile and per-video totals only |
| Spotify | Own Spotify app (2 values) | No listener or stream numbers exist in any Spotify API |

## The brand folder

```
Funnelwise – <Brand>/
├── brand.yaml     name, report language, colours, one account ID per platform, competitors, sponsors
├── reports/       <topic>-<YYYY-MM>.md / .html
├── data/          <topic>-<YYYY-MM>.json: the numbers behind each report
└── notes/         profile.md (your role and goal) and brand facts
```

Credentials live in the brand folder's hidden `.credentials/` (folder 700, files 600, git-ignored),
or in `~/.funnelwise/credentials/<brand>/` when the brand folder is synced to a cloud drive (iCloud
Desktop & Documents, Dropbox, Google Drive, OneDrive), so keys never leave the computer.
`fw_prepare_credentials` writes each file with `<paste …>` placeholders for the user to fill in a
text editor; `fw_connection_status` says which fields are still missing without showing values,
and a hook stops Claude from opening, searching or editing credential files. Example: `templates/brand.example.yaml`; schema:
`schemas/brand.schema.json`; a demo brand with fabricated data: `examples/demo-brand/`.

### Output contract

Every report skill saves `data/<topic>-<YYYY-MM>.json`:
`{topic, period: {from, to}, generated_at, brand, language, metrics: {<metrics.yaml id>: number|null},
source, caveats[], extra}`, plus the report in `reports/`, and diffs against the previous
snapshot of the same topic (`fw_diff_snapshot`). KPI definitions: `reference/metrics.yaml`.

## Repository layout

| Path | Contents |
|---|---|
| `.claude-plugin/` | `plugin.json`, `marketplace.json` |
| `.mcp.json` | The 5 own MCP servers |
| `servers/` | `core.py` (brand folder, credentials, snapshots, reports, catalog), `ga4.py`, `search_console.py`, `spotify.py`, `tiktok.py`, `youtube.py`, `instagram.py`, `facebook.py`; `lib/` shared code; `_vendor/` PyYAML, Jinja2, MarkupSafe |
| `hooks/` | `session_start.py` (brand scope summary), `write_guard.py` (read-only + scope guard), `secret_guard.py` (keeps Claude out of credential files) |
| `skills/` | The six skills |
| `reference/` | `metrics.yaml`, `skill-catalog.yaml`, `sources.md`, `connector-guides/`, `connector-gotchas.md`, `report-templates/` |
| `docs/spikes/` | Phase 0 findings; `docs/pilot/` the pilot kit |
| `tests/`, `dev/` | Test suite; `smoke.py` (MCP handshake + optional live calls), `package.sh` |
| `CLAUDE.md` | Rules for working on this repo with Claude Code (not packaged, not loaded by the plugin) |

## Development

```bash
/usr/bin/python3 -m venv .venv && .venv/bin/pip install pytest jsonschema   # once; /usr/bin/python3 is the oldest supported (3.9)
.venv/bin/pytest                                                               # tests
/usr/bin/python3 dev/smoke.py                                                  # every server starts and lists tools
FUNNELWISE_BRAND_DIR=/path/to/test-brand /usr/bin/python3 dev/smoke.py --live  # one real read call per own server
claude --plugin-dir .                                                          # try a local checkout in Claude Code
dev/package.sh                                                                 # dist/funnelwise-<version>.plugin
```

Opening this repo itself in Claude Code also loads its `.mcp.json` as project servers; they fail
there because `${CLAUDE_PLUGIN_ROOT}` is only set for an installed plugin. Use `--plugin-dir` instead.

Rules the tests enforce: servers stay standard-library Python 3.9; every skill in the catalog has a
`SKILL.md` and names only real tools and files; the repo contains no customer identifiers or
secrets; no top-level `bin/` (it blocks installation in Cowork).

## Licence

Not decided yet (plan Q2). Until then: all rights reserved, see `LICENSE`. Third-party code:
`THIRD_PARTY_NOTICES.md`.
