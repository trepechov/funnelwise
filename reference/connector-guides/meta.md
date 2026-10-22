# Connect Instagram and Facebook

Instagram must be a **Business or Creator account linked to a Facebook Page**. Personal accounts
have no API access.

## Easy path: Metricool (`via: metricool`, recommended)

1. In Claude: **Settings → Connectors**, add **Metricool**, sign in, and connect the brand's
   Instagram and Facebook Page inside Metricool (free plan: one brand).
2. Tell Claude the Instagram **username** and the Facebook **Page ID** (Page → About → Page
   transparency, or Meta Business Suite → Settings → Page info). Claude saves them with
   `fw_set_connector instagram metricool <username>` / `facebook metricool <page id>`.
3. Metricool's connector can also *post*. Funnelwise blocks every posting, replying and deleting
   tool, but turn off posting permissions in Metricool too if you can.

## Developer path (`via: own`, Claude Code with `uv`)

Uses a Meta app and long-lived tokens. Best done by the Meta Business Manager admin.

1. <https://developers.facebook.com> → **My apps → Create app** (type Business). Add **Instagram
   Graph API**.
2. Request **read-only** permissions: `instagram_basic`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`, `read_insights`. Leave out
   `pages_manage_posts`, `pages_messaging` and `instagram_content_publish`, so posting fails even
   though the connector lists such tools.
3. Best: create a **System User** in Business Manager and generate a non-expiring token for it.
   Otherwise: Graph API Explorer → user token → exchange for a long-lived token (60 days), then get
   the **Page token** from `/me/accounts` (Page tokens from a long-lived user token don't expire;
   verify in the Access Token Debugger).
4. Save with `fw_save_credential`:
   - `instagram`: `{access_token, app_id, app_secret, business_account_id}`
   - `facebook`: `{access_token: <PAGE token>, page_id}`

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| OAuthException 190, subcode 2069032 "Page access token is required" | The Facebook token is a User token | Use the Page token (step 3) |
| Token works for ~60 days, then 190 "Session has expired" | Long-lived user token expired | Use a System User token, or re-exchange every 60 days |
| Instagram "Unsupported get request" | Wrong business_account_id, or account not Business/Creator | Get the ID from `/me/accounts?fields=instagram_business_account` |
| The launcher refuses to start ("belongs to a different account") | `facebook.json` page_id ≠ brand.yaml page_id | Fix whichever is wrong; Funnelwise won't read another Page |
