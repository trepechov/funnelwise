---
name: content-performance
description: What works on the brand's social channels. Compares each recent post or video with the channel's own median at a similar age, finds the format, topic, length and posting-day patterns behind the winners, and proposes first changes, each with the metric to watch. Covers YouTube (long-form, Shorts, live), Instagram, TikTok and Facebook. Use when the user asks which videos or posts work best, why views are down, what to post more of, or how to grow a channel.
---

# Content performance

Follow `reference/report-templates/report-conventions.md`. Needs at least one of youtube,
instagram, tiktok, facebook. Topic: `content-performance` (or
`content-performance-<platform>` when the user asks about one platform).

## 1. Scope

Ask (if unclear) which platforms and the window. Default: content published in the last 90 days,
judged by numbers as of today. Ask nothing else.

## 2. Fetch per platform (`reference/sources.md`)

For each platform, a sample of the last 90 days' content (YouTube up to 50 videos; Instagram up to
50 posts; TikTok up to 60 videos via `cursor`; Facebook up to 25 posts). For each item record: id,
title/caption (first 80 chars), publish date, **format** (YouTube: long-form / Short ≤ 3 min /
live, as `youtube_list_videos` labels them; Instagram: reel / carousel / image; TikTok: video; Facebook: video / link / image),
duration, views (or reach/impressions), likes, comments, shares/saves.

## 3. Analyse (do the arithmetic carefully; show the numbers)

1. **Age-fair comparison.** Views keep growing, so compare like with like: bucket items by age
   (0–7, 8–30, 31–90 days) and compute each bucket's median views per format. An item's
   **performance index** = its views ÷ its bucket-and-format median. ≥ 1.5 = winner, ≤ 0.5 = laggard.
2. **Engagement** per metrics.yaml (per view on YouTube/TikTok, per reach on Instagram, per
   impressions on Facebook). Note the denominator.
3. **Patterns** across winners vs the rest: format, topic or series (cluster titles by recurring
   words/names), length band, weekday/hour of publishing, title style (question, number, brand
   name first), thumbnail/hook if visible from the title. Only claim a pattern with ≥ 3 items behind
   it; say how many.
4. **Cross-platform:** the same topic on several platforms. Where did it do best?
5. If YouTube Analytics is available: retention and traffic sources for the top 3 and bottom 3.

Save metrics: `youtube.avg_views_per_video_30d`, `youtube.engagement_rate`, `youtube.shorts_share`,
`instagram.engagement_rate`, `instagram.reach`, `tiktok.avg_views_per_video`,
`tiktok.engagement_rate`, `facebook.engagement_rate`, `youtube.views` where available; the scored
item list goes in `extra`.

## 4. Write

Summary → **Top 5 and bottom 5** (table: item, format, age, views, index, engagement) → **What the
winners share** (each pattern with its count) → per-platform notes → **First changes** (3–5, in the
Change/Why/Watch format, e.g. *"Change: post the weekly show's best 60 s as a Short within 24 h.
Why: Shorts cut from episodes averaged 2.3× the Shorts median (5 of 6). Watch: Shorts median
views over the next 4 weeks."*) → convention sections.

Be concrete: name the videos and posts. No generic social-media advice that the numbers don't
support.

## 5. Save

Per conventions §5. Next steps: `social-improvement-plan` (planned) for a full plan, and
`media-kit` to use the winning formats as sponsor proof points.
