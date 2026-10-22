#!/usr/bin/env python3
"""Read-only YouTube server: Data API v3 (public numbers) and Analytics API v2.

Every call names brand.yaml connectors.youtube.channel_id (or a competitor's
channel for public numbers); nothing uses `mine`, which resolves to whoever
signed in rather than the brand. Scopes are read-only: youtube.readonly and
yt-analytics.readonly.

Sign-in without a terminal (same pattern as TikTok): youtube_login_start opens
a loopback listener and returns a Google link. Google OAuth client of type
"Desktop app" in client_secret.json, PKCE (S256). The sign-in is saved only if
the signed-in account can read the brand channel's Analytics, which catches the
Brand Account gotcha (a Studio Editor's sign-in sees only their own channel).

Google apps left in "Testing" mode end every sign-in after 7 days. Google
then reports `refresh_token_expires_in` with the token: the login tools say
so at once, and an expired sign-in explains how to publish the app.

CLI (developer path): youtube.py auth | auth-url | auth-finish '<url>'
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib.credentials import is_placeholder  # noqa: E402
from lib.google_auth import TOKEN_URI, expired_signin, refresh_token_access  # noqa: E402
from lib.http import get_json, request_json  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, load_brand  # noqa: E402

DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly"
REDIRECT_PORT = 3456
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/"
LOGIN_TIMEOUT = 600
SHORT_MAX_SECONDS = 180  # Shorts can be up to 3 minutes since October 2024
RELOGIN = "run youtube_login_start and sign in as an Owner or Manager of the brand's channel"
TESTING_MODE = ("Google says this sign-in ends in {days} days: the Google Cloud app is in Testing mode. Fix it now: "
                "Google Cloud console → Google Auth Platform → Audience → Publishing status → Publish app "
                "(\"In production\"; no verification needed for the brand's own use), then sign in again. "
                "Otherwise YouTube disconnects every week.")
DEFAULT_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained",
                   "subscribersLost", "likes", "comments", "shares"]


class Account:
    """OAuth client and token paths for the active brand."""

    def __init__(self, brand: Brand):
        self.brand = brand
        self.channel_id = brand.scope_id("youtube")
        self.token_file = brand.credential("token.json")
        self.pending_file = brand.credential("youtube_login.json.pending")
        path = brand.credential("client_secret.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            client = data.get("installed") or data.get("web") or {}
            self.client_id, self.client_secret = client["client_id"], client["client_secret"]
            self.token_uri = client.get("token_uri", TOKEN_URI)
        except FileNotFoundError:
            raise ToolError(f"No Google sign-in client yet ({path}). Run fw_prepare_credentials youtube and fill it "
                            "in (guide: reference/connector-guides/youtube.md).")
        except (KeyError, ValueError):
            raise ToolError(f"{path} must be a Google OAuth client file of type Desktop app.")
        if is_placeholder(self.client_id) or is_placeholder(self.client_secret):
            raise ToolError(f"{path} still has <paste …> placeholders: fill in the Client ID and secret and save.")


def _read_token(acct: Account) -> dict:
    try:
        return json.loads(acct.token_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"YouTube is not signed in yet: {RELOGIN}.")


def _access_token(acct: Account) -> str:
    token = _read_token(acct)
    expires_at = token.get("refresh_token_expires_at")
    if expires_at and time.time() >= expires_at:
        raise expired_signin(RELOGIN)
    return refresh_token_access(acct.client_id, acct.client_secret, token["refresh_token"], acct.token_uri, RELOGIN)


def _get(acct: Account, url: str, params: dict, token: str = "") -> dict:
    return get_json(url, params, service="YouTube", headers={"Authorization": f"Bearer {token or _access_token(acct)}"})


def resolve_channel(brand: Brand, channel_id: str) -> str:
    """The brand's channel by default; another only if it is a listed competitor (public numbers)."""
    own = brand.scope_id("youtube")
    if not channel_id or channel_id == own:
        return own
    if channel_id in brand.competitor_ids("youtube"):
        return channel_id
    raise ToolError(f"Channel {channel_id} is outside this brand's scope. Allowed: the brand's channel {own}"
                    + (f" and competitor channels {', '.join(brand.competitor_ids('youtube'))}"
                       if brand.competitor_ids("youtube") else "")
                    + ". Add a competitor to brand.yaml to research another channel.")


def _seconds(iso: str) -> int:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def _video(v: dict) -> dict:
    stats, snippet = v.get("statistics", {}), v.get("snippet", {})
    seconds = _seconds(v.get("contentDetails", {}).get("duration", ""))
    if "liveStreamingDetails" in v:
        fmt = "live"
    else:
        fmt = "short" if 0 < seconds <= SHORT_MAX_SECONDS else "long"
    return {"id": v["id"], "title": snippet.get("title"), "published": snippet.get("publishedAt"),
            "channel_id": snippet.get("channelId"), "duration_seconds": seconds, "format": fmt,
            "views": int(stats.get("viewCount", 0)), "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0))}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _authorize_url(acct: Account, verifier: str, state: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": acct.client_id, "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": _challenge(verifier), "code_challenge_method": "S256",
    })


def _save_token(acct: Account, data: dict) -> dict:
    now = time.time()
    token = {"refresh_token": data["refresh_token"], "token_uri": acct.token_uri, "scopes": data.get("scope", SCOPES).split(),
             "signed_in_at": now}
    if data.get("refresh_token_expires_in"):
        token["refresh_token_expires_at"] = now + int(data["refresh_token_expires_in"])
    acct.token_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(acct.token_file) + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(token, f, indent=2)
    tmp.replace(acct.token_file)
    return token


def _finish_login(acct: Account, result: dict, state: str, verifier: str) -> dict:
    if "error" in result:
        raise ToolError(f"Google sign-in failed: {result['error']}.")
    if result.get("state") != state:
        raise ToolError("Google sign-in failed: the link was from an older sign-in attempt. Start again.")
    data = request_json("POST", acct.token_uri, service="Google sign-in", form={
        "client_id": acct.client_id, "client_secret": acct.client_secret, "code": result["code"],
        "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
    })
    if not data.get("refresh_token"):
        raise ToolError("Google returned no lasting sign-in. Remove Funnelwise's access at myaccount.google.com → "
                        "Security → Third-party connections, then start again.")
    token = data["access_token"]
    today = time.strftime("%Y-%m-%d")
    try:
        _get(acct, ANALYTICS_API, {"ids": f"channel=={acct.channel_id}", "startDate": today, "endDate": today,
                                   "metrics": "views"}, token)
    except ToolError:
        own = _get(acct, f"{DATA_API}/channels", {"part": "snippet", "mine": "true"}, token).get("items") or [{}]
        who = own[0].get("snippet", {}).get("title", "an account without a channel")
        raise ToolError(f"Signed in as \"{who}\", which can't read the Analytics of the brand's channel "
                        f"{acct.channel_id}. Nothing was saved. Sign in again choosing the brand's channel (Brand "
                        "Account); the person needs to be its Owner or Manager, not only a Studio Editor.")
    saved = _save_token(acct, data)
    channel = _get(acct, f"{DATA_API}/channels", {"part": "snippet,statistics", "id": acct.channel_id}, token)["items"][0]
    out = {"signed_in": True, "channel": channel["snippet"]["title"],
           "subscribers": int(channel["statistics"].get("subscriberCount", 0))}
    if saved.get("refresh_token_expires_at"):
        out["warning"] = TESTING_MODE.format(days=round((saved["refresh_token_expires_at"] - time.time()) / 86400))
    return out


def _new_pending(acct: Account) -> dict:
    pending = {"verifier": secrets.token_urlsafe(64), "state": secrets.token_urlsafe(16), "created": time.time()}
    acct.pending_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(acct.pending_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(pending, f)
    return pending


_listener = {"thread": None, "result": None, "error": None}


def _listen(acct: Account, pending: dict) -> None:
    captured = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if "code" in query or "error" in query:
                captured.update(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Google sign-in received. You can close this tab and go back to Claude.".encode())

        def log_message(self, *args):
            pass

    try:
        httpd = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    except OSError:
        _listener["error"] = f"Port {REDIRECT_PORT} is busy; use the remote option (youtube_login_finish)."
        return
    httpd.timeout = 2
    deadline = time.time() + LOGIN_TIMEOUT
    while not captured and time.time() < deadline:
        httpd.handle_request()
    httpd.server_close()
    if not captured:
        _listener["error"] = "Sign-in timed out after 10 minutes. Start again."
        return
    try:
        _listener["result"] = _finish_login(acct, captured, pending["state"], pending["verifier"])
        acct.pending_file.unlink(missing_ok=True)
    except ToolError as e:
        _listener["error"] = str(e)


server = Server("funnelwise-youtube", instructions=(
    "YouTube data for the brand's channel only (brand.yaml), plus public numbers of competitor channels listed "
    "there. Never pass mine=true. Analytics (watch time, retention, traffic sources, demographics) needs the "
    "one-time sign-in by the channel's Owner or Manager (youtube_login_start)."
))


@server.tool()
def youtube_login_start() -> dict:
    """Start the one-time Google sign-in for the brand's YouTube channel. Returns a link to open. Opened on
    this computer, the sign-in completes by itself; check with youtube_login_status. If the channel owner is
    elsewhere, send them the link and complete it with youtube_login_finish."""
    acct = Account(load_brand())
    pending = _new_pending(acct)
    _listener.update(result=None, error=None)
    t = threading.Thread(target=_listen, args=(acct, pending), daemon=True)
    _listener["thread"] = t
    t.start()
    return {
        "login_link": _authorize_url(acct, pending["verifier"], pending["state"]),
        "sign_in_as": f"an Owner or Manager of channel {acct.channel_id}; choose the brand's channel if Google asks",
        "same_computer": "Open the link, sign in and allow. If Google warns the app isn't verified, choose "
                         "Advanced → continue (it is the brand's own app). Then call youtube_login_status.",
        "other_computer": ("Send the link to the channel owner. After allowing, their browser shows a page that fails "
                           f"to load at {REDIRECT_URI}?…code=… They copy that full address and send it back; pass it "
                           "to youtube_login_finish within a few minutes."),
    }


@server.tool()
def youtube_login_status() -> dict:
    """Whether the YouTube sign-in has finished, and whether it will expire (Google app in Testing mode)."""
    acct = Account(load_brand())
    if _listener["result"]:
        return _listener["result"]
    if _listener["error"]:
        return {"signed_in": False, "error": _listener["error"]}
    if acct.token_file.is_file():
        token = _read_token(acct)
        out = {"signed_in": True}
        if token.get("refresh_token_expires_at"):
            days = (token["refresh_token_expires_at"] - time.time()) / 86400
            out["warning"] = TESTING_MODE.format(days=max(0, round(days))) if days > 0 else str(expired_signin(RELOGIN))
        return out
    t = _listener["thread"]
    return {"signed_in": False, "waiting": bool(t and t.is_alive())}


@server.tool()
def youtube_login_finish(redirected_url: str) -> dict:
    """Complete a YouTube sign-in done on another computer.

    Args:
        redirected_url: The full http://127.0.0.1:3456/?…code=… address the owner's browser landed on.
    """
    acct = Account(load_brand())
    try:
        pending = json.loads(acct.pending_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError("No sign-in in progress. Run youtube_login_start first.")
    result = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(redirected_url.strip()).query))
    if "code" not in result and "error" not in result:
        raise ToolError("That address has no code= in it. Ask for the full contents of the address bar.")
    out = _finish_login(acct, result, pending["state"], pending["verifier"])
    acct.pending_file.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@server.tool()
def youtube_channel(channel_id: str = "") -> dict:
    """Get a channel's public numbers: title, handle, subscribers (rounded by YouTube), total views, video count.

    Args:
        channel_id: Optional. Empty = the brand's channel. Otherwise only competitor channels in brand.yaml.
    """
    brand = load_brand()
    cid = resolve_channel(brand, channel_id)
    items = _get(Account(brand), f"{DATA_API}/channels", {"part": "snippet,statistics,contentDetails", "id": cid}).get("items")
    if not items:
        raise ToolError(f"YouTube has no channel {cid}. Check the channel ID (it starts with UC) in brand.yaml.")
    c = items[0]
    s = c.get("statistics", {})
    return {"id": cid, "title": c["snippet"].get("title"), "handle": c["snippet"].get("customUrl"),
            "subscribers": int(s.get("subscriberCount", 0)), "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)), "created": c["snippet"].get("publishedAt"),
            "is_brand_channel": cid == brand.scope_id("youtube")}


@server.tool()
def youtube_list_videos(max_results: int = 25, page_token: str = "", channel_id: str = "") -> dict:
    """List a channel's uploads, newest first, with views, likes, comments, duration and format
    (long / short ≤ 3 min / live).

    Args:
        max_results: 1–50 videos per page.
        page_token: The `next_page_token` from the previous page.
        channel_id: Optional. Empty = the brand's channel. Otherwise only competitor channels in brand.yaml.
    """
    brand = load_brand()
    cid = resolve_channel(brand, channel_id)
    acct = Account(brand)
    uploads = "UU" + cid[2:]  # the uploads playlist of channel UC…
    params = {"part": "contentDetails", "playlistId": uploads, "maxResults": max(1, min(max_results, 50))}
    if page_token:
        params["pageToken"] = page_token
    page = _get(acct, f"{DATA_API}/playlistItems", params)
    ids = [i["contentDetails"]["videoId"] for i in page.get("items", [])]
    videos = []
    if ids:
        videos = _get(acct, f"{DATA_API}/videos", {"part": "snippet,statistics,contentDetails,liveStreamingDetails",
                                                   "id": ",".join(ids)}).get("items", [])
    return {"channel_id": cid, "videos": [_video(v) for v in videos], "next_page_token": page.get("nextPageToken")}


@server.tool()
def youtube_get_videos(video_ids: List[str]) -> dict:
    """Current numbers for specific videos (up to 50) of the brand's or a listed competitor's channel.

    Args:
        video_ids: Video IDs, e.g. from youtube_list_videos.
    """
    brand = load_brand()
    allowed = {brand.scope_id("youtube"), *brand.competitor_ids("youtube")}
    items = _get(Account(brand), f"{DATA_API}/videos", {"part": "snippet,statistics,contentDetails,liveStreamingDetails",
                                                        "id": ",".join(video_ids[:50])}).get("items", [])
    videos = [_video(v) for v in items]
    refused = [v["id"] for v in videos if v["channel_id"] not in allowed]
    return {"videos": [v for v in videos if v["channel_id"] in allowed],
            **({"refused_other_channels": refused} if refused else {})}


@server.tool()
def youtube_analytics(date_from: str, date_to: str, metrics: Optional[List[str]] = None, dimensions: str = "",
                      sort: str = "", max_results: int = 25, filters: str = "") -> dict:
    """YouTube Analytics report for the brand's channel (needs the owner/manager sign-in).

    Args:
        date_from: YYYY-MM-DD.
        date_to: YYYY-MM-DD (data lags 1–2 days).
        metrics: Default views, estimatedMinutesWatched, averageViewDuration, subscribersGained, subscribersLost,
            likes, comments, shares. Others: averageViewPercentage, cardClicks, viewerPercentage (with ageGroup/gender).
        dimensions: Optional, e.g. "day", "video", "insightTrafficSourceType", "country", "ageGroup,gender",
            "deviceType", "creatorContentType".
        sort: Optional, e.g. "-views" (needed with dimension video).
        max_results: Row limit for dimension video or country.
        filters: Optional, e.g. "video==abc123" or "country==BG".
    """
    for d in (date_from, date_to):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            raise ToolError("Dates must be YYYY-MM-DD.")
    brand = load_brand()
    acct = Account(brand)
    params = {"ids": f"channel=={acct.channel_id}", "startDate": date_from, "endDate": date_to,
              "metrics": ",".join(metrics or DEFAULT_METRICS)}
    for key, value in (("dimensions", dimensions), ("sort", sort), ("filters", filters)):
        if value:
            params[key] = value
    if dimensions:
        params["maxResults"] = max(1, min(max_results, 200))
    try:
        data = _get(acct, ANALYTICS_API, params)
    except ToolError as e:
        if "403" in str(e):
            raise ToolError("The saved sign-in can't read this channel's Analytics: the person who signed in is not "
                            f"an Owner or Manager of it. {RELOGIN[0].upper() + RELOGIN[1:]}.") from None
        raise
    names = [h["name"] for h in data.get("columnHeaders", [])]
    return {"channel_id": acct.channel_id, "period": {"from": date_from, "to": date_to},
            "rows": [dict(zip(names, r)) for r in data.get("rows", [])]}


def _cli(args: List[str]) -> None:
    acct = Account(load_brand())
    if args == ["auth"]:
        import webbrowser
        pending = _new_pending(acct)
        url = _authorize_url(acct, pending["verifier"], pending["state"])
        print(f"Opening Google sign-in for channel {acct.channel_id}.\nIf it doesn't open, visit:\n{url}\n")
        webbrowser.open(url)
        _listen(acct, pending)
        print(_listener["result"] or _listener["error"])
    elif args == ["auth-url"]:
        pending = _new_pending(acct)
        print(f"Send this link to an Owner/Manager of {acct.channel_id}:\n\n"
              f"{_authorize_url(acct, pending['verifier'], pending['state'])}\n\n"
              "Then run: youtube.py auth-finish '<the 127.0.0.1 URL they send back>'")
    elif len(args) == 2 and args[0] == "auth-finish":
        print(youtube_login_finish(args[1]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if sys.argv[1:]:
        try:
            _cli(sys.argv[1:])
        except ToolError as e:
            sys.exit(str(e))
    else:
        server.run()
