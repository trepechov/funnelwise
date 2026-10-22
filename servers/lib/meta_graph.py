"""Meta Graph API reads for the Instagram and Facebook servers.

One credential covers both: meta.json {"access_token": …}, ideally a System
User token from Meta Business Settings (never expires; scoped to the Pages and
Instagram accounts the business assigned to it). The single-brand repo's
facebook.json / instagram.json are read as fallbacks.

Page insights and post insights need a Page token. It is derived at run time
for the brand's Page only (GET /{page_id}?fields=access_token) and kept in
memory; other Pages the token can see are never listed or stored.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

from lib.credentials import is_placeholder
from lib.mcp_stdio import ToolError
from lib.workspace import Brand

GRAPH = "https://graph.facebook.com/v25.0"
TIMEOUT = 60
GUIDE = "reference/connector-guides/meta.md"
PERMISSIONS = "instagram_basic, instagram_manage_insights, pages_show_list, pages_read_engagement, read_insights"
_page_tokens = {}  # type: Dict[Tuple[str, str], str]
_ig_ids = {}  # type: Dict[Tuple[str, str], str]


class GraphError(ToolError):
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


def user_token(brand: Brand) -> str:
    for name in ("meta.json", "facebook.json", "instagram.json"):
        path = brand.credential(name)
        if not path.is_file():
            continue
        try:
            token = json.loads(path.read_text(encoding="utf-8")).get("access_token", "")
        except ValueError:
            raise ToolError(f"{path} is not valid JSON: check the quotes and commas.")
        if token and not is_placeholder(token):
            return token.strip()
        raise ToolError(f"The Meta token in {path} is not filled in yet: replace the <paste …> text and save.")
    raise ToolError("Instagram and Facebook are not set up yet: run fw_prepare_credentials for instagram and paste "
                    f"a Meta System User token into the file it creates (guide: {GUIDE}).")


def _explain(err: dict, status: int) -> GraphError:
    code, msg = int(err.get("code") or 0), str(err.get("message") or "")[:300]
    if code == 190:
        return GraphError("The Meta token is invalid or expired (" + msg + "). Create a new System User token "
                          f"and paste it into meta.json (guide: {GUIDE}).", code)
    if code == 10 or 200 <= code < 300:
        return GraphError(f"The Meta token is missing a permission ({msg}). Generate it again with: {PERMISSIONS}.", code)
    if code in (4, 17, 32, 613):
        return GraphError("Meta's rate limit was reached; try again in a few minutes.", code)
    return GraphError(f"Meta API error {code or status}: {msg}", code)


def get(path: str, params: dict, token: str) -> dict:
    url = f"{GRAPH}/{path.lstrip('/')}?" + urllib.parse.urlencode({**params, "access_token": token})
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
        except ValueError:
            err = {}
        raise _explain(err, e.code) from None
    except urllib.error.URLError as e:
        raise ToolError(f"Could not reach Meta: {e.reason}. Check the internet connection.")


def page_token(brand: Brand, page_id: str) -> str:
    token = user_token(brand)
    key = (token[-16:], page_id)
    if key not in _page_tokens:
        data = get(page_id, {"fields": "access_token"}, token)
        if not data.get("access_token"):
            raise ToolError(f"The Meta token has no access to the brand's Page {page_id}. In Meta Business Settings → "
                            "System users, assign this Page to the system user, then generate the token again.")
        _page_tokens[key] = data["access_token"]
    return _page_tokens[key]


def instagram_account(brand: Brand) -> str:
    """The Instagram business account ID for brand.yaml's username; refuses any other account."""
    block = brand.connector("instagram")
    username = brand.scope_id("instagram").lstrip("@").lower()
    token = user_token(brand)
    key = (token[-16:], username)
    if key in _ig_ids:
        return _ig_ids[key]
    candidates = []  # type: List[str]
    if block.get("business_account_id"):
        candidates = [str(block["business_account_id"])]
    else:
        page_id = (brand.connectors.get("facebook") or {}).get("page_id")
        pages = [{"id": str(page_id)}] if page_id else get("me/accounts", {"fields": "id", "limit": 100}, token).get("data", [])
        for p in pages:
            ig = get(p["id"], {"fields": "instagram_business_account"}, token).get("instagram_business_account")
            if ig:
                candidates.append(ig["id"])
    for ig_id in candidates:
        if get(ig_id, {"fields": "username"}, token).get("username", "").lower() == username:
            _ig_ids[key] = ig_id
            return ig_id
    raise ToolError(f"The Meta token can't see the Instagram account @{username}. It must be a Business or Creator "
                    "account linked to the brand's Facebook Page, and assigned to the system user (guide: "
                    f"{GUIDE}).")


def insights(object_id: str, metrics: List[str], params: dict, token: str) -> Tuple[List[dict], List[str]]:
    """Fetch insights; a metric Meta doesn't offer for this object is returned in `unavailable`, not raised."""
    try:
        return get(f"{object_id}/insights", {**params, "metric": ",".join(metrics)}, token).get("data", []), []
    except GraphError as e:
        if e.code != 100:
            raise
    if len(metrics) == 1:
        return [], metrics
    data, unavailable = [], []
    for m in metrics:
        try:
            data += get(f"{object_id}/insights", {**params, "metric": m}, token).get("data", [])
        except GraphError as e:
            if e.code != 100:
                raise
            unavailable.append(m)
    return data, unavailable


def day_range(date_from: str, date_to: str, max_days: int) -> List[Tuple[int, int]]:
    """Split YYYY-MM-DD..YYYY-MM-DD (inclusive) into Graph `since`/`until` windows of at most max_days."""
    try:
        start = int(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
        end = int(time.mktime(time.strptime(date_to, "%Y-%m-%d"))) + 86400
    except ValueError:
        raise ToolError("Dates must be YYYY-MM-DD.")
    if end <= start:
        raise ToolError("date_from must be on or before date_to.")
    windows, step = [], max_days * 86400
    while start < end:
        windows.append((start, min(start + step, end)))
        start += step
    return windows


def page_of(data: dict) -> Optional[str]:
    """The `after` cursor for the next page, or None."""
    if not (data.get("paging") or {}).get("next"):
        return None
    return ((data.get("paging") or {}).get("cursors") or {}).get("after")
