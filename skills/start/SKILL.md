---
name: start
description: Answer "what can I do?" for Funnelwise. Shows the reports suggested for the user's role and goal, which ones can run with the platforms connected now, what connecting one more platform would unlock, and what is coming. Use when the user asks what Funnelwise can do, which report to run, or seems unsure where to begin.
---

# What can I do?

1. `fw_brand`. If there is no brand folder, offer the `onboarding` skill and stop.
2. Read the role id and goal from `profile` (notes/profile.md). No profile → ask the role in one
   multiple-choice question and the goal in their words, offer to save them (see `onboarding` step 2).
3. `fw_skill_catalog(role)`.

Answer in the brand's language, short:

**Suggested for you** (role + goal): the available skills from `for_role.available_now` that can run,
in order, each with one line on why it serves *their stated goal* and an example request, e.g.
*"Make a media kit for a tyre brand, in PDF"*.

**Ready with your connections**: the other available skills with `can_run_now: true`.

**Connect one more platform to unlock**: for skills blocked only by `missing_connections`, name the
platform and what it unlocks (*"Connect Search Console to get the SEO opportunity list"*). Pick at
most 3, most relevant to the goal first.

**Coming later**: one line listing a few `planned` skills relevant to the role.

End with: anything custom works too, because reports reuse the saved `data/` snapshots
(*"compare this month with July"*, *"a one-pager for one sponsor"*).

If the stated goal clearly differs from the saved one, offer to update `notes/profile.md`.
