#!/usr/bin/env python3
"""Read-only Spotify server: public show/episode metadata for the brand's podcast.

Client Credentials flow (app-only token, no user login, no write or playback
scopes). The Spotify Web API has no podcast analytics (listeners, streams,
audience) at any access level; those exist only in Spotify for Creators.

Scope: brand.yaml connectors.spotify.show_id, plus shows listed under
competitors[].spotify for competitor research. Any other show is refused.
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib.http import get_json, request_json  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, load_brand  # noqa: E402

server = Server("funnelwise-spotify", instructions=(
    "Spotify public catalog data for the brand's podcast (scoped by brand.yaml). There are no listener or "
    "stream numbers in this API; say so instead of estimating them."
))
_token = {"value": None, "expires_at": 0.0, "client_id": None}


def _credentials(brand: Brand) -> dict:
    path = brand.credential("spotify.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"client_id": data["client_id"], "client_secret": data["client_secret"]}
    except FileNotFoundError:
        raise ToolError(f"No Spotify credentials yet ({path}). See reference/connector-guides/spotify.md.")
    except (KeyError, ValueError):
        raise ToolError(f"{path} must contain client_id and client_secret.")


def _get_token(brand: Brand) -> str:
    c = _credentials(brand)
    if _token["value"] and _token["client_id"] == c["client_id"] and time.time() < _token["expires_at"]:
        return _token["value"]
    auth = base64.b64encode(f"{c['client_id']}:{c['client_secret']}".encode()).decode()
    data = request_json("POST", "https://accounts.spotify.com/api/token", service="Spotify sign-in",
                        headers={"Authorization": f"Basic {auth}"}, form={"grant_type": "client_credentials"})
    _token.update(value=data["access_token"], expires_at=time.time() + data["expires_in"] - 60, client_id=c["client_id"])
    return _token["value"]


def resolve_show(brand: Brand, show_id: str) -> str:
    """The brand's show by default; a named show only if it is the brand's or a listed competitor's."""
    own = brand.scope_id("spotify")
    if not show_id or show_id == own:
        return own
    if show_id in brand.competitor_ids("spotify"):
        return show_id
    raise ToolError(
        f"Show {show_id} is outside this brand's scope. Allowed: the brand's show {own}"
        + (f" and competitor shows {', '.join(brand.competitor_ids('spotify'))}" if brand.competitor_ids("spotify") else "")
        + ". Add a competitor to brand.yaml to research another show."
    )


def _api(brand: Brand, path: str, params: dict) -> dict:
    return get_json(f"https://api.spotify.com/v1{path}", params,
                    headers={"Authorization": f"Bearer {_get_token(brand)}"}, service="Spotify")


@server.tool()
def spotify_get_show(show_id: str = "", market: str = "US") -> dict:
    """Get the brand's podcast metadata: name, publisher, description, total episodes, languages.

    Args:
        show_id: Optional. Empty = the brand's show from brand.yaml. Only competitor shows listed in brand.yaml are allowed otherwise.
        market: Two-letter country code for availability, e.g. "US", "BG".
    """
    brand = load_brand()
    sid = resolve_show(brand, show_id)
    data = _api(brand, f"/shows/{sid}", {"market": market})
    return {
        "id": data.get("id"), "name": data.get("name"), "publisher": data.get("publisher"),
        "description": data.get("description"), "total_episodes": data.get("total_episodes"),
        "languages": data.get("languages"), "explicit": data.get("explicit"),
        "media_type": data.get("media_type"), "external_url": data.get("external_urls", {}).get("spotify"),
        "is_brand_show": sid == brand.scope_id("spotify"),
    }


@server.tool()
def spotify_get_show_episodes(show_id: str = "", limit: int = 20, offset: int = 0, market: str = "US") -> dict:
    """List the brand's podcast episodes, newest first: name, release date, duration, description.

    Args:
        show_id: Optional. Empty = the brand's show from brand.yaml.
        limit: 1–50 episodes per page.
        offset: Episodes to skip, for paging.
        market: Two-letter country code, e.g. "US", "BG".
    """
    brand = load_brand()
    sid = resolve_show(brand, show_id)
    data = _api(brand, f"/shows/{sid}/episodes", {"limit": max(1, min(limit, 50)), "offset": offset, "market": market})
    episodes = [{
        "id": ep.get("id"), "name": ep.get("name"), "release_date": ep.get("release_date"),
        "duration_ms": ep.get("duration_ms"), "description": ep.get("description"),
        "external_url": ep.get("external_urls", {}).get("spotify"),
    } for ep in data.get("items", []) if ep]
    return {"show_id": sid, "total": data.get("total"), "episodes": episodes}


if __name__ == "__main__":
    server.run()
