---
name: onboarding
description: Set up Funnelwise for a brand, step by step. Welcomes the user, asks and confirms the brand details (name, website, report language, folder), collects the links of every channel the brand has (YouTube, Instagram, Facebook, TikTok, Spotify podcast, others), captures the user's role and goal, connects each channel and checks it live, then suggests the first report. Use right after installing Funnelwise, and when the user says "set up my brand", "set up Funnelwise", "get started", "connect my accounts", when there is no brand.yaml, when platforms are missing, or when they want to connect one more platform.
---

# Funnelwise onboarding

Goal: from nothing to a first real report in under an hour, without a terminal. The user is
usually a marketer opening Funnelwise for the first time, not a developer.

## How to talk during onboarding

- **Four steps, always in this order, always numbered** in what you say: *Step 1 of 4: your brand* ·
  *Step 2 of 4: your channels* · *Step 3 of 4: about you* · *Step 4 of 4: connect and first report*.
  Start every message of the flow with the step label so the user always knows where they are.
- **One question per message.** Prefer multiple choice (AskUserQuestion where available). Give an
  example answer with every open question.
- **Never show internals.** No tool names, file names, brand.yaml keys, JSON, error text, stack
  traces or notes from the session start. Translate them: "Saved." / "That link didn't work, let's
  try again." The only paths to show are the brand folder and a file the user must pick.
- **Never guess brand details.** A folder name, a website or an existing brand.yaml is a
  *suggestion*: show it and ask the user to confirm or correct it. Spelling of the brand name
  matters (it goes into every report), so read it back.
- Speak the user's chat language; reports use the brand's report language.

## 0. Where are we? (silent)

Call `fw_brand`, without saying anything about the result yet.
- **"No brand folder found"** → send the welcome, then step 1.
- **A brand exists** → send the welcome with "you're partly set up", then resume at the first
  unfinished step: brand details not confirmed by the user in this flow → step 1 (show and confirm);
  `brand.channels` missing → step 2; no `profile` → step 3; `channels_not_connected` or
  `not_connected` platforms the user said they use → step 4. Don't redo finished steps.

**Welcome** (adapt the wording, keep it this short):

> Welcome to Funnelwise. I'll set it up with you in 4 short steps (about 15 minutes, plus a few
> minutes per platform you connect):
> 1. your brand · 2. your channels · 3. about you · 4. connect them and run a first report.
>
> Funnelwise only reads your data. It never posts, replies or deletes anything.

## Step 1 of 4: your brand

Ask, one per message:
1. **Brand name** exactly as it should appear in reports (example: *"Acme Outdoor"*). Read the
   spelling back.
2. **Short name** or abbreviation, optional (example: *"Acme"*).
3. **Website**, optional (example: *https://www.acme.com*).
4. **Report language** (multiple choice: the chat language, English, and other likely ones).
5. **Folder** for reports and data: suggest the current working folder if it is empty or already
   named after the brand, otherwise `~/Documents/Funnelwise – <Brand>`.

Then show a short summary (name, short name, website, language, folder) and ask **"Is this right?"**
(Yes / Change something). Only after "yes": `fw_init_brand(folder, name, language, website, short)`
for a new brand, or `fw_update_brand({"brand": {...}})` for corrections to an existing one.
Say in one sentence what the folder holds (reports, data, notes) and that passwords and keys are
kept elsewhere on this computer.

## Step 2 of 4: your channels

Ask once, as a multi-select: **"Which channels does the brand have?"** Website (already known) ·
YouTube · Instagram · Facebook · TikTok · Spotify / podcast · LinkedIn · X. Every channel they
pick gets a link in the next question.

Then ask for the links, all in one message (example list for the ones they picked):

> Paste the link to each one, e.g.
> YouTube: https://www.youtube.com/@acme · Instagram: https://www.instagram.com/acme/ ·
> Facebook: https://www.facebook.com/acme · TikTok: https://www.tiktok.com/@acme ·
> Spotify: https://open.spotify.com/show/…

Show the list back, ask "Is this right?", then save with
`fw_update_brand({"brand": {"channels": {"youtube": "<link>", …}}})`. These links are the brand's
official accounts: step 4 connects exactly these and nothing else.

Also ask, optionally, for 1–3 competitors (name + website or channel) and save them with
`fw_update_brand({"competitors": [...]})`. Skipping is fine.

## Step 3 of 4: about you

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

## Step 4 of 4: connect and first report

Call `fw_skill_catalog(role)` and `fw_connection_status`. The list to connect is: the website
(GA4 + Search Console) plus every channel from step 2 that has a connector (YouTube, Instagram,
Facebook, TikTok, Spotify). LinkedIn and X are kept as links only; say so in one line.

Show the list with a rough time per platform and the order you suggest, **goal first**
(sponsorship → YouTube and the socials; SEO → Search Console then GA4; "data from everything" →
website first, then the channels by audience size). The user may reorder or skip any; a skipped
platform stays on the list for next time.

For each platform, follow its guide in `reference/connector-guides/`:

| Platform | Path (all `via: own`) | Credential | Guide |
|---|---|---|---|
| GA4, Search Console | One Google service-account key for both | downloaded file → `fw_import_credential` | `google.md` |
| YouTube | Own Google sign-in client + one sign-in (`youtube_login_start`) | `fw_prepare_credentials youtube` | `youtube.md` |
| Instagram + Facebook | One Meta System User token for both | `fw_prepare_credentials instagram` | `meta.md` |
| TikTok | Own TikTok app in Sandbox + one sign-in (`tiktok_login_start`) | `fw_prepare_credentials tiktok` | `tiktok.md` |
| Spotify | Own Spotify app (2 values) | `fw_prepare_credentials spotify` | `spotify.md` |

If the Google project from GA4/Search Console exists, reuse it for YouTube (the guide says so).

Rules while connecting:
- **Scope ID from the step 2 link.** Work out the account ID from the link the user gave
  (username from an Instagram/TikTok link, show ID from a Spotify link; ask for what a link can't
  give, like a YouTube channel ID `UC…` or a Facebook Page ID, and say where to find it). Save it with
  `fw_set_connector(connector, via, scope_id)` and read the account back to the user to confirm.
- **Secrets never go through the chat.** Values that come as text (client IDs and secrets, the Meta
  token): `fw_prepare_credentials(connector)` creates the file with `<paste …>` placeholders and
  opens it in the user's text editor. Tell them: replace each `<paste …>` text, keep the quotes,
  save, then say "done". Check with `fw_connection_status` (it names unfilled fields, never values).
  Downloaded files (Google key, Google client): `fw_import_credential(kind, path)`, then tell them
  to delete the download. If the user pastes a secret into the chat anyway, don't repeat it; save
  it with `fw_save_credential` and suggest rotating it later. Never open, search or edit credential
  files yourself (a hook blocks it).
- **Where the keys live**, in one sentence: in the brand folder's hidden `.credentials` folder, or,
  when `fw_prepare_credentials` shows the brand folder is synced (iCloud, Dropbox…), in a private
  folder outside it so keys don't leave the computer. Pass on any `warning` it returns.
- **Sign-ins without a terminal:** YouTube → `youtube_login_start`, then `youtube_login_status`;
  TikTok → `tiktok_login_start`, then `tiktok_login_status`.
- **Google Testing mode:** before the YouTube sign-in, make sure the user did the guide's "Publish
  app" step. If a login tool returns a `warning` that the sign-in ends in 7 days, stop and walk them
  through publishing, then sign in again: otherwise YouTube disconnects every week.
- **Validate live** right after each one: one cheap call (the same ones `connection-check` uses).
  ✅ → say the one number it returned (*"Connected: 12,400 subscribers"*) and go on. ❌ → explain in
  plain words with the guide's troubleshooting table; offer retry or skip. Don't loop more than
  twice on the same error.

**First report.** From `fw_skill_catalog(role)` → `for_role.available_now`, take the first skill
that can run with what is now connected; else the first of `fallback_mvp_skills`. Adjust to the goal
(e.g. a marketing manager whose goal is sponsors → `media-kit`). Say in one sentence **why** it
serves their goal, and offer to run it now.

**Recap** (short): brand folder, channels connected ✅ and still to connect ⏳, the profile, and
that "what can I do?" shows everything else and "connect my accounts" resumes setup.
