---
name: connection-check
description: Cheap health check of every connected Funnelwise platform. One small read call per platform, confirming it works and pulling one useful number with a quick insight. Use when the user asks "is everything connected?", "check my connections", before a big report, or when a report was missing a platform.
---

# Connection check

Budget: **exactly one live tool call per connected platform**, small limits, short windows. No
retries, no debugging, no re-authenticating inside this check. Load any deferred tools in one batch.

1. `fw_connection_status` (no network). Platforms with `connected: false` are listed as "not
   connected", not tested. Own-server platforms whose `credentials.ready` is false are ❌ with the
   first `next_steps` item; don't call them.
2. For each remaining platform make one call. **Rotate** what you sample across runs (pick by the
   day of the month) so repeated checks show different angles:

| Platform | Call (own path) | Rotate between |
|---|---|---|
| GA4 | `ga_run_report(date_from="yesterday", date_to="today", metrics=[activeUsers or eventCount], dimensions=[one of: country, deviceCategory, eventName, sessionDefaultChannelGroup], limit=5)` | the dimension and the metric |
| Search Console | `gsc_performance_overview(date_from=today-5d, date_to=today-3d, compare_previous=false)` | which number anchors the insight: clicks, impressions, CTR, position |
| YouTube, Instagram, Facebook | One cheap profile/stats call on the connector the brand chose (Metricool etc.), for the brand's own channel/username/Page ID | the one number it returned |
| TikTok | `tiktok_get_profile()` or `tiktok_list_videos(max_count=3)` | profile totals vs. newest/most-viewed of 3 |
| Spotify | `spotify_get_show_episodes(limit=3)` | newest episode vs. days between the last two |

For `via: metricool` / `windsor`: one lightweight read from that connector for the platform. If its
tools aren't loaded, status ❌ "connector not enabled in Claude's settings".

3. Output only this table (brand's language), plus at most one line after it:

| Platform | Status | Sample | Quick insight |
|---|---|---|---|

- **Status:** ✅ data returned · ⚠️ connected but empty/stale · ❌ error (name it in a few words:
  "token expired", "not signed in", "no access to property")
- **Sample:** the one brand-specific number, with its window, e.g. "142 clicks (3 days)".
- **Quick insight:** one genuinely useful observation about that number (trend, anomaly, idea),
  not filler.

Never mention other properties, sites or channels a credential can see, and never report counts
across accounts. For ❌ rows, the one line after the table may point to the guide in
`reference/connector-guides/` for the first broken platform.
