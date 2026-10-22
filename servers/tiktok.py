#!/usr/bin/env python3
"""Read-only TikTok server for the official Display API (v2).

Returns the authorized account's own profile stats and per-video
views/likes/comments/shares; there is no period analytics and no access to
other creators. The OAuth token belongs to one TikTok account, so the API
itself scopes results; login additionally refuses any account other than
brand.yaml connectors.tiktok.username.

The developer app can stay in Sandbox mode (no App Review) with the brand's
account added as a target user. Login uses Login Kit for Desktop: PKCE with a
*hex*-encoded SHA256 challenge (TikTok-specific) and a loopback redirect URI.

Login without a terminal: tiktok_login_start opens a local listener and
returns the link; when the account owner logs in on this computer the token
is saved automatically. If they log in elsewhere, they send back the
localhost address their browser lands on and tiktok_login_finish completes it.

CLI (developer path): tiktok.py auth | auth-url | auth-finish '<url>'
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
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
from lib.http import request_json  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, load_brand  # noqa: E402

API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list"
# Must be registered verbatim under the app's Login Kit > Desktop redirect URIs.
REDIRECT_PORT = 3455
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback/"
LOGIN_TIMEOUT = 600
USER_FIELDS = ("open_id,display_name,username,bio_description,is_verified,"
               "profile_deep_link,follower_count,following_count,likes_count,video_count")
VIDEO_FIELDS = ("id,title,video_description,create_time,duration,share_url,"
                "view_count,like_count,comment_count,share_count")


class Account:
    """Credentials and token paths for the active brand."""

    def __init__(self, brand: Brand):
        self.brand = brand
        self.username = brand.scope_id("tiktok").lstrip("@")
        self.token_file = brand.credential("tiktok_token.json")
        self.pending_file = brand.credential("tiktok_token.json.pending")
        path = brand.credential("tiktok.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.client_key, self.client_secret = data["client_key"], data["client_secret"]
        except FileNotFoundError:
            raise ToolError(f"No TikTok app credentials yet ({path}). See reference/connector-guides/tiktok.md.")
        except (KeyError, ValueError):
            raise ToolError(f"{path} must contain client_key and client_secret.")


def _token_request(fields: dict) -> dict:
    data = request_json("POST", f"{API}/oauth/token/", form=fields, service="TikTok sign-in")
    if "access_token" not in data:
        raise ToolError(f"TikTok sign-in failed: {data.get('error')}: {data.get('error_description')}")
    return data


def _save_token(acct: Account, data: dict) -> dict:
    now = time.time()
    token = {
        "access_token": data["access_token"], "refresh_token": data["refresh_token"],
        "open_id": data.get("open_id"), "scope": data.get("scope"),
        "expires_at": now + data["expires_in"] - 60, "refresh_expires_at": now + data["refresh_expires_in"],
    }
    acct.token_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(acct.token_file) + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(token, f, indent=2)
    tmp.replace(acct.token_file)
    return token


def _access_token(acct: Account) -> str:
    try:
        token = json.loads(acct.token_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"TikTok is not signed in yet. Run tiktok_login_start and log in as @{acct.username}.")
    if time.time() < token["expires_at"]:
        return token["access_token"]
    if time.time() >= token["refresh_expires_at"]:
        raise ToolError(f"The TikTok sign-in expired (after 365 days). Run tiktok_login_start again as @{acct.username}.")
    # Access tokens last 24h; refresh tokens 365d and may rotate on refresh.
    token = _save_token(acct, _token_request({
        "client_key": acct.client_key, "client_secret": acct.client_secret,
        "grant_type": "refresh_token", "refresh_token": token["refresh_token"],
    }))
    return token["access_token"]


def _api(acct: Account, method: str, path: str, fields: str, body: Optional[dict] = None, token: str = "") -> dict:
    url = f"{API}{path}?{urllib.parse.urlencode({'fields': fields})}"
    data = request_json(method, url, body=body, service="TikTok",
                        headers={"Authorization": f"Bearer {token or _access_token(acct)}"})
    err = data.get("error", {})
    if err.get("code") != "ok":
        raise ToolError(f"TikTok API error: {err.get('code')}: {err.get('message')} (log_id {err.get('log_id')})")
    return data["data"]


def _video(v: dict) -> dict:
    return {**v, "create_time": time.strftime("%Y-%m-%d %H:%M", time.gmtime(v["create_time"])) + " UTC"}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def _authorize_url(acct: Account, verifier: str, state: str) -> str:
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": acct.client_key, "response_type": "code", "scope": SCOPES,
        "redirect_uri": REDIRECT_URI, "state": state,
        "code_challenge": hashlib.sha256(verifier.encode()).hexdigest(), "code_challenge_method": "S256",
    })


def _finish_login(acct: Account, result: dict, state: str, verifier: str) -> dict:
    if "error" in result:
        raise ToolError(f"TikTok login failed: {result['error']}: {result.get('error_description')}")
    if result.get("state") != state:
        raise ToolError("TikTok login failed: the link was from an older login attempt. Start again.")
    data = _token_request({
        "client_key": acct.client_key, "client_secret": acct.client_secret, "code": result["code"],
        "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
    })
    user = _api(acct, "GET", "/user/info/", "username,display_name,follower_count", token=data["access_token"])["user"]
    if user["username"].lower() != acct.username.lower():
        raise ToolError(f"Wrong TikTok account: logged in as @{user['username']}, but this brand is @{acct.username}. "
                        "Nothing was saved. Log out of TikTok in the browser and try again.")
    _save_token(acct, data)
    return {"signed_in_as": f"@{user['username']}", "display_name": user["display_name"],
            "followers": user["follower_count"]}


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
            self.wfile.write("TikTok login received. You can close this tab and go back to Claude.".encode())

        def log_message(self, *args):
            pass

    try:
        httpd = http.server.HTTPServer(("localhost", REDIRECT_PORT), Handler)
    except OSError:
        _listener["error"] = f"Port {REDIRECT_PORT} is busy; use the remote option (tiktok_login_finish)."
        return
    httpd.timeout = 2
    deadline = time.time() + LOGIN_TIMEOUT
    while not captured and time.time() < deadline:
        httpd.handle_request()
    httpd.server_close()
    if not captured:
        _listener["error"] = "Login timed out after 10 minutes. Start again."
        return
    try:
        _listener["result"] = _finish_login(acct, captured, pending["state"], pending["verifier"])
        acct.pending_file.unlink(missing_ok=True)
    except ToolError as e:
        _listener["error"] = str(e)


server = Server("funnelwise-tiktok", instructions=(
    "TikTok Display API data for the brand's own account only: profile stats and per-video totals. "
    "There are no views-by-day, audience or other creators' data in this API."
))


@server.tool()
def tiktok_login_start() -> dict:
    """Start the one-time TikTok sign-in for the brand's account. Returns a link to open. If it is opened on
    this computer, the sign-in completes by itself; check with tiktok_login_status. If the account owner is
    elsewhere, send them the link and complete it with tiktok_login_finish."""
    acct = Account(load_brand())
    pending = _new_pending(acct)
    _listener.update(result=None, error=None)
    t = threading.Thread(target=_listen, args=(acct, pending), daemon=True)
    _listener["thread"] = t
    t.start()
    return {
        "login_link": _authorize_url(acct, pending["verifier"], pending["state"]),
        "log_in_as": f"@{acct.username}",
        "same_computer": "Open the link, log in and approve. Then call tiktok_login_status.",
        "other_computer": ("Send the link to the account owner. After approving, their browser shows a page that "
                           "fails to load at http://localhost:3455/callback/?code=… They copy that full address "
                           "and send it back; pass it to tiktok_login_finish within a few minutes."),
    }


@server.tool()
def tiktok_login_status() -> dict:
    """Whether the TikTok sign-in started with tiktok_login_start has finished, and for which account."""
    acct = Account(load_brand())
    if _listener["result"]:
        return {"signed_in": True, **_listener["result"]}
    if _listener["error"]:
        return {"signed_in": False, "error": _listener["error"]}
    if acct.token_file.is_file():
        return {"signed_in": True, "token_file": str(acct.token_file)}
    t = _listener["thread"]
    return {"signed_in": False, "waiting": bool(t and t.is_alive())}


@server.tool()
def tiktok_login_finish(redirected_url: str) -> dict:
    """Complete a TikTok sign-in done on another computer.

    Args:
        redirected_url: The full http://localhost:3455/callback/?code=… address the account owner's browser landed on.
    """
    acct = Account(load_brand())
    try:
        pending = json.loads(acct.pending_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError("No sign-in in progress. Run tiktok_login_start first.")
    result = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(redirected_url.strip()).query))
    if "code" not in result and "error" not in result:
        raise ToolError("That address has no ?code= in it. Ask for the full contents of the address bar.")
    out = _finish_login(acct, result, pending["state"], pending["verifier"])
    acct.pending_file.unlink(missing_ok=True)
    return out


@server.tool()
def tiktok_get_profile() -> dict:
    """Get the brand's TikTok profile and lifetime stats: followers, following, total likes, video count."""
    acct = Account(load_brand())
    return _api(acct, "GET", "/user/info/", USER_FIELDS)["user"]


@server.tool()
def tiktok_list_videos(max_count: int = 10, cursor: Optional[int] = None) -> dict:
    """List the brand's public TikTok videos, newest first, with views, likes, comments and shares.

    Args:
        max_count: Up to 20 per page (TikTok's limit).
        cursor: The `cursor` from the previous page, to page further back.
    """
    acct = Account(load_brand())
    body = {"max_count": max(1, min(max_count, 20))}
    if cursor is not None:
        body["cursor"] = cursor
    data = _api(acct, "POST", "/video/list/", VIDEO_FIELDS, body)
    return {"videos": [_video(v) for v in data.get("videos", [])], "cursor": data.get("cursor"),
            "has_more": data.get("has_more")}


@server.tool()
def tiktok_get_videos(video_ids: List[str]) -> dict:
    """Get current stats for specific videos of the brand's account by ID (up to 20).

    Args:
        video_ids: Video IDs from tiktok_list_videos.
    """
    acct = Account(load_brand())
    data = _api(acct, "POST", "/video/query/", VIDEO_FIELDS, {"filters": {"video_ids": video_ids[:20]}})
    return {"videos": [_video(v) for v in data.get("videos", [])]}


def _cli(args: List[str]) -> None:
    acct = Account(load_brand())
    if args == ["auth"]:
        import webbrowser
        pending = _new_pending(acct)
        url = _authorize_url(acct, pending["verifier"], pending["state"])
        print(f"Opening TikTok login. Log in as @{acct.username}.\nIf it doesn't open, visit:\n{url}\n")
        webbrowser.open(url)
        _listen(acct, pending)
        print(_listener["result"] or _listener["error"])
    elif args == ["auth-url"]:
        pending = _new_pending(acct)
        print(f"Send this link to the owner of @{acct.username}:\n\n{_authorize_url(acct, pending['verifier'], pending['state'])}\n\n"
              "Then run: tiktok.py auth-finish '<the localhost URL they send back>'")
    elif len(args) == 2 and args[0] == "auth-finish":
        print(tiktok_login_finish(args[1]))
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
