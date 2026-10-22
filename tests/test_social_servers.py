"""YouTube, Instagram and Facebook servers, credential templates and the secret guard."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import time
import urllib.parse

import pytest

import core
import facebook
import instagram
import youtube
from conftest import write_creds
from lib import google_auth
from lib import meta_graph as graph
from lib.mcp_stdio import ToolError
from lib.workspace import load_brand
from secret_guard import decide as secret_decide
from write_guard import is_write_tool

CLIENT = {"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "cs",
                        "token_uri": "https://oauth2.googleapis.com/token"}}


@pytest.fixture(autouse=True)
def clear_caches():
    graph._page_tokens.clear()
    graph._ig_ids.clear()
    google_auth._cache.clear()
    youtube._listener.update(thread=None, result=None, error=None)


# --- servers have read tools only ------------------------------------------

@pytest.mark.parametrize("mod", [youtube, instagram, facebook])
def test_no_write_tools(mod):
    assert mod.server.tools and not [t for t in mod.server.tools if is_write_tool(t)]


# --- credential templates ----------------------------------------------------

def test_prepare_templates_and_status(brand_dir):
    out = core.fw_prepare_credentials("instagram", open_in_editor=False)
    path = brand_dir / ".credentials" / "meta.json"
    assert out["files"] == [{"file": str(path), "created": True, "to_fill": ["access_token"]}]
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["access_token"].startswith("<paste")
    status = core.fw_connection_status()["connectors"]["facebook"]["credentials"]
    assert status["ready"] is False and status["to_fill"] == {"meta.json": ["access_token"]}
    assert "replace the <paste" in status["next_steps"][0] and "EAA" not in json.dumps(status)

    data = json.loads(path.read_text())
    data["access_token"] = "EAAsecret"
    path.write_text(json.dumps(data))
    again = core.fw_prepare_credentials("facebook", open_in_editor=False)
    assert again["files"][0]["created"] is False and again["files"][0]["to_fill"] == []  # never overwritten
    assert json.loads(path.read_text())["access_token"] == "EAAsecret"
    assert core.fw_connection_status()["connectors"]["instagram"]["credentials"]["ready"] is True


def test_prepare_templates_youtube_and_google(brand_dir):
    out = core.fw_prepare_credentials("youtube", open_in_editor=False)
    assert out["files"][0]["to_fill"] == ["installed.client_id", "installed.client_secret"]
    with pytest.raises(ToolError, match="placeholders"):
        youtube.Account(load_brand())
    assert "fw_import_credential" in core.fw_prepare_credentials("ga4", open_in_editor=False)["note"]
    with pytest.raises(ToolError, match="No credential files"):
        core.fw_prepare_credentials("semrush")


# --- secret guard --------------------------------------------------------------

@pytest.mark.parametrize("tool,args", [
    ("Read", {"file_path": "/Users/a/Acme/.credentials/meta.json"}),
    ("Bash", {"command": "cat ~/.funnelwise/credentials/acme/token.json"}),
    ("Bash", {"command": "ls '/Users/a/Acme/.credentials'"}),
    ("Grep", {"pattern": "access_token", "path": ".credentials"}),
    ("Edit", {"file_path": "./.credentials/spotify.json", "old_string": "a", "new_string": "b"}),
])
def test_secret_guard_denies(tool, args):
    assert "out of the chat" in secret_decide({"tool_name": tool, "tool_input": args})


@pytest.mark.parametrize("tool,args", [
    ("Read", {"file_path": "/Users/a/Acme/brand.yaml"}),
    ("Bash", {"command": "pytest tests/test_credentials.py"}),
    ("Read", {"file_path": "/repo/servers/lib/credentials.py"}),
    ("mcp__plugin_funnelwise_funnelwise__fw_prepare_credentials", {"connector": ".credentials"}),
])
def test_secret_guard_allows(tool, args):
    assert secret_decide({"tool_name": tool, "tool_input": args}) is None


# --- Google sign-in expiry -----------------------------------------------------

def test_invalid_grant_explains_testing_mode(monkeypatch):
    def fail(*a, **k):
        raise ToolError("Google sign-in returned HTTP 400: invalid_grant")
    monkeypatch.setattr(google_auth, "request_json", fail)
    with pytest.raises(ToolError, match="Testing mode.*Publish app.*run youtube_login_start"):
        google_auth.refresh_token_access("c", "s", "r", how_to_sign_in_again="run youtube_login_start")


# --- YouTube ---------------------------------------------------------------------

def test_youtube_channel_scope(brand_dir):
    b = load_brand()
    assert youtube.resolve_channel(b, "") == "UCacme000000000000000000"
    assert youtube.resolve_channel(b, "UCtrail00000000000000000") == "UCtrail00000000000000000"  # competitor
    with pytest.raises(ToolError, match="outside this brand's scope"):
        youtube.resolve_channel(b, "UCsomeoneelse")


def test_youtube_not_set_up_messages(brand_dir):
    with pytest.raises(ToolError, match="fw_prepare_credentials youtube"):
        youtube.youtube_channel()
    write_creds(brand_dir, "client_secret.json", CLIENT)
    with pytest.raises(ToolError, match="not signed in yet"):
        youtube.youtube_channel()
    write_creds(brand_dir, "token.json", {"refresh_token": "r", "refresh_token_expires_at": time.time() - 1})
    with pytest.raises(ToolError, match="Testing mode"):
        youtube.youtube_channel()


def test_youtube_authorize_url_pkce(brand_dir):
    write_creds(brand_dir, "client_secret.json", CLIENT)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(
        youtube._authorize_url(youtube.Account(load_brand()), "verifier", "st")).query))
    assert q["code_challenge"] == base64.urlsafe_b64encode(hashlib.sha256(b"verifier").digest()).rstrip(b"=").decode()
    assert q["scope"] == youtube.SCOPES and "upload" not in q["scope"] and q["access_type"] == "offline"


def _token_response(**extra):
    return {"access_token": "at", "refresh_token": "rt", "expires_in": 3599, "scope": youtube.SCOPES, **extra}


def test_youtube_login_refuses_account_without_analytics(brand_dir, monkeypatch):
    write_creds(brand_dir, "client_secret.json", CLIENT)
    acct = youtube.Account(load_brand())
    monkeypatch.setattr(youtube, "request_json", lambda *a, **k: _token_response())

    def get(acct_, url, params, token=""):
        if url == youtube.ANALYTICS_API:
            raise ToolError("YouTube returned HTTP 403: Forbidden")
        assert params.get("mine") == "true"
        return {"items": [{"snippet": {"title": "Personal Channel"}}]}
    monkeypatch.setattr(youtube, "_get", get)
    with pytest.raises(ToolError, match="Signed in as \"Personal Channel\".*Nothing was saved"):
        youtube._finish_login(acct, {"code": "c", "state": "s"}, "s", "v")
    assert not acct.token_file.exists()


def test_youtube_login_warns_testing_mode(brand_dir, monkeypatch):
    write_creds(brand_dir, "client_secret.json", CLIENT)
    acct = youtube.Account(load_brand())
    monkeypatch.setattr(youtube, "request_json", lambda *a, **k: _token_response(refresh_token_expires_in=604799))
    monkeypatch.setattr(youtube, "_get", lambda a, url, params, token="": {"rows": []} if url == youtube.ANALYTICS_API
                        else {"items": [{"snippet": {"title": "Acme"}, "statistics": {"subscriberCount": "1200"}}]})
    out = youtube._finish_login(acct, {"code": "c", "state": "s"}, "s", "v")
    assert out["channel"] == "Acme" and out["subscribers"] == 1200
    assert "ends in 7 days" in out["warning"] and "Publish app" in out["warning"]
    saved = json.loads(acct.token_file.read_text())
    assert saved["refresh_token"] == "rt" and saved["refresh_token_expires_at"] > time.time()
    assert stat.S_IMODE(os.stat(acct.token_file).st_mode) == 0o600
    assert "Testing mode" in youtube.youtube_login_status()["warning"]


def test_youtube_videos_and_analytics_scoped(brand_dir, monkeypatch):
    write_creds(brand_dir, "client_secret.json", CLIENT)
    write_creds(brand_dir, "token.json", {"refresh_token": "r"})
    monkeypatch.setattr(youtube, "refresh_token_access", lambda *a: "at")
    calls = []

    def get_json(url, params, **k):
        calls.append((url, params))
        if url.endswith("/videos"):
            return {"items": [
                {"id": "v1", "snippet": {"channelId": "UCacme000000000000000000", "title": "Short"},
                 "contentDetails": {"duration": "PT58S"}, "statistics": {"viewCount": "10"}},
                {"id": "v2", "snippet": {"channelId": "UCacme000000000000000000", "title": "Long"},
                 "contentDetails": {"duration": "PT1H2M3S"}, "statistics": {"viewCount": "5"}},
                {"id": "v3", "snippet": {"channelId": "UCother", "title": "Other"},
                 "contentDetails": {"duration": "PT5M"}, "statistics": {}}]}
        return {"columnHeaders": [{"name": "day"}, {"name": "views"}], "rows": [["2026-10-01", 7]]}
    monkeypatch.setattr(youtube, "get_json", get_json)
    out = youtube.youtube_get_videos(["v1", "v2", "v3"])
    assert [(v["id"], v["format"], v["duration_seconds"]) for v in out["videos"]] == [("v1", "short", 58), ("v2", "long", 3723)]
    assert out["refused_other_channels"] == ["v3"]
    rep = youtube.youtube_analytics("2026-10-01", "2026-10-07", ["views"], "day")
    assert calls[-1][1]["ids"] == "channel==UCacme000000000000000000" and "mine" not in calls[-1][1]
    assert rep["rows"] == [{"day": "2026-10-01", "views": 7}]
    assert "channel_id" not in youtube.server.tools["youtube_analytics"].input_schema["properties"]


# --- Meta ------------------------------------------------------------------------

def test_meta_token_messages(brand_dir):
    with pytest.raises(ToolError, match="fw_prepare_credentials for instagram"):
        graph.user_token(load_brand())
    core.fw_prepare_credentials("instagram", open_in_editor=False)
    with pytest.raises(ToolError, match="not filled in yet"):
        graph.user_token(load_brand())
    write_creds(brand_dir, "meta.json", {"access_token": "EAAx"})
    assert graph.user_token(load_brand()) == "EAAx"


def test_meta_legacy_files(brand_dir):
    write_creds(brand_dir, "facebook.json", {"access_token": "EAAlegacy", "page_id": "100000000000001"})
    assert graph.user_token(load_brand()) == "EAAlegacy"


def fake_graph(monkeypatch, responses):
    calls = []

    def get(path, params, token):
        calls.append((path, params))
        for key, value in responses.items():
            if path == key:
                if isinstance(value, Exception):
                    raise value
                return value(params) if callable(value) else value
        raise AssertionError(f"unexpected Graph call {path}")
    monkeypatch.setattr(graph, "get", get)
    return calls


def test_instagram_account_must_match_username(brand_dir, monkeypatch):
    write_creds(brand_dir, "meta.json", {"access_token": "EAAx"})
    fake_graph(monkeypatch, {"100000000000001": {"instagram_business_account": {"id": "17841"}},
                             "17841": {"username": "someoneelse"}})
    with pytest.raises(ToolError, match="can't see the Instagram account @acmeoutdoor"):
        instagram.instagram_profile()
    graph._ig_ids.clear()
    fake_graph(monkeypatch, {"100000000000001": {"instagram_business_account": {"id": "17841"}},
                             "17841": lambda p: {"username": "AcmeOutdoor", "followers_count": 5}})
    assert instagram.instagram_profile()["followers_count"] == 5


def test_instagram_insights_skip_unavailable_metrics(brand_dir, monkeypatch):
    write_creds(brand_dir, "meta.json", {"access_token": "EAAx"})

    def insights(p):
        if "," in p["metric"] or p["metric"] == "shares":
            raise graph.GraphError("invalid metric", 100)
        return {"data": [{"name": p["metric"], "values": [{"value": 3}]}]}
    fake_graph(monkeypatch, {"m1": {"username": "acmeoutdoor", "media_product_type": "REELS"},
                             "m2": {"username": "other"}, "m1/insights": insights})
    out = instagram.instagram_media_insights(["m1", "m2"])
    assert out["media"][0] == {"id": "m1", "format": "reel", "timestamp": None, "views": 3, "reach": 3, "saved": 3,
                               "total_interactions": 3, "unavailable": ["shares"]}
    assert out["refused_not_brand"] == ["m2"]
    with pytest.raises(ToolError, match="at most 30 days"):
        instagram.instagram_account_insights("2026-08-01", "2026-10-01")


def test_facebook_scope_and_page_insights(brand_dir, monkeypatch):
    write_creds(brand_dir, "meta.json", {"access_token": "EAAx"})

    def page_insights(p):
        return {"data": [{"name": "page_media_view", "values": [{"value": 10}, {"value": 5}]},
                         {"name": "page_follows", "values": [{"value": 100}, {"value": 102}]}]}
    calls = fake_graph(monkeypatch, {"100000000000001": {"access_token": "PAGE"},
                                     "100000000000001/insights": page_insights})
    out = facebook.facebook_get_post_insights(["999_1"])
    assert out == {"posts": [], "refused_not_brand": ["999_1"]}
    rep = facebook.facebook_page_insights("2026-10-01", "2026-10-02")
    assert rep["totals"] == {"page_media_view": 15} and rep["at_end"] == {"page_follows": 102}
    assert [c[0] for c in calls] == ["100000000000001", "100000000000001/insights"]  # page token fetched once


def test_facebook_page_token_missing(brand_dir, monkeypatch):
    write_creds(brand_dir, "meta.json", {"access_token": "EAAx"})
    fake_graph(monkeypatch, {"100000000000001": {"id": "100000000000001"}})
    with pytest.raises(ToolError, match="no access to the brand's Page"):
        facebook.facebook_page()


def test_graph_error_translation():
    assert "invalid or expired" in str(graph._explain({"code": 190, "message": "Session expired"}, 400))
    assert "missing a permission" in str(graph._explain({"code": 200, "message": "x"}, 403))
    assert graph._explain({"code": 100, "message": "bad metric"}, 400).code == 100
    assert len(graph.day_range("2026-01-01", "2026-12-31", 90)) == 5
