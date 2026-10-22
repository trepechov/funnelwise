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
Demographics and retention may not be available through it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Analytics tools return 0 rows; subscriber count is tiny | Signed in as a personal account, not the Brand Account | Sign in again choosing the brand account; the signer needs Owner/Manager rights |
