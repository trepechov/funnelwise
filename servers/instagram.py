#!/usr/bin/env python3
"""Read-only Instagram server (Instagram Graph API via the brand's Facebook Page).

Profile, recent posts, per-post insights, account insights for a period and
follower demographics, for brand.yaml connectors.instagram.username only. The
account must be a Business or Creator account linked to a Facebook Page.
Credentials: meta.json (see lib/meta_graph.py). No tool posts, replies,
deletes or messages.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib import meta_graph as graph  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import load_brand  # noqa: E402

MEDIA_FIELDS = "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"
MEDIA_METRICS = ["views", "reach", "saved", "shares", "total_interactions"]
ACCOUNT_METRICS = ["reach", "views", "accounts_engaged", "total_interactions", "profile_views",
                   "website_clicks", "follows_and_unfollows"]
BREAKDOWNS = ("country", "city", "age", "gender")

server = Server("funnelwise-instagram", instructions=(
    "Instagram Graph API data for the brand's own account only (brand.yaml). Instagram counts `views`, not "
    "impressions. Engagement rate is per reach. Account insights cover at most 30 days per call."
))


def _format(m: dict) -> str:
    product, kind = m.get("media_product_type"), m.get("media_type")
    if product == "REELS":
        return "reel"
    if product == "STORY":
        return "story"
    return {"CAROUSEL_ALBUM": "carousel", "IMAGE": "image", "VIDEO": "video"}.get(kind, str(kind).lower())


def _media(m: dict) -> dict:
    return {"id": m["id"], "format": _format(m), "timestamp": m.get("timestamp"),
            "caption": (m.get("caption") or "")[:120], "likes": m.get("like_count"),
            "comments": m.get("comments_count"), "permalink": m.get("permalink")}


def _values(rows: List[dict]) -> dict:
    out = {}
    for r in rows:
        if "total_value" in r:
            out[r["name"]] = r["total_value"].get("value", r["total_value"].get("breakdowns"))
        elif r.get("values"):
            out[r["name"]] = r["values"][-1].get("value")
    return out


@server.tool()
def instagram_profile() -> dict:
    """Get the brand's Instagram profile: username, name, followers, follows, number of posts, bio, website."""
    brand = load_brand()
    ig = graph.instagram_account(brand)
    return graph.get(ig, {"fields": "username,name,followers_count,follows_count,media_count,biography,website"},
                     graph.user_token(brand))


@server.tool()
def instagram_list_media(limit: int = 25, after: str = "") -> dict:
    """List the brand's recent Instagram posts, newest first: format (reel / carousel / image / video), date,
    caption start, likes, comments, link. For views and reach use instagram_media_insights.

    Args:
        limit: 1–50 posts per page.
        after: The `next_after` cursor from the previous page.
    """
    brand = load_brand()
    ig = graph.instagram_account(brand)
    params = {"fields": MEDIA_FIELDS, "limit": max(1, min(limit, 50))}
    if after:
        params["after"] = after
    data = graph.get(f"{ig}/media", params, graph.user_token(brand))
    return {"media": [_media(m) for m in data.get("data", [])], "next_after": graph.page_of(data)}


@server.tool()
def instagram_media_insights(media_ids: List[str]) -> dict:
    """Per-post insights for the brand's posts: views, reach, saves, shares, total interactions (up to 50 IDs).
    Posts of other accounts are refused.

    Args:
        media_ids: Post IDs from instagram_list_media.
    """
    brand = load_brand()
    token = graph.user_token(brand)
    username = brand.scope_id("instagram").lstrip("@").lower()
    out, refused = [], []
    for mid in media_ids[:50]:
        info = graph.get(mid, {"fields": "username,media_type,media_product_type,timestamp"}, token)
        if info.get("username", "").lower() != username:
            refused.append(mid)
            continue
        rows, unavailable = graph.insights(mid, MEDIA_METRICS, {}, token)
        out.append({"id": mid, "format": _format(info), "timestamp": info.get("timestamp"), **_values(rows),
                    **({"unavailable": unavailable} if unavailable else {})})
    return {"media": out, **({"refused_not_brand": refused} if refused else {})}


@server.tool()
def instagram_account_insights(date_from: str, date_to: str) -> dict:
    """Account totals for a period of at most 30 days: reach, views, accounts engaged, interactions, profile
    views, website clicks, follows/unfollows; plus new followers per day (last 30 days only).

    Args:
        date_from: YYYY-MM-DD.
        date_to: YYYY-MM-DD (inclusive).
    """
    windows = graph.day_range(date_from, date_to, 30)
    if len(windows) > 1:
        raise ToolError("Instagram account insights cover at most 30 days per call (reach is unique people, so "
                        "periods can't be added up). Ask for 30 days or less.")
    since, until = windows[0]
    brand = load_brand()
    ig, token = graph.instagram_account(brand), graph.user_token(brand)
    rows, unavailable = graph.insights(ig, ACCOUNT_METRICS, {"period": "day", "metric_type": "total_value",
                                                             "since": since, "until": until}, token)
    daily, _ = graph.insights(ig, ["follower_count"], {"period": "day", "since": since, "until": until}, token)
    new_followers = [{"date": v.get("end_time", "")[:10], "value": v.get("value")}
                     for r in daily for v in r.get("values", [])]
    return {"period": {"from": date_from, "to": date_to}, "totals": _values(rows),
            "new_followers_by_day": new_followers, **({"unavailable": unavailable} if unavailable else {})}


@server.tool()
def instagram_audience(breakdown: str = "country") -> dict:
    """Follower demographics of the brand's account (needs 100+ followers).

    Args:
        breakdown: country, city, age or gender.
    """
    if breakdown not in BREAKDOWNS:
        raise ToolError(f"breakdown must be one of {', '.join(BREAKDOWNS)}.")
    brand = load_brand()
    ig, token = graph.instagram_account(brand), graph.user_token(brand)
    rows, unavailable = graph.insights(ig, ["follower_demographics"], {
        "period": "lifetime", "metric_type": "total_value", "breakdown": breakdown}, token)
    results = []
    for r in rows:
        for b in r.get("total_value", {}).get("breakdowns", []):
            results += [{breakdown: x["dimension_values"][0], "followers": x["value"]} for x in b.get("results", [])]
    results.sort(key=lambda x: -x["followers"])
    return {"breakdown": breakdown, "followers": results, **({"unavailable": unavailable} if unavailable else {})}


if __name__ == "__main__":
    server.run()
