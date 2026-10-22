# Where each metric comes from

Skills depend on **metrics** (`reference/metrics.yaml`), not on tool names. This file maps each
metric to the tool that provides it for every connection path in `brand.yaml` `via:`.

- **own** = Funnelwise's local servers. Tool names are exact and tested.
- **metricool / windsor** = easy-path connectors added in Claude's connector settings. Their tool
  names and coverage are **not verified yet** (spike 0.3, `docs/spikes/0.3-easy-path-audit.md`):
  find the matching tool by name, and if a metric isn't offered, report it as not available.
- **manual** = the user supplies a CSV/XLSX export or types the number; record it with source `manual`.

Tool names appear in Claude as `mcp__…__<tool>`; only the last part is listed here.

## Website: GA4 (`via: own` → server `ga4`)

| Metric | Tool call |
|---|---|
| `ga4.active_users`, `ga4.sessions`, `ga4.engagement_rate`, `ga4.key_events` | `ga_run_report(metrics=[activeUsers, sessions, engagementRate, keyEvents])` |
| `ga4.avg_engagement_time` | `ga_run_report(metrics=[userEngagementDuration, activeUsers])` → divide |
| `ga4.organic_search_sessions`, `ga4.social_sessions` | `ga_run_report(metrics=[sessions], dimensions=[sessionDefaultChannelGroup])` → pick rows |
| `ga4.returning_users_share` | `ga_run_report(metrics=[activeUsers], dimensions=[newVsReturning])` |
| country / device / landing page breakdowns (extra) | `dimensions=[country]`, `[deviceCategory]`, `[landingPagePlusQueryString]` |

Other paths: `google-ga4-mcp` (Google's official server; needs gcloud sign-in) → its `run_report`;
`windsor` → its GA4 source (verify).

## Website: Search Console (`via: own` → server `search-console`)

| Metric | Tool call |
|---|---|
| `gsc.clicks`, `gsc.impressions`, `gsc.ctr`, `gsc.avg_position` | `gsc_performance_overview(date_from, date_to)` (includes previous period) |
| `gsc.striking_distance_queries`, `gsc.non_brand_click_share` | `gsc_opportunities(date_from, date_to)` → `striking_distance_count`, `non_brand_click_share` |
| Query/page tables (extra) | `gsc_query(dimensions="query"` or `"page"` or `"query,page")` |
| Indexing (extra) | `gsc_indexing_issues(pages=[…])`, `gsc_sitemaps()` |

Other paths: `windsor` → its Search Console source (verify).

## YouTube (`via: own` → server `youtube`, youtube-studio-mcp)

Always pass the brand's `channel_id`. Never `mine: true` (the write guard blocks it).

| Metric | Tool call |
|---|---|
| `youtube.subscribers` | `youtube_get_channel(channel_id)` → `subscriberCount` (public, rounded) |
| `youtube.avg_views_per_video_30d`, `youtube.engagement_rate`, `youtube.shorts_share` | `youtube_list_videos(channel_id, …)` then `youtube_get_video` for stats/duration; compute per metrics.yaml |
| `youtube.views`, `youtube.watch_time_hours`, `youtube.avg_view_duration` | `youtube_analytics_overview` (needs the **channel owner/manager's** sign-in, see the YouTube guide) |
| Traffic sources, demographics, geography, retention (extra) | `youtube_analytics_traffic_sources`, `_demographics`, `_geography`, `_retention` (same sign-in) |
| Search demand (extra, content ideas) | `youtube_search_suggestions(query)` |

If Analytics tools return no rows for the brand channel, the sign-in belongs to another account.
Fall back to the public Data API numbers and list the Analytics metrics as not available.

Other paths: `metricool` → YouTube channel/video stats (verify which Analytics metrics).

## Instagram (`via: own` → server `instagram`, ig-mcp)

| Metric | Tool call |
|---|---|
| `instagram.followers` | `get_profile_info()` → `followers_count` |
| `instagram.reach`, `instagram.profile_views`, `instagram.website_clicks` | `get_account_insights(metric=…, period="day")` summed over the period |
| `instagram.engagement_rate` | `get_media_posts(limit)` + `get_media_insights(media_id)` per post (reach, likes, comments, saves, shares) |

Other paths: `metricool` → Instagram account and post stats (verify).

## Facebook (`via: own` → server `facebook`, facebook-mcp-server)

| Metric | Tool call |
|---|---|
| `facebook.fans` | `get_page_fan_count()` or `get_page_info()` |
| `facebook.impressions`, `facebook.engagement_rate` | `get_page_posts()` + `get_post_impressions`, `get_post_reactions_breakdown`, `get_number_of_comments`, `get_post_share_count` per post (needs a **Page** token) |

Other paths: `metricool` → Facebook Page stats (verify).

## TikTok (`via: own` → server `tiktok`, official Display API)

| Metric | Tool call |
|---|---|
| `tiktok.followers`, `tiktok.total_likes` | `tiktok_get_profile()` |
| `tiktok.avg_views_per_video`, `tiktok.engagement_rate` | `tiktok_list_videos(max_count=20)` (page with `cursor`) |

No views-by-day, audience or traffic-source data exists in the Display API.
Other paths: `metricool` → TikTok stats (verify; may include more than the Display API).

## Spotify (`via: own` → server `spotify`)

| Metric | Tool call |
|---|---|
| `spotify.episode_count` | `spotify_get_show()` → `total_episodes` |
| `spotify.release_cadence_days` | `spotify_get_show_episodes(limit=10)` → median gap between `release_date`s |

No listener, stream or audience numbers exist in the Spotify Web API. If the user has them from
Spotify for Creators, record them as `manual` in `extra` (they have no metrics.yaml id yet).

## Cross-platform

| Metric | How |
|---|---|
| `cross.total_followers` | Sum of the follower metrics fetched above; list the platforms included |
| `cross.monthly_reach` | Per formula in metrics.yaml; list the parts included |
| `cross.est_cpm_value` | Only from the brand's rate card or a past deal (ask the user); never market averages |
