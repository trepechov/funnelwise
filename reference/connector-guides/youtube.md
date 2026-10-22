# Connect YouTube

Funnelwise reads YouTube with your own Google sign-in client and one sign-in by the channel's
owner or manager. About 20 minutes, once.

- **Public numbers** (subscribers, views, likes, comments, the video list).
- **YouTube Analytics** (watch time, average view duration, traffic sources, countries, age and
  gender, new subscribers per period).

Funnelwise asks only for read access (`youtube.readonly`, `yt-analytics.readonly`). It can't
upload, edit, comment or delete.

## What you need

- The Google Cloud project you made for Analytics and Search Console (`google.md`), or a new one.
- The person who will sign in must be an **Owner or Manager** of the channel. If the channel is a
  Brand Account, that means Owner/Manager of the Brand Account. Being a Studio Editor isn't enough.

## Steps

1. **Turn on the two APIs.** <https://console.cloud.google.com/> → the project → **APIs &
   Services → Library**. Enable **YouTube Data API v3**, then **YouTube Analytics API**.
2. **Set up the sign-in screen.** Menu → **Google Auth Platform** (or **APIs & Services → OAuth
   consent screen**) → **Get started**. App name e.g. "Funnelwise <Brand>", your email as support
   contact, audience **External**, then **Create**.
3. **Publish it (important).** **Audience → Publishing status → Publish app → Confirm**, so the
   status reads **In production**. An app left in **Testing** ends every sign-in after 7 days and
   YouTube disconnects every week. You don't need Google's verification for the brand's own use:
   the sign-in just shows a "Google hasn't verified this app" warning once (step 7). If the brand
   uses Google Workspace, choosing audience **Internal** also avoids the 7-day limit.
4. **Create the client.** **Clients → Create client** → application type **Desktop app** → name
   "Funnelwise" → **Create**. Keep the window with the **Client ID** and **Client secret** open.
5. **Give the client to Funnelwise without pasting it into the chat.** Claude runs
   `fw_prepare_credentials youtube`, which creates `client_secret.json` in the brand's private
   credentials folder and opens it in your text editor. Replace the two `<paste …>` values (keep
   the quotes) and save. Or click **Download JSON** and tell Claude *"the YouTube client file is in
   my Downloads"*: it imports the file with `fw_import_credential kind=google-oauth-client`.
6. **Channel ID.** YouTube Studio → **Settings → Channel → Advanced settings**, or
   <https://www.youtube.com/account_advanced>: the ID starts with `UC`. Claude saves it with
   `fw_set_connector youtube own <UC…> {"handle": "@…"}`.
7. **Sign in once.** Claude runs `youtube_login_start` and gives you a link. Open it, choose the
   **brand's channel** if Google asks which account or channel. On "Google hasn't verified this
   app", click **Advanced → Go to Funnelwise <Brand>** (it's your own app), then **Continue** /
   **Allow**. The browser says "Google sign-in received". Claude checks with `youtube_login_status`.
   If the owner is somewhere else, send them the link: their browser ends on a page that doesn't
   load (`http://127.0.0.1:3456/?…code=…`). They copy that whole address and send it back, and
   Claude finishes with `youtube_login_finish`.

Funnelwise saves the sign-in only if the account can read **this channel's** Analytics. If the
wrong account signs in, nothing is saved and Claude tells you which account it was.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Google says this sign-in ends in 7 days" right after signing in | App still in **Testing** | Step 3 (Publish app), then sign in again |
| "The Google sign-in has expired or was revoked" after about a week | Same: Testing mode | Step 3, then `youtube_login_start` again |
| "Signed in as … which can't read the Analytics of the brand's channel" | Personal account or Studio Editor signed in | Sign in again choosing the Brand Account; the person needs Owner/Manager rights |
| "Access blocked: … has not completed the Google verification process" / `access_denied` | App in Testing and the person isn't a test user | Step 3 |
| `redirect_uri_mismatch` | Client type isn't **Desktop app** | Step 4 again with Desktop app |
| HTTP 403 "API has not been used in project" | API not enabled | Step 1, in the same project as the client |
| "Port 3456 is busy" | Another sign-in is still waiting | Wait 10 minutes or use the other-computer route |
