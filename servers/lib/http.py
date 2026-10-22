"""Tiny JSON-over-HTTPS helpers with error messages a marketer can act on."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from lib.mcp_stdio import ToolError

TIMEOUT = 60


def request_json(method: str, url: str, *, headers: Optional[dict] = None, body: Optional[dict] = None,
                 form: Optional[dict] = None, service: str = "API") -> dict:
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except ValueError:
            detail = raw.decode("utf-8", "replace")[:300]
        raise ToolError(f"{service} returned HTTP {e.code}: {_short(detail)}{_hint(e.code)}")
    except urllib.error.URLError as e:
        raise ToolError(f"Could not reach {service}: {e.reason}. Check the internet connection.")
    return json.loads(raw) if raw else {}


def get_json(url: str, params: Optional[dict] = None, **kw) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return request_json("GET", url, **kw)


def post_json(url: str, body: dict, **kw) -> dict:
    return request_json("POST", url, body=body, **kw)


def _short(detail: object) -> str:
    if isinstance(detail, dict):
        err = detail.get("error", detail)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("status") or err)[:300]
        return str(err)[:300]
    return str(detail)[:300]


def _hint(code: int) -> str:
    if code == 401:
        return " (the credential is invalid or expired; run the connection check for next steps)"
    if code == 403:
        return " (the credential has no access to this account/property; see the connector guide)"
    if code == 429:
        return " (rate limit; try again in a minute)"
    return ""
