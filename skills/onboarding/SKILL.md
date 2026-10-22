---
name: onboarding
description: Set up Funnelwise for a brand. Creates the brand folder and brand.yaml, captures the user's role and goal, connects each platform (GA4, Search Console, YouTube, Instagram, Facebook, TikTok, Spotify) the easiest way available, checks each connection live, and suggests the first report. Use right after installing Funnelwise, and when the user says "set up my brand", "set up Funnelwise", "get started", "connect my accounts", when there is no brand.yaml, or when they want to connect one more platform.
---

# Funnelwise onboarding

Goal: from nothing to a first real report in under an hour, without a terminal. The user is
usually a marketer, not a developer. Ask one thing at a time, prefer multiple-choice questions
(AskUserQuestion where available), and explain any technical step in plain words.

## 0. Where are we?

Call `fw_brand`.
- **Works** → a brand already exists. Skip to step 3 for the platforms in `not_connected`, or to
  step 2 if there is no `profile`. Don't redo finished steps.
- **"No brand folder found"** → step 1.

## 1. Create the brand folder

Ask for (one question each, with an example):
1. Brand name. 2. Website (optional). 3. Report language (offer the likely ones; code like `en`, `bg`).
4. Where to keep the folder: suggest the current working folder if it is empty or already named
   after the brand, otherwise `~/Documents/Funnelwise – <Brand>`.

Then `fw_init_brand(folder, name, language, website, short)`. Mention in one sentence what the
folder holds (brand.yaml, reports/, data/, notes/) and that passwords/keys are kept elsewhere.

## 2. Role and goal (profile)

Ask the role (single choice): Marketing manager · Social media / content manager · SEO / web
specialist · Sponsorship / advertising specialist · Data analyst · Developer · Other.

Ask the goal in their own words, with examples: *"land more sponsors with a media kit"*, *"get more
traffic from Google"*, *"find out which videos work and post more of those"*, *"track our KPIs every
month"*. Save it **verbatim**.

Write `notes/profile.md`:

```markdown
# Profile
- **Role:** <role label> (`<role id>`)
- **Goal:** <their words>
- **Saved:** <YYYY-MM-DD>
```

Role ids: marketing-manager, social-media-manager, seo-specialist, sponsorship-specialist,
data-analyst, developer, other. If a profile exists and their stated goal has clearly changed, offer
to update it; never overwrite silently.

## 3. Connect platforms

Call `fw_skill_catalog(role)` and `fw_connection_status`. Ask which platforms the brand uses
(multi-select). Connect the ones that matter most **for their goal first** (sponsorship → YouTube
and the socials; SEO → Search Console then GA4). Each platform can be skipped.

For each platform, pick the path and follow its guide in `reference/connector-guides/`:

| Platform | Easiest path | Guide |
|---|---|---|
| GA4, Search Console | One Google service-account key for both | `google.md` |
| YouTube | Channel owner/manager signs in once | `youtube.md` |
| Instagram, Facebook | Metricool connector (sign-in); developer path: Meta token | `meta.md` |
| TikTok | Own TikTok app in Sandbox + one sign-in | `tiktok.md` |
| Spotify | Own Spotify app (2 values) | `spotify.md` |

Rules while connecting:
- **Scope ID first.** Get the one account ID (GA4 property ID, site URL, channel ID, username, Page
  ID, show ID) and save it with `fw_set_connector(connector, via, scope_id)`. Read the ID back to the
  user to confirm it is the right account.
- **Secrets via files.** Use `fw_import_credential(kind, path)` for downloaded files (it locks the
  file to the user and tells them to delete the download). Use `fw_save_credential` only for values
  that come as text (Spotify/TikTok IDs and secrets), and say they pass through the chat.
- **Sign-ins without a terminal:** TikTok → `tiktok_login_start`, then `tiktok_login_status`;
  YouTube → `youtube_auth` (developer path).
- **Easy path (`via: metricool` etc.):** the user adds the connector in Claude's settings
  (Settings → Connectors). Funnelwise can't install it for them. After they do, check that its tools
  answer.
- **Validate live** right after each one: one cheap call (the same ones `connection-check` uses).
  ✅ → next platform. ❌ → explain the error with the guide's troubleshooting table; offer to retry
  or skip. Don't loop more than twice on the same error.
- Warn once, if they use Metricool or the developer Meta/YouTube servers: these connectors also
  contain posting/deleting tools; Funnelwise blocks them, and nothing will be posted.

## 4. First report

From `fw_skill_catalog(role)` → `for_role.available_now`, take the first skill that can run with
what is now connected; else the first of `fallback_mvp_skills`. Adjust to the goal (e.g. a
marketing manager whose goal is sponsors → `media-kit`). Say in one sentence **why** it serves their
goal, and offer to run it now.

Finish with a short recap: brand folder path, platforms connected (and skipped), the profile, and
that "what can I do?" (`start` skill) shows everything else.
