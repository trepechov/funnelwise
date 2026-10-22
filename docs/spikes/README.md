# Phase 0 spike notes

Each note answers one Phase 0 question from the plan, says what was verified and how, and lists
what is still unverified. **Verified** = tested on a real machine or account. **Documented** =
taken from official docs or vendor pages, not yet tried. **Open** = needs a human with Claude
Desktop or a pilot user.

| Spike | Question | Status (2026-10-22) |
|---|---|---|
| [0.1](0.1-cowork-plugin-capabilities.md) | What a plugin can ship and run in Claude Desktop / Cowork | Partly verified (from an earlier plugin); Desktop install of Funnelwise open |
| [0.2](0.2-server-packaging.md) | Servers without a terminal | **Decided and verified**: stdlib Python 3.9 servers + vendored libs, no `uv`/Node |
| [0.3](0.3-easy-path-audit.md) | Which easy-path connectors cover which metrics | Documented; live audit with an account open |
| [0.4](0.4-write-guard-on-desktop.md) | Do PreToolUse hooks run in Cowork; can a plugin block connector tools | Hook works in Claude Code (tested); Cowork open |
| [0.5](0.5-setup-friction-test.md) | Time a non-developer through the Google setup | Protocol written; run open |
