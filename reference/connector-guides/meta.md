# Connect Instagram and Facebook

One Meta token covers both. Funnelwise reads the brand's Facebook Page and its Instagram account
with read-only permissions. It can't post, reply, delete or send messages. About 20 minutes, once.

## What you need

- Instagram as a **Business or Creator account linked to the brand's Facebook Page** (Instagram
  app → Settings → Account type and tools). Personal accounts have no API access.
- The Page in a **Meta Business portfolio** (<https://business.facebook.com/>) where you are an
  admin. Create one for free if the Page isn't in one yet.

The token is a **System User token**: it belongs to the business, not to a person, and doesn't
expire. Nobody's password is involved, and it sees only the Page and Instagram account you assign.

## Steps

1. **Create a Meta app.** <https://developers.facebook.com/apps> → **Create app**. Name it e.g.
   "Funnelwise <Brand>". When asked for a use case choose **Other**, then app type **Business**,
   and connect it to the brand's business portfolio. The app can stay in development mode.
2. **Create a system user.** <https://business.facebook.com/settings> → **Users → System users →
   Add**. Name `funnelwise`, role **Employee** → **Create system user**.
3. **Give it the brand's accounts, read-only.** With the system user selected → **Assign assets**:
   - **Pages** → the brand's Page → turn on only the **insights / view performance** permission
     (plus **content** if posts don't show up later) → **Assign**.
   - **Instagram accounts** → the brand's account → the same → **Assign**.
   - **Apps** → the app from step 1 → **Assign** (needed to generate the token in step 4).
4. **Generate the token.** Same screen → **Generate new token** → choose the app → **Token
   expiration: Never** → tick only: `instagram_basic`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `read_insights` → **Generate token**. Copy it (it
   starts with `EAA`). Meta shows it only once.
5. **Give it to Funnelwise without pasting it into the chat.** Claude runs
   `fw_prepare_credentials instagram`, which creates `meta.json` in the brand's private
   credentials folder and opens it in your text editor. Replace the `<paste …>` value (keep the
   quotes) and save.
6. **Account IDs.** The Instagram **username** (without @) and the Facebook **Page ID** (Page →
   **About → Page transparency**, or Meta Business Suite → Settings → Page info). Claude saves them
   with `fw_set_connector instagram own <username>` and `facebook own <page id>` and runs one test
   call each.

Funnelwise uses only the Page and Instagram account in brand.yaml, even if the token can see more.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| "The Meta token is invalid or expired" | Token copied incompletely, deleted, or a short-lived personal token was used | Step 4 with **Never** expiry; paste it again into `meta.json` |
| "The Meta token is missing a permission" | A permission wasn't ticked | Step 4 again with all five permissions |
| "The Meta token has no access to the brand's Page" | Page not assigned to the system user | Step 3 (Pages) |
| "can't see the Instagram account @…" | Instagram not Business/Creator, not linked to the Page, or not assigned | Check the account type and the Page link in Instagram; step 3 (Instagram accounts) |
| Posts list is empty but the Page has posts | Insights-only access | Step 3: add the content permission for the Page |
| "Meta's rate limit was reached" | Too many calls in a short time | Wait a few minutes |
