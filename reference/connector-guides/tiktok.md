# Connect TikTok

Funnelwise uses TikTok's official **Display API**: profile totals (followers, likes, video count)
and, per video, views, likes, comments and shares. It has **no** views by day, audience or
traffic data, and no access to other creators. The sign-in belongs to one TikTok account, so the
data is automatically the brand's own.

## Own app (`via: own`, works in Claude Desktop, no terminal)

About 20 minutes, once. No TikTok review is needed because the app stays in **Sandbox**.

1. <https://developers.tiktok.com/> → log in → **Manage apps → Connect an app**. Any name, e.g.
   "Funnelwise <Brand>".
2. Add products **Login Kit** and **Display API**. Scopes: `user.info.basic`, `user.info.profile`,
   `user.info.stats`, `video.list`.
3. Login Kit → **Desktop** → redirect URI exactly `http://localhost:3455/callback/`.
4. Keep the app in **Sandbox** and under **Sandbox settings → Target users** add the brand's TikTok
   account.
5. **Client key** and **Client secret**: Claude runs `fw_prepare_credentials tiktok`, which creates
   `tiktok.json` in the brand's private credentials folder and opens it in your text editor.
   Replace the two `<paste …>` values (keep the quotes) and save. They never pass through the chat.
6. Claude saves the username (`fw_set_connector tiktok own <username without @>`) and runs
   `tiktok_login_start`. Open the link **logged in as the brand's TikTok account** and approve.
   - Same computer: done automatically; Claude checks with `tiktok_login_status`.
   - Account owner elsewhere: send them the link. After approving, their browser shows a page that
     doesn't load at `http://localhost:3455/callback/?code=…`. They copy that whole address and send
     it back within a few minutes; Claude finishes with `tiktok_login_finish`.

The sign-in renews itself for 365 days, then needs step 6 again.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| "Wrong TikTok account: logged in as @x" | Browser was logged in to another TikTok account | Log out of TikTok in the browser, start again |
| `redirect_uri` error on TikTok's page | URI doesn't match step 3 exactly (trailing slash!) | Fix it in Login Kit |
| "Port 3455 is busy" | Another login is still waiting | Use the remote option (`tiktok_login_finish`) or restart Claude |
| `scope_not_authorized` | Display API or a scope not added | Step 2, then log in again |
