---
name: media-kit
description: Build a sponsor-facing media kit (or a one-page pitch for one platform or one sponsor) from the brand's real audience, reach and engagement numbers across YouTube, Instagram, Facebook, TikTok, Spotify, the website and search. Use when the user wants to land advertisers or sponsors, pitch a specific brand, make a media kit or rate card page, or "show sponsors our reach". Saves the report and its data snapshot to the brand folder.
---

# Media kit

Follow `reference/report-templates/report-conventions.md` (period, fetching, honesty, saving). This
file adds what is specific to media kits.

## 1. Clarify (one question at a time; skip what the request already says)

- **Mode:** full media kit (all platforms) or **one-pager** (one platform, e.g. TikTok or the
  podcast, or one target sponsor).
- **Audience:** a specific sponsor/industry? (*"a tyre brand"*: then tailor proof points and ad
  formats to them.)
- **Format:** HTML to send (default for media kits), Markdown, or PDF (save HTML, then print to PDF
  if the environment can, otherwise tell the user to print it).
- **Language:** `brand.language` unless the user asks for another (sponsor abroad).
- **Period:** last full month for monthly numbers; 90 days for website/search.

Topic names: `media-kit` (full) or `media-kit-onepager-<platform or sponsor slug>`.

## 2. Fetch (per `reference/sources.md`, only connected platforms)

Collect, where available:

| Section | Metrics (metrics.yaml) | Extra (into snapshot `extra`) |
|---|---|---|
| At a glance | `cross.total_followers`, `cross.monthly_reach` | per-platform follower list |
| YouTube | `youtube.subscribers`, `youtube.avg_views_per_video_30d`, `youtube.engagement_rate`, `youtube.views`, `youtube.watch_time_hours` | format mix (long-form/Shorts/live), top 5 videos last 12 months, series (e.g. a weekly show) |
| Instagram / Facebook | `instagram.followers`, `instagram.reach`, `instagram.engagement_rate`, `facebook.fans`, `facebook.impressions` | top posts |
| TikTok | `tiktok.followers`, `tiktok.avg_views_per_video`, `tiktok.engagement_rate`, `tiktok.total_likes` | top 5 recent videos |
| Podcast | `spotify.episode_count`, `spotify.release_cadence_days` | latest episodes; listener numbers only if the user supplies them (manual) |
| Website & search | `ga4.active_users`, `ga4.engagement_rate`, `gsc.impressions`, `gsc.clicks` | top countries (flag bot-like ones), top search topics showing purchase intent |
| Audience | — | demographics/geography from YouTube Analytics or Instagram if available |
| Proof | `cross.est_cpm_value` only from a rate card or past deal | `brand.yaml` `sponsorship.past_sponsors`, examples of past sponsor integrations |

Use the brand's own medians for "strong" claims (*"Shorts average 2.1× the channel's long-form
views"*), never outside benchmarks without a source in metrics.yaml.

## 3. Write

Structure (adapt headings to the language):

1. **Hero:** one sentence on who the audience is, from the data (*"Bulgaria's EV buyers"* style),
   period and "data as of" date.
2. **At a glance:** 4–6 big numbers (followers total, monthly reach, avg views per video,
   engagement rate, website users), each labelled with platform and period.
3. **One section per connected platform:** 2–4 numbers, the format mix, 3–5 top pieces of content.
4. **Audience:** who they are (countries, ages, gender where available), what they search for.
5. **Brands already working with us:** past sponsors and how the integration ran.
6. **Advertising opportunities:** formats that exist on these channels (integration in a video,
   dedicated video, Shorts series, podcast read, social posts, website placement), each tied to a
   number. Prices only from the user/rate card.
7. **For <sponsor>** (if targeted): 3 bullets on audience fit for that industry, from the data.
8. Then the convention sections: What changed, Data not available, Method & caveats, Next steps.

HTML: a single self-contained page in brand colours (`brand.colors`), big-number tiles, no charts
that need data the kit doesn't contain, readable printed on A4. Contact line: leave a placeholder
`[contact]` unless the user gives one.

## 4. Save and hand over

Per conventions §5. Then offer one follow-up from `next` in the skill catalog (e.g.
`content-performance` to find the formats that would carry a sponsor's message best).
