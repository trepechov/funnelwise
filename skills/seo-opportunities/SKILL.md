---
name: seo-opportunities
description: Prioritised SEO change list for the brand's website from Search Console (plus GA4 when connected). Striking-distance queries to push into the top 3, titles and meta descriptions to rewrite where CTR is far below what the position should get, pages competing for the same query, pages losing clicks, and indexing problems. Each change says which page, what to do, the metric behind it and what to watch. Use when the user wants more Google traffic, better search CTR, or asks which pages to fix first.
---

# SEO opportunities

Follow `reference/report-templates/report-conventions.md`. Needs `gsc` connected; GA4 adds
engagement of organic visitors.

## 1. Period

Default: the last 28 days ending 3 days before today, compared with the 28 days before
(`gsc_opportunities` computes the previous period itself). Topic: `seo-opportunities`.

## 2. Fetch

1. `gsc_performance_overview(date_from, date_to)` → `gsc.clicks`, `gsc.impressions`, `gsc.ctr`,
   `gsc.avg_position` and the previous period.
2. `gsc_opportunities(date_from, date_to)` → striking distance, CTR gaps, cannibalisation,
   declining pages, non-brand share (`gsc.striking_distance_queries` = `striking_distance_count`,
   `gsc.non_brand_click_share`).
3. `gsc_indexing_issues(pages=[the pages named in the top recommendations, max 10])` and
   `gsc_sitemaps()`.
4. If GA4 is connected: `ga_run_report(metrics=[sessions, engagementRate], dimensions=[landingPagePlusQueryString],
   dimension_filter={"filter": {"fieldName": "sessionDefaultChannelGroup", "stringFilter": {"value": "Organic Search"}}})`
   for the same pages → `ga4.organic_search_sessions`; note pages
   with high search clicks but low engagement (the page doesn't deliver what the query promised).
5. Optional, only if the user wants the full visual audit: `gsc_audit` (its text is Italian; say so).

## 3. Prioritise

Score each candidate change by **expected extra clicks per month** (from the tool's
`potential_extra_clicks` / `missed_clicks`), then by effort:

| Type | Effort | Typical change |
|---|---|---|
| CTR below expected (positions 1–10) | Low | Rewrite title + meta description to match the query's intent; add the number/year/price the searcher wants |
| Striking distance (positions 4–20) | Medium | Expand the section answering the query, add an FAQ block, internal links from strong pages with the query as anchor text |
| Cannibalisation | Medium | Pick one page per query; merge or differentiate the other, canonical or internal links to the winner |
| Declining page | Medium | Check indexing and the query mix; refresh content, fix what changed |
| Not indexed / sitemap errors | Low–High | Fix the reported coverage state; resubmit in Search Console (the user does this, Funnelwise is read-only) |

Group recommendations **by page** (one page may have several queries). Top 10 pages max.

## 4. Write

Sections: Summary (with total opportunity in clicks/month) → Search performance (4 numbers vs
previous period) → **Change list** (table: priority, page, change, why with numbers, watch) → For
each of the top 3 pages: a concrete proposed title (≤ 60 characters) and meta description
(≤ 155 characters) in the page's language, drafts only → Cannibalisation & indexing → convention
sections (What changed, Data not available, Method & caveats, Next steps).

Method note must say: the expected-CTR curve is a generic industry curve (from the tool's
`expected_ctr_curve`), used to rank opportunities, not a promise; brand queries are excluded.

## 5. Save

Per conventions §5, Markdown by default. `extra`: the top 25 striking-distance and CTR-gap rows and
the change list, so `content-ideas` can reuse them later.
