# Where each metric comes from

Skills depend on **metrics** (`reference/metrics.yaml`), not on tool names. This file maps each
metric to the tool that provides it for every connection path in `brand.yaml` `via:`.

- **own** = Funnelwise's local servers. Tool names are exact and tested.
- **windsor** = Windsor.ai's connector added in Claude's connector settings. Its tool names and
  coverage are **not verified**: find the matching tool by name, and if a metric isn't offered,
  report it as not available.
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

## YouTube (`via: own` → server `youtube`)

| Metric | Tool call |
|---|---|
| `youtube.subscribers` | `youtube_channel()` → `subscribers` (rounded by YouTube) |
| `youtube.views`, `youtube.watch_time_hours`, `youtube.avg_view_duration` | `youtube_analytics(date_from, date_to)` → `views`, `estimatedMinutesWatched` / 60, `averageViewDuration` |
| `youtube.avg_views_per_video_30d`, `youtube.engagement_rate`, `youtube.shorts_share` | `youtube_list_videos(max_results=50)` → videos published in the window; `format` short/long/live |
| Traffic sources, countries, age/gender, devices (extra) | `youtube_analytics(..., dimensions="insightTrafficSourceType" / "country" / "ageGroup,gender" / "deviceType")` |
| Retention of one video (extra) | `youtube_analytics(..., metrics=[averageViewPercentage, averageViewDuration], filters="video==<id>")` |

Analytics needs the owner/manager sign-in; public numbers work for listed competitor channels too.

## Instagram (`via: own` → server `instagram`)

| Metric | Tool call |
|---|---|
| `instagram.followers` | `instagram_profile()` → `followers_count` |
| `instagram.reach`, `instagram.profile_views`, `instagram.website_clicks` | `instagram_account_insights(date_from, date_to)` (≤ 30 days) → `totals` |
| `instagram.engagement_rate` | `instagram_list_media` + `instagram_media_insights(ids)` → `total_interactions / reach` per post |
| Audience (extra) | `instagram_audience("country" / "city" / "age" / "gender")` |

Instagram counts `views`, not impressions (Meta retired impressions in 2025).

## Facebook (`via: own` → server `facebook`)

| Metric | Tool call |
|---|---|
| `facebook.fans` | `facebook_page()` → `followers_count` |
| `facebook.impressions` | `facebook_page_insights(date_from, date_to)` → `totals.page_media_view` (views; Meta retired impressions) |
| `facebook.engagement_rate` | `facebook_list_posts` (reactions, comments, shares) + `facebook_get_post_insights(ids)` → `post_media_view` |

## TikTok (`via: own` → server `tiktok`, official Display API)

| Metric | Tool call |
|---|---|
| `tiktok.followers`, `tiktok.total_likes` | `tiktok_get_profile()` |
| `tiktok.avg_views_per_video`, `tiktok.engagement_rate` | `tiktok_list_videos(max_count=20)` (page with `cursor`) |

No views-by-day, audience or traffic-source data exists in the Display API.

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
