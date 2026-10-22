# Report conventions (all Funnelwise report skills)

Every report skill follows these rules so reports look alike, can be compared over time, and never
overstate the data.

## 1. Before fetching

1. `fw_brand`: brand name, **report language** (`brand.language`), scoped account IDs, profile.
2. `fw_list_snapshots(topic)`: if a snapshot of this topic exists, say so: *"There is a media kit from
   2026-07. I'll make a fresh one and show what changed."*
3. Confirm the period if the user didn't give one. Defaults: last full calendar month; for Search
   Console end 3 days before today (its data is incomplete for the last days).

## 2. Fetching

- Use only the IDs from `fw_brand`. Never call "list all sites/properties/accounts" tools to browse.
- Find the tool for each metric in `reference/sources.md` for the connector named in `via`.
- One platform failing never stops the report: record it, continue, and list it under
  **Data not available**.
- Keep raw lists (top posts, query tables) small: top 10–25.

## 3. The report

Write in `brand.language`. Use the brand's name, never "the client". Structure:

1. **Title + period + generated date**
2. **Summary**: 3–5 bullets a busy reader needs; each with a number.
3. **Body**: the skill's own sections.
4. **Recommendations**: each one in this format:
   > **Change:** what to do (concrete: which page/video/post, what to write)
   > **Why:** the metric behind it, with the number and period
   > **Watch:** the metric that should move, and when to check it
5. **What changed since <previous period>**: the table from `fw_diff_snapshot` plus 1–3 sentences
   on the biggest movements. Omit only on the first snapshot of a topic (say it's the first).
6. **Data not available**: every platform or metric that was missing, and why in a few words
   ("TikTok not connected", "YouTube Analytics needs the channel owner's sign-in").
7. **Method & caveats**: the `caveats` of each metric used (from `fw_metrics`), the period, and
   for estimates the formula.
8. **Next steps**: 1–2 related skills from `fw_skill_catalog` (`next:` of this skill) with their
   one-line reason, filtered to what the user's connections can run.

## 4. Honesty rules

- Every number comes from a tool result in this session or a saved snapshot. Never estimate a
  number that wasn't fetched; write "not available" instead.
- No outside benchmarks unless `metrics.yaml` has one with a source. Compare with the brand's own
  history or channel median instead.
- Say which denominator an engagement rate uses (per reach, per impressions, per view).
- Lifetime numbers (followers, total likes) are labelled "lifetime" or "as of <date>".
- Flag suspicious traffic (e.g. a country with high users and very low engagement) instead of
  quoting it to sponsors.

## 5. Saving

1. `fw_save_snapshot(topic, stamp=YYYY-MM, period…, metrics={metrics.yaml id: value}, source, caveats, extra)`.
   Metrics that could not be fetched are `null`. Tables used in the report go in `extra`.
2. `fw_diff_snapshot(topic)` → put its markdown into section 5.
3. `fw_save_report(topic, stamp, content, format)`: Markdown by default; HTML when the user wants
   something to send (media kits). HTML is one self-contained file: inline CSS, brand colours from
   `brand.colors`, no external scripts except optionally Chart.js from a CDN, print-friendly.
4. Tell the user where both files are, in one line. Don't paste the whole report again in chat.
