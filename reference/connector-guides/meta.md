# Connect Instagram and Facebook

Instagram must be a **Business or Creator account linked to a Facebook Page**. Personal accounts
have no API access.

## Metricool (`via: metricool`)

1. In Claude: **Settings → Connectors**, add **Metricool**, sign in, and connect the brand's
   Instagram and Facebook Page inside Metricool (free plan: one brand).
2. Tell Claude the Instagram **username** and the Facebook **Page ID** (Page → About → Page
   transparency, or Meta Business Suite → Settings → Page info). Claude saves them with
   `fw_set_connector instagram metricool <username>` / `facebook metricool <page id>`.
3. Metricool's connector can also *post*. Funnelwise blocks every posting, replying and deleting
   tool, but turn off posting permissions in Metricool too if you can.
