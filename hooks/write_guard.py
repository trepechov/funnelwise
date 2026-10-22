#!/usr/bin/env python3
"""PreToolUse hook: keep marketing connectors read-only and on the brand's own accounts.

Applies to MCP tools whose server looks like a marketing platform (ours, the
pinned third-party servers, and easy-path connectors such as Metricool). Two
checks:

1. Write guard: deny tools whose action verb writes to a live account (post,
   publish, reply, delete, send, schedule, upload, update, …). The verb is the
   first word of the tool name after any platform prefix, so `get_post_comments`
   is allowed and `youtube_post_comment` is not.
2. Scope guard: deny calls whose account argument (site_url, show_id, property
   ID, channel ID, Page ID, username) points at an account other than the one in
   brand.yaml (or a listed competitor where research makes sense), and YouTube
   `mine: true`, which resolves to whoever signed in rather than the brand.

Never blocks on its own failure: if brand.yaml can't be read, only the write
guard applies.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servers"))

MARKETING_SERVER = re.compile(
    r"youtube|instagram|facebook|meta|tiktok|spotify|analytics|ga4|search.?console|gsc|metricool|windsor|"
    r"supermetrics|semrush|ahrefs", re.I)
PLATFORM_PREFIXES = {"youtube", "yt", "ga", "ga4", "gsc", "tiktok", "spotify", "instagram", "ig", "facebook", "fb",
                     "meta", "metricool", "windsor", "semrush"}
WRITE_VERBS = {
    "post", "publish", "repost", "delete", "remove", "send", "reply", "respond", "schedule", "reschedule",
    "update", "upload", "create", "hide", "unhide", "bulk", "set", "add", "edit", "comment", "like", "unlike",
    "follow", "unfollow", "share", "modify", "patch", "put", "insert", "write", "submit", "approve", "ban",
    "block", "unblock", "boost", "pin", "unpin", "archive", "rename", "move", "invite", "dm", "message",
}

PLATFORM_OF_SERVER = [
    ("gsc", re.compile(r"search.?console|gsc", re.I)),
    ("ga4", re.compile(r"analytics|ga4", re.I)),
    ("youtube", re.compile(r"youtube", re.I)),
    ("spotify", re.compile(r"spotify", re.I)),
    ("tiktok", re.compile(r"tiktok", re.I)),
    ("facebook", re.compile(r"facebook", re.I)),
    ("instagram", re.compile(r"instagram", re.I)),
]
SCOPE_ARGS = {
    "gsc": ("site_url", "siteUrl", "site"),
    "ga4": ("property_id", "propertyId", "property"),
    "youtube": ("channel_id", "channelId"),
    "spotify": ("show_id", "showId"),
    "tiktok": ("username",),
    "facebook": ("page_id", "pageId"),
}


def split_tool(tool_name: str) -> Tuple[str, str]:
    """mcp__<server>__<tool> → (server, tool). Server names may contain underscores."""
    if not tool_name.startswith("mcp__"):
        return "", tool_name
    rest = tool_name[len("mcp__"):]
    server, _, tool = rest.rpartition("__")
    return server, tool


def words(tool: str) -> List[str]:
    tool = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", tool)  # camelCase → snake_case
    return [w for w in re.split(r"[_\-\s.]+", tool.lower()) if w]


def is_write_tool(tool: str) -> bool:
    ws = words(tool)
    while ws and ws[0] in PLATFORM_PREFIXES:
        ws = ws[1:]
    return bool(ws) and ws[0] in WRITE_VERBS


def platform_of(server: str) -> Optional[str]:
    for platform, pat in PLATFORM_OF_SERVER:
        if pat.search(server):
            return platform
    return None


def _norm(v: object) -> str:
    return str(v).strip().lower().rstrip("/").lstrip("@").replace("properties/", "")


def scope_problem(platform: Optional[str], args: dict, brand_data: Optional[dict]) -> Optional[str]:
    if not platform or not brand_data:
        return None
    if platform == "youtube" and args.get("mine") is True:
        own = ((brand_data.get("connectors") or {}).get("youtube") or {}).get("channel_id")
        return ("`mine: true` returns the signed-in Google account's channel, which may not be the brand's. "
                + (f"Use channel_id {own} instead." if own else "Pass the brand's channel ID instead."))
    block = (brand_data.get("connectors") or {}).get(platform)
    if not block:
        return None
    from lib.workspace import SCOPE_FIELDS  # noqa: E402

    own = block.get(SCOPE_FIELDS[platform])
    if not own:
        return None
    allowed = {_norm(own)}
    competitor_key = {"youtube": "youtube", "spotify": "spotify", "tiktok": "tiktok"}.get(platform)
    if competitor_key:
        allowed |= {_norm(c[competitor_key]) for c in brand_data.get("competitors") or [] if c.get(competitor_key)}
    for key in SCOPE_ARGS.get(platform, ()):
        if key in args and args[key] not in (None, "") and _norm(args[key]) not in allowed:
            return (f"{key}={args[key]} is outside this brand's scope. The brand's {platform} account is {own}"
                    + (" (competitors listed in brand.yaml are also allowed)." if competitor_key else "."))
    return None


def load_brand_data() -> Optional[dict]:
    try:
        from lib import bootstrap

        bootstrap()
        from lib.workspace import find_brand_dir, load_yaml

        d = find_brand_dir()
        return load_yaml(d / "brand.yaml") if d else None  # type: ignore[return-value]
    except Exception:
        return None


def decide(event: dict, brand_data: Optional[dict] = None, load: bool = True) -> Optional[str]:
    """Return a denial reason, or None to let the call through."""
    server, tool = split_tool(event.get("tool_name", ""))
    if not server or not MARKETING_SERVER.search(server):
        return None
    if is_write_tool(tool):
        return (f"Funnelwise is read-only: `{tool}` would change a live account (post, reply, delete, message, "
                "upload…). Draft the text in the brand folder instead and let the user publish it themselves.")
    if brand_data is None and load:
        brand_data = load_brand_data()
    return scope_problem(platform_of(server), event.get("tool_input") or {}, brand_data)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    reason = decide(event)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
