# Funnelwise brand folder

This folder holds everything Funnelwise knows about one brand. It is yours: back it up,
share the reports, keep it in Drive or Dropbox if you like.

| Path | What it is |
|---|---|
| `brand.yaml` | Brand name, report language, colours, and the one account per platform Funnelwise may use |
| `reports/` | Finished reports, one file per topic and month, e.g. `media-kit-2026-10.html` |
| `data/` | The numbers behind each report, e.g. `media-kit-2026-10.json`; used for "what changed" and custom reports |
| `notes/` | What Funnelwise has learned: `profile.md` (your role and goal), brand facts |

Passwords, tokens and keys live in the hidden `.credentials/` folder here, readable only by your
user account and excluded from git. If this folder is synced (iCloud Drive, including a synced
Desktop or Documents folder, Dropbox, Google Drive, OneDrive), they live in
`~/.funnelwise/credentials/<brand>/` instead, so they never leave this computer. Don't share or
upload `.credentials/`.
