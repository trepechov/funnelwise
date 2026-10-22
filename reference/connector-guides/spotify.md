# Connect Spotify (podcast)

What you get: the show's public catalog data: name, description, number of episodes, each
episode's title, release date and length. That supports cadence and consistency claims in a media
kit.

What nobody gets through the API: **listeners, streams, followers or audience**. Those exist only
in **Spotify for Creators** (the podcast dashboard). If you want them in a report, export or read
them from there and give them to Claude as numbers (recorded as `manual`).

## Steps (about 5 minutes)

1. <https://developer.spotify.com/dashboard> → **Create app**. Any name and description. Redirect
   URI: `http://127.0.0.1:8888/callback` (required by the form, never used). Tick **Web API** →
   **Save**.
2. App → **Settings**: copy **Client ID** and **Client secret** and give them to Claude
   (`fw_save_credential(kind="spotify", …)`).
3. The show ID is the last part of the show's link: `open.spotify.com/show/<show id>`. Claude saves
   it with `fw_set_connector spotify own <show id>`.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| HTTP 403 "Active premium subscription required for the owner of the app" | Spotify now requires the **app owner's** account to have Premium for Web API access | Create the app from an account with Premium, or upgrade the owner; access returns a few hours after the status changes |
| HTTP 401 / "invalid_client" | Wrong ID/secret, or the secret was rotated | Copy both again from Settings |
| "Show … is outside this brand's scope" | Asked for another show | Add it to `competitors` in brand.yaml for competitor research |
