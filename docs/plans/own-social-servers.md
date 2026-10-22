# Plan: own YouTube, Instagram and Facebook servers

Status: **done** 2026-10-22 (spike in `docs/spikes/0.6-own-social-apis.md`). Metricool removed entirely. Replaces "Metricool is the path for YouTube/Instagram/Facebook"
(provisional Q15) for these three platforms.

## Why

The original single-brand project read YouTube, Instagram and Facebook through three third-party
MCP servers (youtube-studio-mcp, ig-mcp, facebook-mcp-server). They needed `uv`, pinned git
checkouts and `mcp<2`, so they were removed and the platforms moved to Metricool. Relying on a
paid third-party connector was never the intent: Funnelwise should read the brand's own data with
the brand's own credentials, like it already does for GA4, Search Console, TikTok and Spotify.

So we write our own servers, in the same style as `servers/tiktok.py`:

- **Standard-library Python 3.9 only** (`urllib`, `http.server`, `hashlib`, `secrets`), started as
  `python3 servers/<name>.py`. No `uv`, no pip, nothing new in `_vendor/`.
- **Read-only.** No tool posts, replies, deletes or messages. Only read scopes are requested.
- **Scoped to one account.** The ID comes from brand.yaml; any other channel, account or Page is
  refused, and no tool lists "all accounts the token can see".
- **Same credential files as the original project**, so an existing `.credentials/` folder keeps
  working: `client_secret.json` + `token.json` (YouTube), `instagram.json`, `facebook.json`.
- Metricool and Windsor stay as optional `via:` values for brands that already use them.

## Servers and tools

### `servers/youtube.py` (connector `youtube`, scope `channel_id`)

APIs: YouTube Data API v3 and YouTube Analytics API v2. Scopes `youtube.readonly` and
`yt-analytics.readonly`.

| Tool | What it returns |
|---|---|
| `youtube_login_start` / `youtube_login_status` / `youtube_login_finish` | One-time Google sign-in by the channel owner or manager, no terminal (same pattern as TikTok) |
| `youtube_channel` | Title, handle, subscribers, total views, video count, uploads playlist |
| `youtube_list_videos` | Recent uploads (paged): id, title, published, duration, format (long / Short / live) |
| `youtube_get_videos` | Views, likes, comments, duration for up to 50 video IDs of this channel |
| `youtube_analytics` | Analytics report for the channel: views, watch time, average view duration, subscribers gained/lost, by day / video / traffic source / country / age-gender / device, with a date range |

- Sign-in: Google OAuth "Desktop app" client, loopback redirect `http://127.0.0.1:<port>/` with
  PKCE (S256). Refresh via `oauth2.googleapis.com/token`. Lives in a new shared
  `servers/lib/google_oauth.py`; the legacy Search Console OAuth path can reuse it.
- Scope check: after sign-in, confirm the signed-in identity can see the brand's `channel_id`
  (`channels.list?id=` plus an Analytics probe `ids=channel==<id>`). If it can't, say who signed in
  and that a Brand Account Owner/Manager must sign in instead (the known Studio-Editor gotcha).
  Every call passes `id=` / `ids=channel==<channel_id>`; there is no `mine` parameter.
- Public numbers (channel, videos) also work with a plain API key, as a fallback for brands whose
  owner can't sign in yet. Analytics needs the sign-in.

### `servers/instagram.py` (connector `instagram`, scope `username` + `business_account_id`)

API: Instagram Graph API via Facebook Login (Business/Creator account linked to a Page).

| Tool | What it returns |
|---|---|
| `instagram_profile` | Username, followers, follows, media count |
| `instagram_list_media` | Recent posts (paged): id, type (reel / carousel / image), caption start, timestamp, likes, comments, permalink |
| `instagram_media_insights` | Per post: views, reach, saves, shares, total interactions |
| `instagram_account_insights` | Account totals for a date range: reach, views, accounts engaged, interactions, profile visits, follower change |
| `instagram_audience` | Follower demographics: age, gender, country, city |

### `servers/facebook.py` (connector `facebook`, scope `page_id`)

API: Facebook Graph API with a Page access token.

| Tool | What it returns |
|---|---|
| `facebook_page` | Name, followers, likes (fans), link |
| `facebook_list_posts` | Recent posts (paged): id, type, message start, created time, reactions, comments, shares |
| `facebook_post_insights` | Per post: impressions/reach, engaged users, video views where available |
| `facebook_page_insights` | Page totals for a date range (metric list confirmed in the spike, see below) |

### Shared Meta sign-in: `servers/lib/meta_graph.py`

- The brand creates its own Meta developer app (stays in Development mode; no App Review is needed
  when the person signing in has a role on the app), the same "own app" pattern as TikTok.
- Connect without a terminal: the user generates a short-lived user token in Graph API Explorer
  (read permissions only: `instagram_basic`, `instagram_manage_insights`, `pages_show_list`,
  `pages_read_engagement`, `read_insights`) and pastes it once. The server exchanges it for a
  long-lived token (`fb_exchange_token` with app ID/secret), takes the **Page token for the brand's
  Page only** (non-expiring when derived from a long-lived user token), reads the linked
  Instagram business account ID, checks it matches `username`, and stores `facebook.json` and
  `instagram.json` (mode 600). Other Pages the person manages are never stored or shown.
- Shared helpers: Graph version constant, paging, error translation (expired token, missing
  permission, rate limit) into plain next steps.

## Changes outside the servers

| Area | Change |
|---|---|
| `.mcp.json` | Add `youtube`, `instagram`, `facebook` (`python3 ${CLAUDE_PLUGIN_ROOT}/servers/<name>.py`) |
| `lib/workspace.py`, schema | Drop `NO_OWN`; `via: own` requires `channel_id` / `username` / `page_id` again |
| `lib/credentials.py` | `KINDS`: `meta-app` (app_id, app_secret); `NEEDS` for youtube, instagram, facebook; next steps |
| `core.py` | `OWN_PATH` gains the three; a `fw_meta_connect` style tool is not needed if the exchange lives in the servers |
| Write guard hook | Unchanged (our servers have no write tools); keep the `mine: true` block |
| Skills | `onboarding` table: own path first, Metricool as alternative; `connection-check` gets the three cheap calls |
| Guides | Rewrite `connector-guides/youtube.md` and `meta.md` for the own path, with screenshots later (T6) |
| `reference/metrics.yaml` | Map each metric id to the tool and field that fills it |
| Tests | Fake-HTTP tests per server: scope refusals, paging, token refresh, error messages, no write tools listed; schema/validator sync; structure test that every server is in `.mcp.json` |
| `dev/smoke.py --live` | One read call per new server |

## Steps

| # | Step | Size |
|---|---|---|
| 0 | **Spike** with the first customer's existing credentials: confirm the current Instagram metric names (`views` replaced `impressions`), which Page insights metrics still exist after Meta's deprecations, and that Analytics works for a Brand Account manager sign-in. Write `docs/spikes/0.6-own-social-apis.md` | ½ day |
| 1 | `lib/google_oauth.py` (loopback + PKCE + refresh) and `lib/meta_graph.py` (exchange, Page token, paging, errors) with tests | 1 day |
| 2 | `youtube.py` + tests | 1 day |
| 3 | `instagram.py` + `facebook.py` + tests | 1½ days |
| 4 | Wiring: `.mcp.json`, validator/schema, credentials, skills, guides, metrics map | ½ day |
| 5 | Live check on the first customer, compare numbers with the old third-party servers and Metricool (plan 2.6), fix gaps | ½ day |

About 5 working days. Each step ends with the tests passing on Python 3.9.

## Risks and decisions to make

- **Google "Testing" apps expire refresh tokens after 7 days.** The brand's OAuth consent screen
  must be set to *In production* (unverified is fine for the brand's own use; the sign-in shows a
  warning screen once). The guide must say so, or YouTube disconnects every week.
- **Meta token paste passes through the chat.** It is short-lived and exchanged at once; the
  stored long-lived tokens never do. Alternative: a loopback Facebook Login flow like TikTok's,
  if the Meta app's redirect settings allow `localhost` (check in the spike).
- **Meta API churn.** Insights metrics get deprecated often. Keep metric names in one table per
  server so a change is a one-line fix, and let tools return "metric not available" instead of
  failing the whole call.
- **Decision:** keep Metricool as an optional path (recommended: yes, as `via: metricool`, for
  brands that can't create developer apps), or remove it from the onboarding entirely.

## What changed while building (2026-10-22)

- **Metricool removed** as a path (decision above): `via` no longer accepts `metricool`.
- **Meta sign-in:** no token exchange. The spike showed System User tokens never expire, so the
  user creates one and fills it into `meta.json` (one file for both platforms); the Page token is
  derived at run time. No secret passes through the chat.
- **Credentials as files with placeholders:** `fw_prepare_credentials` writes each file with
  `<paste …>` values and opens it in the text editor. New brands keep keys in the brand folder's
  hidden `.credentials/`, or in `~/.funnelwise/credentials/<brand>/` when the folder is
  cloud-synced. A hook (`hooks/secret_guard.py`) keeps Claude's file and shell tools out of them.
- **Testing mode:** detected at sign-in (`refresh_token_expires_in`) and on expiry (`invalid_grant`).
- No YouTube API-key fallback (not needed: the sign-in also serves public numbers).
