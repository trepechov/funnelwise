# Connector gotchas

Things that went wrong with real accounts and how to recognise them. Brand-specific facts belong
in the brand folder's `notes/`, not here. Each connector guide in `connector-guides/` has its own
troubleshooting table; this file is the cross-platform summary for reports and the connection check.

## Google (GA4, Search Console) and YouTube

- **Service account beats personal OAuth.** A service account sees only the properties it was added
  to. A personal OAuth token sees every site/property the person has, so a report could pick up the
  wrong one. Funnelwise's servers pin the property from brand.yaml either way.
- **Search Console `site_url` must match the property form exactly**: `https://www.example.com/`
  (URL-prefix, with trailing slash) or `sc-domain:example.com`. The bare domain gets a 403.
- **Search data lags ~3 days.** End comparison periods 3 days before today.
- **OAuth apps in Testing mode** issue refresh tokens that expire after **7 days**, and only listed
  test users can sign in. Publish the app ("In production"). Google then stops sending
  `refresh_token_expires_in`; the YouTube login tools use that field to warn straight away.
- **YouTube Brand Accounts:** only an Owner/Manager of the Brand Account gets the channel's
  Analytics. A Studio Editor's sign-in silently returns their personal channel (0 rows in
  Analytics). Always query by channel ID, never `mine: true`.
- YouTube public subscriber counts are rounded (3 significant figures).
- GA4 bot traffic shows up as high-user, very-low-engagement countries. Check before quoting reach.

## Meta (Instagram, Facebook)

- Instagram needs a Business/Creator account linked to a Facebook Page.
- Facebook post-level insights need a **Page** token; a User token fails with OAuthException 190
  subcode 2069032 even though page-level reads work.
- Long-lived user tokens expire after ~60 days; System User tokens and Page tokens derived from a
  long-lived user token don't (verify in the Access Token Debugger).
- Meta retired `impressions` (Instagram) and `page_impressions*` / `page_fans` (Facebook) in 2025:
  use `views` / `page_media_view`. Post insights return both a lifetime and daily rows: ask for
  `period=lifetime`.
- Third-party connectors list write tools (post, reply, delete, DM). Funnelwise's write guard
  blocks them; its own servers have none.
- Engagement rate denominators differ: Instagram per reach, Facebook per impressions.

## TikTok

- The Display API gives profile totals and per-video totals only: no views by day, no audience, no
  other creators. Competitor research needs another source.
- PKCE challenge is **hex**-encoded SHA256 (TikTok-specific, not base64url).
- Desktop redirect URI must match exactly, including the trailing slash.
- Sandbox apps work without review for accounts listed as target users.
- Access tokens last 24 h (auto-refreshed); refresh tokens 365 days.

## Spotify

- No listener/stream/audience numbers via any API; only Spotify for Creators has them.
- Since 2026, Web API access returns HTTP 403 "Active premium subscription required for the owner
  of the app" when the app owner's account has no Premium.
