from __future__ import annotations

import json

import pytest

import thirdparty
from conftest import handshake, run_server, write_creds
from lib.mcp_stdio import ToolError
from lib.workspace import load_brand


def test_youtube_launch_plan(brand_dir):
    with pytest.raises(ToolError, match="client_secret.json"):
        thirdparty.plan_launch("youtube", load_brand(), "/usr/bin/uv")
    write_creds(brand_dir, "client_secret.json", {"installed": {"client_id": "a", "client_secret": "b"}})
    argv, env, cwd = thirdparty.plan_launch("youtube", load_brand(), "/usr/bin/uv")
    assert argv == ["/usr/bin/uv", "tool", "run", "--with", "mcp<2", f"youtube-studio-mcp=={thirdparty.YOUTUBE_MCP_VERSION}"]
    assert env["YOUTUBE_MCP_CONFIG_DIR"] == str(brand_dir / ".credentials") and cwd is None


def test_instagram_via_metricool_is_not_launched(brand_dir):
    with pytest.raises(ToolError, match="connected via metricool"):
        thirdparty.plan_launch("instagram", load_brand(), "/usr/bin/uv")


def test_facebook_refuses_mismatched_page(brand_dir, monkeypatch):
    write_creds(brand_dir, "facebook.json", {"access_token": "t", "page_id": "999"})
    monkeypatch.setattr(thirdparty, "_vendor_clone", lambda *a: pytest.fail("should refuse before cloning"))
    with pytest.raises(ToolError, match="Refusing to start"):
        thirdparty.plan_launch("facebook", load_brand(), "/usr/bin/uv")


def test_facebook_launch_plan(brand_dir, monkeypatch, tmp_path):
    write_creds(brand_dir, "facebook.json", {"access_token": "t", "page_id": "100000000000001"})
    monkeypatch.setattr(thirdparty, "_vendor_clone", lambda repo, commit, name: tmp_path / name)
    argv, env, cwd = thirdparty.plan_launch("facebook", load_brand(), "uv")
    assert env == {"FACEBOOK_ACCESS_TOKEN": "t", "FACEBOOK_PAGE_ID": "100000000000001"}
    assert cwd == tmp_path / "facebook-mcp-server" and argv[-3:] == ["mcp", "run", "server.py"]


def test_stub_server_explains_when_not_runnable(brand_dir):
    # Instagram is via metricool in the test brand → stub with a help tool.
    replies = run_server("thirdparty.py", handshake(("instagram_connection_help", {})), args=["instagram"])
    assert replies[0]["result"]["serverInfo"]["name"] == "funnelwise-instagram-unavailable"
    assert [t["name"] for t in replies[1]["result"]["tools"]] == ["instagram_connection_help"]
    help_ = json.loads(replies[2]["result"]["content"][0]["text"])
    assert help_["running"] is False and "metricool" in help_["reason"] and "Metricool" in help_["easy_path"]


def test_stub_without_brand():
    replies = run_server("thirdparty.py", handshake(("youtube_connection_help", {})), args=["youtube"])
    assert "No brand folder" in json.loads(replies[2]["result"]["content"][0]["text"])["reason"]
