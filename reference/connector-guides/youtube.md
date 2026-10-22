# Connect YouTube

Two levels:

- **Public numbers** (subscribers, video views, likes, comments counts, video list) work as soon as
  YouTube is connected. That is enough for most of the media kit and content-performance reports.
- **YouTube Analytics** (watch time, average view duration, retention, traffic sources,
  demographics) needs a one-time sign-in **by the channel's owner or manager**.

## The one gotcha that matters

If the channel is a **Brand Account**, the person who signs in must be an **Owner or Manager of the
Brand Account** (Google account settings → brand account → Manage permissions). A *Studio Editor*
or *Viewer* role in YouTube Studio is not enough: the sign-in "works" but returns the signer's own
(often empty) personal channel. Funnelwise always asks for the brand's channel by ID and blocks
`mine: true` for that reason.

## Easy path: Metricool (`via: metricool`)

Add the Metricool connector in Claude's settings and connect YouTube inside Metricool. Which
Analytics metrics it exposes is still being verified (`docs/spikes/0.3-easy-path-audit.md`).
Demographics and retention will probably still need the developer path.

## Developer path (`via: own`, Claude Code with `uv` installed)

1. Find the **channel ID**: YouTube Studio → Settings → Channel → Advanced settings, or the
   `youtube.com/channel/UC…` link. Claude saves it with `fw_set_connector youtube own UC… {handle}`.
2. In the same Google Cloud project as the GA4 key (see `google.md`): **APIs & Services → Library**,
   enable **YouTube Data API v3**, **YouTube Analytics API** and **YouTube Reporting API**.
3. **OAuth consent screen**: User type External, app name "Funnelwise", your email. Under **Test
   users** add the email of the person who will sign in.
4. **Credentials → Create credentials → OAuth client ID → Desktop app**. Download the JSON and
   import it: `fw_import_credential(kind="google-oauth-client", …)`.
5. Restart Claude, then run the `youtube_auth` tool. The channel owner/manager signs in, choosing
   the **brand account** in Google's account picker.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Analytics tools return 0 rows; subscriber count is tiny | Signed in as a personal account, not the Brand Account | Delete `token.json` in the credentials folder, sign in again choosing the brand account; the signer needs Owner/Manager rights |
| Sign-in works for a week, then fails (`invalid_grant`) | OAuth app in **Testing** mode: refresh tokens expire after 7 days | Re-run `youtube_auth` weekly, or publish the consent screen (Google verification needed for sensitive scopes) |
| 403 "insufficient authentication scopes" on comments | Token was created without the comments scope | Re-run `youtube_auth` |
| `youtube_connection_help` is the only tool | `uv` not installed or YouTube not set to `via: own` | Use Metricool, or install uv (developer path) |
