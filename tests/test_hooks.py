from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from conftest import DEMO_BRAND, ROOT
from write_guard import decide, is_write_tool, split_tool

# Real tool names from the pinned third-party servers (dev/smoke.py output) and our own.
WRITE_TOOLS = [
    "mcp__plugin_funnelwise_facebook__post_to_facebook", "mcp__facebook__reply_to_comment",
    "mcp__facebook__delete_post", "mcp__facebook__delete_comment", "mcp__facebook__hide_comment",
    "mcp__facebook__unhide_comment", "mcp__facebook__delete_comment_from_post", "mcp__facebook__post_image_to_facebook",
    "mcp__facebook__send_dm_to_user", "mcp__facebook__update_post", "mcp__facebook__schedule_post",
    "mcp__facebook__bulk_delete_comments", "mcp__facebook__bulk_hide_comments", "mcp__facebook__bulk_unhide_comments",
    "mcp__instagram__publish_media", "mcp__instagram__send_dm",
    "mcp__youtube__youtube_upload_video", "mcp__youtube__youtube_update_video", "mcp__youtube__youtube_set_thumbnail",
    "mcp__youtube__youtube_delete_video", "mcp__youtube__youtube_create_playlist", "mcp__youtube__youtube_add_to_playlist",
    "mcp__youtube__youtube_remove_from_playlist", "mcp__youtube__youtube_post_comment", "mcp__youtube__youtube_reply_to_comment",
    "mcp__google-analytics__ga_send_event", "mcp__google-analytics__ga_send_purchase", "mcp__google-analytics__ga_send_pageview",
    "mcp__claude_ai_Metricool__createScheduledPost", "mcp__metricool__publishPost", "mcp__metricool__deletePost",
    # Metricool's published tool names (metricool.com/metricool-mcp-claude, checked 2026-10-22)
    "mcp__claude_ai_Metricool__post_schedule_post", "mcp__claude_ai_Metricool__update_schedule_post",
]
READ_TOOLS = [
    "mcp__facebook__get_page_posts", "mcp__facebook__get_post_comments", "mcp__facebook__filter_negative_comments",
    "mcp__facebook__get_number_of_likes", "mcp__facebook__get_scheduled_posts", "mcp__facebook__get_page_info",
    "mcp__instagram__get_media_insights", "mcp__instagram__get_conversation_messages", "mcp__instagram__validate_access_token",
    "mcp__youtube__youtube_auth", "mcp__youtube__youtube_list_comments", "mcp__youtube__youtube_analytics_overview",
    "mcp__youtube__youtube_reporting_create_job", "mcp__youtube__youtube_search_suggestions",
    "mcp__google-analytics__ga_run_report", "mcp__google-analytics__ga_validate_event",
    "mcp__plugin_funnelwise_tiktok__tiktok_login_start", "mcp__plugin_funnelwise_search-console__gsc_opportunities",
    "mcp__metricool__getPostsStats",
    "mcp__claude_ai_Metricool__get_instagram_posts", "mcp__claude_ai_Metricool__get_tiktok_videos",
    "mcp__claude_ai_Metricool__get_youtube_videos", "mcp__claude_ai_Metricool__get_scheduled_posts",
    "mcp__claude_ai_Metricool__get_best_time_to_post", "mcp__claude_ai_Metricool__get_analytics",
]
NOT_MARKETING = ["mcp__github__create_issue", "mcp__claude_ai_Google_Drive__create_file", "Write", "Bash",
                 "mcp__plugin_funnelwise_funnelwise__fw_save_report", "mcp__plugin_funnelwise_funnelwise__fw_set_connector"]


def event(tool, **tool_input):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


@pytest.mark.parametrize("tool", WRITE_TOOLS)
def test_write_tools_denied(tool):
    reason = decide(event(tool), load=False)
    assert reason and "read-only" in reason


@pytest.mark.parametrize("tool", READ_TOOLS)
def test_read_tools_allowed(tool):
    assert decide(event(tool), load=False) is None


@pytest.mark.parametrize("tool", NOT_MARKETING)
def test_non_marketing_tools_untouched(tool):
    assert decide(event(tool), load=False) is None


def test_split_and_verb_detection():
    assert split_tool("mcp__plugin_funnelwise_search-console__gsc_query") == ("plugin_funnelwise_search-console", "gsc_query")
    assert split_tool("Bash") == ("", "Bash")
    assert is_write_tool("ytPostComment") and not is_write_tool("get_post_comments")


SCOPE_CASES = [
    ("mcp__plugin_funnelwise_search-console__gsc_query", {"site_url": "https://other.example/"}, "outside"),
    ("mcp__plugin_funnelwise_search-console__gsc_query", {"site_url": "https://www.acme-outdoor.example"}, None),
    ("mcp__google-search-console__gsc_audit", {"site_url": "sc-domain:other.example"}, "outside"),
    ("mcp__spotify__spotify_get_show", {"show_id": "4rOoJ6Egrf8K2IrywzwOMk"}, "outside"),
    ("mcp__spotify__spotify_get_show", {"show_id": "0000000000000000000099"}, None),  # competitor
    ("mcp__youtube__youtube_get_channel", {"mine": True}, "UCacme000000000000000000"),
    ("mcp__youtube__youtube_list_videos", {"channel_id": "UCtrail00000000000000000"}, None),  # competitor
    ("mcp__youtube__youtube_list_videos", {"channel_id": "UCrandom0000000000000000"}, "outside"),
    ("mcp__google-analytics__ga_run_report", {"property_id": "properties/999"}, "outside"),
    ("mcp__google-analytics__ga_run_report", {"property_id": "properties/123456789"}, None),
    ("mcp__facebook__get_page_info", {"page_id": "1"}, "outside"),
    ("mcp__claude_ai_Metricool__getStats", {"site_url": "https://other.example"}, None),  # platform unknown → no scope check
]


@pytest.mark.parametrize("tool,args,expect", SCOPE_CASES)
def test_scope_guard(tool, args, expect):
    reason = decide(event(tool, **args), brand_data=DEMO_BRAND)
    if expect is None:
        assert reason is None
    else:
        assert reason and expect in reason


def run_hook(script, payload, env):
    proc = subprocess.run([sys.executable, str(ROOT / "hooks" / script)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env={**os.environ, **env})
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def test_write_guard_hook_process(brand_dir):
    env = {"FUNNELWISE_BRAND_DIR": str(brand_dir)}
    out = run_hook("write_guard.py", event("mcp__facebook__delete_post", post_id="1"), env)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert run_hook("write_guard.py", event("mcp__facebook__get_page_info"), env) is None
    out = run_hook("write_guard.py", event("mcp__spotify__spotify_get_show", show_id="nope"), env)
    assert "outside" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_write_guard_survives_broken_input_and_brand(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "write_guard.py")], input="not json",
                          capture_output=True, text=True)
    assert proc.returncode == 0 and proc.stdout == ""
    bad = tmp_path / "b"
    bad.mkdir()
    (bad / "brand.yaml").write_text("{{{")
    assert run_hook("write_guard.py", event("mcp__spotify__spotify_get_show", show_id="x"),
                    {"FUNNELWISE_BRAND_DIR": str(bad)}) is None


def test_session_start_with_brand(brand_dir):
    (brand_dir / "notes" / "profile.md").write_text("# Profile\n- **Goal:** more sponsors\n")
    ctx = run_hook("session_start.py", {}, {"FUNNELWISE_BRAND_DIR": str(brand_dir)})["hookSpecificOutput"]["additionalContext"]
    assert "Funnelwise brand: Acme Outdoor" in ctx and "language `en`" in ctx
    assert "- spotify: 0000000000000000000001 via own" in ctx
    assert "more sponsors" in ctx and "never `mine: true`" in ctx


def test_session_start_without_brand_and_with_broken_brand(tmp_path):
    env = {"FUNNELWISE_HOME": str(tmp_path / "h"), "FUNNELWISE_BRAND_DIR": ""}
    env_clean = {k: v for k, v in os.environ.items() if k not in ("FUNNELWISE_BRAND_DIR", "CLAUDE_PROJECT_DIR")}
    proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "session_start.py")], input="{}", capture_output=True,
                          text=True, cwd=tmp_path, env={**env_clean, "FUNNELWISE_HOME": env["FUNNELWISE_HOME"]})
    assert "onboarding" in json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "brand.yaml").write_text("brand: {name: x}\n")
    ctx = run_hook("session_start.py", {}, {"FUNNELWISE_BRAND_DIR": str(bad)})["hookSpecificOutput"]["additionalContext"]
    assert "brand.yaml problem" in ctx


def test_hooks_json_points_at_existing_scripts():
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    for event_name, entries in cfg.items():
        for entry in entries:
            for h in entry["hooks"]:
                script = h["command"].split('"')[1].replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
                assert os.path.isfile(script), (event_name, script)
    assert cfg["PreToolUse"][0]["matcher"] == "mcp__.*"
