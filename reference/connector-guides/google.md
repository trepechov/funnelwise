# Connect Google Analytics 4 and Search Console

One Google **service-account key** connects both. A service account is a robot Google account
that only sees what you add it to, so Funnelwise can never see your other sites or properties.
No browser sign-in, no weekly re-login. About 15 minutes, once.

> Screenshots: to be added during pilot prep (plan 3.3). The steps below name every button.

## What you need

- Admin access to the brand's GA4 property and owner/full access to its Search Console property.
- A Google account that can create a Google Cloud project (any Gmail works; it's free).

## Steps

1. **Create a project.** Open <https://console.cloud.google.com/>, click the project picker at
   the top → **New project** → name it e.g. "Funnelwise <Brand>" → **Create**.
2. **Turn on the two APIs.** Menu → **APIs & Services → Library**. Search **Google Analytics Data
   API** → **Enable**. Back to the library, search **Google Search Console API** → **Enable**.
3. **Create the service account.** Menu → **IAM & Admin → Service Accounts → Create service
   account**. Name: `funnelwise`. Click **Create and continue**, skip the optional role step,
   **Done**.
4. **Download its key.** Click the new service account → **Keys** tab → **Add key → Create new
   key → JSON → Create**. A `.json` file downloads.
5. **Give it to Funnelwise.** Tell Claude *"the Google key is in my Downloads"*. It runs
   `fw_import_credential(kind="google-service-account", source_path=…)`, which copies the key into
   your private credentials folder and shows the robot's email address
   (`funnelwise@<project>.iam.gserviceaccount.com`). Delete the downloaded file afterwards.
6. **Let it read GA4.** In Google Analytics: **Admin → Property access management → + → Add
   users**, paste the robot email, role **Viewer**, untick "Notify", **Add**.
   Copy the **property ID** from **Admin → Property details** (a number like `123456789`).
7. **Let it read Search Console.** In Search Console, select the brand's property → **Settings →
   Users and permissions → Add user**, paste the robot email, permission **Restricted** (enough
   to read) → **Add**. Copy the property name exactly as shown in the property picker: either
   `https://www.example.com/` (URL-prefix) or `example.com` (domain property → write it as
   `sc-domain:example.com`).
8. Claude saves both IDs (`fw_set_connector ga4 own <property id>` and `gsc own <site url>`) and
   runs one test call each.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| HTTP 403 "User does not have sufficient permissions" (GA4) | Robot not added to *this* property, or added to the account but a different property | Step 6 on the right property; wait 1–2 minutes |
| HTTP 403 (Search Console) | Robot not added, or the site URL form differs (`http` vs `https`, `www` vs none, domain vs URL-prefix) | Step 7; copy the property name exactly |
| HTTP 403 "API has not been used in project" | API not enabled | Step 2 in the same project as the key |
| "private key looks invalid" | Wrong file imported (e.g. an OAuth client file) | Re-download the service-account key (step 4) |
| GA4 numbers look inflated, strange countries | Bot traffic | Check engagement rate by country before quoting to sponsors |

The same Google Cloud project also holds the YouTube sign-in client (`youtube.md`).
