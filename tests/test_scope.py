"""Scope enforcement inside our own servers: they only ever touch the accounts in brand.yaml."""
from __future__ import annotations


import pytest

import ga4
import search_console
import spotify
import tiktok
from conftest import handshake, run_server, write_creds
from lib.mcp_stdio import ToolError
from lib.workspace import load_brand


def test_spotify_show_scope(brand_dir):
    b = load_brand()
    assert spotify.resolve_show(b, "") == "0000000000000000000001"
    assert spotify.resolve_show(b, "0000000000000000000001") == "0000000000000000000001"
    assert spotify.resolve_show(b, "0000000000000000000099") == "0000000000000000000099"  # listed competitor
    with pytest.raises(ToolError, match="outside this brand's scope"):
        spotify.resolve_show(b, "4rOoJ6Egrf8K2IrywzwOMk")


def test_spotify_refuses_before_any_network_call(brand_dir, monkeypatch):
    monkeypatch.setattr(spotify, "get_json", lambda *a, **k: pytest.fail("network call made"))
    monkeypatch.setattr(spotify, "request_json", lambda *a, **k: pytest.fail("network call made"))
    with pytest.raises(ToolError, match="outside"):
        spotify.spotify_get_show(show_id="someoneelse0000000000000")


def test_spotify_uses_brand_show_by_default(brand_dir, monkeypatch):
    write_creds(brand_dir, "spotify.json", {"client_id": "id", "client_secret": "secret"})
    calls = []
    monkeypatch.setattr(spotify, "request_json", lambda *a, **k: {"access_token": "t", "expires_in": 3600})
    monkeypatch.setattr(spotify, "get_json", lambda url, params, **k: calls.append(url) or {"id": "x", "name": "Show"})
    out = spotify.spotify_get_show()
    assert calls == ["https://api.spotify.com/v1/shows/0000000000000000000001"]
    assert out["is_brand_show"] is True  # computed from the resolved scope, not from the response


def test_spotify_missing_credentials_message(brand_dir):
    with pytest.raises(ToolError, match="No Spotify credentials yet"):
        spotify.spotify_get_show()


def test_gsc_site_scope_and_host_check(brand_dir):
    b = load_brand()
    assert search_console.site(b) == "https://www.acme-outdoor.example/"
    assert search_console.site(b, "https://www.acme-outdoor.example") == "https://www.acme-outdoor.example/"
    with pytest.raises(ToolError, match="outside this brand's scope"):
        search_console.site(b, "https://www.other.example/")
    ok = search_console._host_ok
    assert ok("https://www.acme-outdoor.example/", "https://www.acme-outdoor.example/blog/x")
    assert not ok("https://www.acme-outdoor.example/", "https://evil.example/https://www.acme-outdoor.example/")
    assert ok("sc-domain:acme.example", "https://shop.acme.example/p")
    assert ok("sc-domain:acme.example", "https://acme.example/")
    assert not ok("sc-domain:acme.example", "https://notacme.example/")


def test_gsc_tools_refuse_other_sites_without_network(brand_dir, monkeypatch):
    monkeypatch.setattr(search_console, "_token", lambda b: pytest.fail("token requested"))
    with pytest.raises(ToolError, match="outside"):
        search_console.gsc_query("2026-10-01", "2026-10-02", site_url="sc-domain:other.example")
    with pytest.raises(ToolError, match="not on"):
        search_console.gsc_indexing_issues(["https://other.example/a"])
    with pytest.raises(ToolError, match="not on"):
        search_console.gsc_inspect_url("https://other.example/a")
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        search_console.gsc_query("last week", "2026-10-02")
    with pytest.raises(ToolError, match="on or before"):
        search_console.gsc_query("2026-10-05", "2026-10-02")


def test_gsc_has_no_list_all_sites_tool():
    assert "gsc_sites" not in search_console.server.tools
    assert "gsc_site_details" not in search_console.server.tools


def test_gsc_credential_fallback_order(brand_dir, monkeypatch):
    with pytest.raises(ToolError, match="No Search Console credentials"):
        search_console._token(load_brand())
    write_creds(brand_dir, "client_secret.json", {"installed": {"client_id": "cid", "client_secret": "cs"}})
    write_creds(brand_dir, "gsc_token.json", {"refresh_token": "rt"})
    seen = []
    monkeypatch.setattr(search_console, "refresh_token_access", lambda *a: seen.append(a) or "oauth-token")
    assert search_console._token(load_brand()) == "oauth-token" and seen == [("cid", "cs", "rt")]
    write_creds(brand_dir, "google-service-account.json", {"type": "service_account", "client_email": "e", "private_key": "k"})
    monkeypatch.setattr(search_console, "service_account_token", lambda info, scope: "sa-token")
    assert search_console._token(load_brand()) == "sa-token"  # service account wins


def test_ga4_property_pinned(brand_dir, monkeypatch):
    write_creds(brand_dir, "google-service-account.json", {"type": "service_account", "client_email": "e", "private_key": "k"})
    monkeypatch.setattr(ga4, "service_account_token", lambda info, scope: "tok")
    sent = {}
    monkeypatch.setattr(ga4, "post_json", lambda url, body, **k: sent.update(url=url, body=body) or {
        "dimensionHeaders": [{"name": "country"}],
        "metricHeaders": [{"name": "activeUsers", "type": "TYPE_INTEGER"}, {"name": "engagementRate", "type": "TYPE_FLOAT"}],
        "rows": [{"dimensionValues": [{"value": "Bulgaria"}], "metricValues": [{"value": "12"}, {"value": "0.5"}]}],
        "totals": [{"dimensionValues": [{"value": "RESERVED_TOTAL"}], "metricValues": [{"value": "12"}, {"value": "0.5"}]}],
        "rowCount": 1})
    out = ga4.ga_run_report("7daysAgo", "yesterday", ["activeUsers", "engagementRate"], ["country"], order_by_metric="activeUsers")
    assert sent["url"].endswith("/properties/123456789:runReport")
    assert sent["body"]["orderBys"] == [{"metric": {"metricName": "activeUsers"}, "desc": True}]
    assert out["rows"] == [{"country": "Bulgaria", "activeUsers": 12, "engagementRate": 0.5}]
    assert out["totals"][0]["activeUsers"] == 12
    assert "property_id" not in ga4.server.tools["ga_run_report"].input_schema["properties"]
    with pytest.raises(ToolError, match="At least one metric"):
        ga4.ga_run_report("7daysAgo", "yesterday", [])


def test_ga4_has_no_write_tools():
    assert all(not n.startswith(("ga_send", "ga_validate")) for n in ga4.server.tools)


def test_tiktok_login_refuses_wrong_account(brand_dir, monkeypatch):
    write_creds(brand_dir, "tiktok.json", {"client_key": "k", "client_secret": "s"})
    acct = tiktok.Account(load_brand())
    monkeypatch.setattr(tiktok, "_token_request", lambda fields: {
        "access_token": "a", "refresh_token": "r", "expires_in": 86400, "refresh_expires_in": 31536000, "open_id": "o"})
    monkeypatch.setattr(tiktok, "_api", lambda *a, **k: {"user": {"username": "someoneelse", "display_name": "X", "follower_count": 1}})
    with pytest.raises(ToolError, match="Wrong TikTok account: logged in as @someoneelse"):
        tiktok._finish_login(acct, {"code": "c", "state": "s1"}, "s1", "v")
    assert not acct.token_file.exists()  # nothing saved
    monkeypatch.setattr(tiktok, "_api", lambda *a, **k: {"user": {"username": "AcmeOutdoor", "display_name": "Acme", "follower_count": 5}})
    out = tiktok._finish_login(acct, {"code": "c", "state": "s1"}, "s1", "v")
    assert out["signed_in_as"] == "@AcmeOutdoor" and acct.token_file.exists()
    with pytest.raises(ToolError, match="older login attempt"):
        tiktok._finish_login(acct, {"code": "c", "state": "other"}, "s1", "v")


def test_tiktok_authorize_url_uses_hex_pkce(brand_dir):
    import hashlib
    import urllib.parse
    write_creds(brand_dir, "tiktok.json", {"client_key": "k", "client_secret": "s"})
    url = tiktok._authorize_url(tiktok.Account(load_brand()), "verifier", "state")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert q["code_challenge"] == hashlib.sha256(b"verifier").hexdigest()
    assert q["redirect_uri"] == "http://localhost:3455/callback/"


def test_tiktok_not_signed_in_message(brand_dir):
    write_creds(brand_dir, "tiktok.json", {"client_key": "k", "client_secret": "s"})
    with pytest.raises(ToolError, match="tiktok_login_start and log in as @acmeoutdoor"):
        tiktok.tiktok_get_profile()


@pytest.mark.parametrize("script", ["core.py", "ga4.py", "search_console.py", "spotify.py", "tiktok.py",
                                    "youtube.py", "instagram.py", "facebook.py"])
def test_every_server_lists_tools_without_brand(script):
    """A server must start even with no brand folder: tools then explain what to do."""
    replies = run_server(script, handshake())
    assert replies[0]["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert replies[1]["result"]["tools"]


def test_tool_error_without_brand_is_actionable():
    replies = run_server("spotify.py", handshake(("spotify_get_show", {})))
    res = replies[2]["result"]
    assert res["isError"] and "Set up my brand" in res["content"][0]["text"]
