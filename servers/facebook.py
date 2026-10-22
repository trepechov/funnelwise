#!/usr/bin/env python3
"""Read-only Facebook Page server (Graph API with a Page token).

Page info, recent posts, per-post insights and Page insights for a period, for
brand.yaml connectors.facebook.page_id only. Credentials: meta.json (see
lib/meta_graph.py); the Page token is derived for the brand's Page at run
time. No tool posts, replies, deletes or messages.

Meta retired `page_impressions*` and `page_fans` in 2025; "views"
(page_media_view) replaced impressions. Metric names live in the lists below so
the next deprecation is a one-line change.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib import meta_graph as graph  # noqa: E402
from lib.mcp_stdio import Server  # noqa: E402
from lib.workspace import load_brand  # noqa: E402

POST_FIELDS = ("id,created_time,message,status_type,permalink_url,shares,"
               "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)")
POST_METRICS = ["post_media_view", "post_total_media_view_unique", "post_clicks", "post_reactions_by_type_total",
                "post_video_views"]
# Daily metrics summed over the period; *_unique ones are sums of daily uniques, not unique people.
PAGE_SUM_METRICS = ["page_media_view", "page_total_media_view_unique", "page_post_engagements", "page_views_total",
                    "page_daily_follows_unique", "page_video_views"]
PAGE_LAST_METRICS = ["page_follows"]  # running total: the last day's value

server = Server("funnelwise-facebook", instructions=(
    "Facebook Page data for the brand's own Page only (brand.yaml). Meta now counts `views` (page_media_view / "
    "post_media_view) instead of impressions; use them for facebook.impressions and say so in the report."
))


def _post(p: dict) -> dict:
    return {"id": p["id"], "created_time": p.get("created_time"), "type": p.get("status_type"),
            "message": (p.get("message") or "")[:120], "permalink": p.get("permalink_url"),
            "reactions": ((p.get("reactions") or {}).get("summary") or {}).get("total_count"),
            "comments": ((p.get("comments") or {}).get("summary") or {}).get("total_count"),
            "shares": (p.get("shares") or {}).get("count", 0)}


@server.tool()
def facebook_page() -> dict:
    """Get the brand's Facebook Page: name, followers, likes (fans), category, link."""
    brand = load_brand()
    page_id = brand.scope_id("facebook")
    return graph.get(page_id, {"fields": "id,name,followers_count,fan_count,category,link"},
                     graph.page_token(brand, page_id))


@server.tool()
def facebook_list_posts(limit: int = 25, after: str = "") -> dict:
    """List the brand's recent Page posts, newest first: date, type, message start, reactions, comments,
    shares, link. For views and clicks use facebook_get_post_insights.

    Args:
        limit: 1–50 posts per page.
        after: The `next_after` cursor from the previous page.
    """
    brand = load_brand()
    page_id = brand.scope_id("facebook")
    params = {"fields": POST_FIELDS, "limit": max(1, min(limit, 50))}
    if after:
        params["after"] = after
    data = graph.get(f"{page_id}/posts", params, graph.page_token(brand, page_id))
    return {"posts": [_post(p) for p in data.get("data", [])], "next_after": graph.page_of(data)}


@server.tool()
def facebook_get_post_insights(post_ids: List[str]) -> dict:
    """Per-post insights for the brand's posts: views, unique viewers, clicks, reactions by type, video views
    (up to 50 IDs). Posts of other Pages are refused.

    Args:
        post_ids: Post IDs from facebook_list_posts (they start with the Page ID).
    """
    brand = load_brand()
    page_id = brand.scope_id("facebook")
    token = graph.page_token(brand, page_id)
    out, refused = [], []
    for pid in post_ids[:50]:
        if not pid.startswith(f"{page_id}_"):
            refused.append(pid)
            continue
        rows, unavailable = graph.insights(pid, POST_METRICS, {"period": "lifetime"}, token)
        values = {r["name"]: (r.get("values") or [{}])[-1].get("value") for r in rows}
        out.append({"id": pid, **values, **({"unavailable": unavailable} if unavailable else {})})
    return {"posts": out, **({"refused_not_brand": refused} if refused else {})}


@server.tool()
def facebook_page_insights(date_from: str, date_to: str) -> dict:
    """Page totals for a period: views, viewers (sum of daily uniques), post engagements, Page views, new
    follows, video views, and the follower total at the end of the period.

    Args:
        date_from: YYYY-MM-DD.
        date_to: YYYY-MM-DD (inclusive).
    """
    brand = load_brand()
    page_id = brand.scope_id("facebook")
    token = graph.page_token(brand, page_id)
    totals, unavailable, last = {}, set(), {}
    for since, until in graph.day_range(date_from, date_to, 90):
        rows, missing = graph.insights(page_id, PAGE_SUM_METRICS + PAGE_LAST_METRICS,
                                       {"period": "day", "since": since, "until": until}, token)
        unavailable.update(missing)
        for r in rows:
            values = [v.get("value") for v in r.get("values", []) if isinstance(v.get("value"), int)]
            if r["name"] in PAGE_LAST_METRICS:
                if values:
                    last[r["name"]] = values[-1]
            else:
                totals[r["name"]] = totals.get(r["name"], 0) + sum(values)
    return {"period": {"from": date_from, "to": date_to}, "totals": totals, "at_end": last,
            **({"unavailable": sorted(unavailable)} if unavailable else {})}


if __name__ == "__main__":
    server.run()
