"""The core server's tools, called in-process, as the onboarding and report skills use them."""
from __future__ import annotations

import json
import os
import stat

import pytest
import yaml

import core
from conftest import ROOT, handshake, run_server
from lib.mcp_stdio import ToolError
from lib.workspace import find_brand_dir


def test_onboarding_flow_end_to_end(tmp_path):
    folder = tmp_path / "Funnelwise – Nova"
    out = core.fw_init_brand(str(folder), "Nova Coffee", "de", website="https://nova.example", short="Nova")
    assert out["brand"]["language"] == "de" and out["not_connected"][0] == "ga4"
    assert {p.name for p in folder.iterdir()} >= {"brand.yaml", "reports", "data", "notes", "README.md", ".gitignore"}
    assert find_brand_dir() == folder.resolve()  # active-brand marker set
    with pytest.raises(ToolError, match="already exists"):
        core.fw_init_brand(str(folder), "Nova Coffee", "de")

    saved = core.fw_set_connector("gsc", "own", "sc-domain:nova.example")
    assert saved["status"]["credentials"]["ready"] is False
    assert "service-account" in saved["status"]["credentials"]["next_steps"][0]
    core.fw_set_connector("instagram", "metricool", "novacoffee")
    with pytest.raises(ToolError, match="required when via is `own`"):
        core.fw_set_connector("spotify", "own")
    with pytest.raises(ToolError, match="Unknown connector"):
        core.fw_set_connector("linkedin", "own", "x")

    key = tmp_path / "Downloads" / "nova-123.json"
    key.parent.mkdir()
    key.write_text(json.dumps({"type": "service_account", "client_email": "fw@nova.iam.gserviceaccount.com",
                               "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n"}))
    imp = core.fw_import_credential("google-service-account", str(key))
    saved_path = tmp_path / "fwhome" / "credentials" / "nova" / "google-service-account.json"
    assert imp["saved_to"] == str(saved_path)
    assert imp["service_account_email"] == "fw@nova.iam.gserviceaccount.com"
    assert stat.S_IMODE(os.stat(saved_path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(saved_path.parent).st_mode) == 0o700
    status = core.fw_connection_status()["connectors"]
    assert status["gsc"]["credentials"]["ready"] is True
    assert status["instagram"]["via"] == "metricool" and "connector settings" in status["instagram"]["note"]
    assert status["tiktok"] == {"connected": False}

    core.fw_update_brand({"sponsorship": {"past_sponsors": ["Bean Co"]}, "brand": {"colors": {"primary": "#112233"}}})
    data = yaml.safe_load((folder / "brand.yaml").read_text())
    assert data["sponsorship"]["past_sponsors"] == ["Bean Co"] and data["brand"]["colors"]["primary"] == "#112233"
    assert data["brand"]["website"] == "https://nova.example"  # untouched keys kept
    with pytest.raises(ToolError, match="would be invalid"):
        core.fw_update_brand({"brand": {"language": "German"}})
    with pytest.raises(ToolError, match="fw_set_connector"):
        core.fw_update_brand({"connectors": {}})
    core.fw_remove_connector("instagram")
    assert "instagram" not in yaml.safe_load((folder / "brand.yaml").read_text())["connectors"]
    assert "Never put passwords" in (folder / "brand.yaml").read_text()


def test_credential_validation(brand_dir, tmp_path):
    bad = tmp_path / "client.json"
    bad.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}))
    with pytest.raises(ToolError, match="missing: type, client_email, private_key"):
        core.fw_import_credential("google-service-account", str(bad))
    assert core.fw_import_credential("google-oauth-client", str(bad))["saved_to"].endswith("client_secret.json")
    with pytest.raises(ToolError, match="downloaded file"):
        core.fw_save_credential("google-service-account", {})
    with pytest.raises(ToolError, match="missing: client_secret"):
        core.fw_save_credential("spotify", {"client_id": "a"})
    with pytest.raises(ToolError, match="Unknown credential kind"):
        core.fw_save_credential("myspace", {})
    with pytest.raises(ToolError, match="File not found"):
        core.fw_import_credential("spotify", str(tmp_path / "nope.json"))
    path = core.fw_save_credential("spotify", {"client_id": "a", "client_secret": "b"})["saved_to"]
    assert path == str(brand_dir / ".credentials" / "spotify.json")


def test_snapshot_report_and_diff_tools(brand_dir):
    first = core.fw_save_snapshot("media-kit", "2026-09", "2026-09-01", "2026-09-30", {"youtube.subscribers": 100})
    assert first["previous_snapshot"] is None
    assert core.fw_diff_snapshot("media-kit")["first_snapshot"] is True
    second = core.fw_save_snapshot("media-kit", "2026-10", "2026-10-01", "2026-10-31", {"youtube.subscribers": 90},
                                   caveats=["TikTok not connected"])
    assert second["previous_snapshot"] == "media-kit-2026-09.json"
    diff = core.fw_diff_snapshot("media-kit")
    assert diff["previous"] == "media-kit-2026-09.json" and diff["rows"][0]["verdict"] == "worse"
    assert core.fw_diff_snapshot("media-kit", stamp="2026-10", against="2026-09")["rows"][0]["change"] == -10
    with pytest.raises(ToolError, match="No `media-kit` snapshot with stamp 2026-11"):
        core.fw_diff_snapshot("media-kit", stamp="2026-11")
    with pytest.raises(ToolError, match="No snapshots"):
        core.fw_diff_snapshot("seo-opportunities")

    listed = core.fw_list_snapshots()["snapshots"]
    assert [s["file"] for s in listed] == ["media-kit-2026-09.json", "media-kit-2026-10.json"]
    assert core.fw_read_snapshot("media-kit-2026-10.json")["caveats"] == ["TikTok not connected"]
    with pytest.raises(ToolError, match="inside the brand's data"):
        core.fw_read_snapshot("../brand.yaml")

    rep = core.fw_save_report("media-kit", "2026-10", "<html></html>", "html")
    assert rep["saved_to"] == str(brand_dir / "reports" / "media-kit-2026-10.html")
    with pytest.raises(ToolError, match="already exists"):
        core.fw_save_report("media-kit", "2026-10", "x", "html")
    with pytest.raises(ToolError, match="md or html"):
        core.fw_save_report("media-kit", "2026-10", "x", "pdf")


def test_brand_summary_includes_profile(brand_dir):
    (brand_dir / "notes" / "profile.md").write_text("# Profile\n- **Role:** Data analyst\n")
    out = core.fw_brand()
    assert out["profile"].startswith("# Profile")
    assert out["connectors"]["youtube"] == {"via": "own", "channel_id": "UCacme000000000000000000", "handle": "@acmeoutdoor"}
    assert out["not_connected"] == ["semrush"]


def test_metrics_lookup():
    assert core.fw_metrics(ids=["gsc.avg_position"])["gsc.avg_position"]["higher_is_better"] is False
    assert all(v["platform"] == "spotify" for v in core.fw_metrics(platform="spotify").values())
    with pytest.raises(ToolError, match="Unknown metric ids: x.y"):
        core.fw_metrics(ids=["x.y"])


def test_skill_catalog_by_role_and_connections(brand_dir):
    cat = core.fw_skill_catalog("sponsorship-specialist")
    assert cat["skills"]["media-kit"]["can_run_now"] is True
    assert cat["skills"]["kpi-scorecard"]["can_run_now"] is False  # planned
    assert cat["for_role"]["available_now"] == ["media-kit"]
    core.fw_remove_connector("gsc")
    cat = core.fw_skill_catalog("seo-specialist")
    assert cat["skills"]["seo-opportunities"]["missing_connections"] == ["gsc"]
    assert cat["for_role"]["fallback_mvp_skills"] == ["media-kit", "content-performance"]
    with pytest.raises(ToolError, match="Unknown role"):
        core.fw_skill_catalog("ceo")


def test_catalog_without_brand_still_works():
    cat = core.fw_skill_catalog()
    assert cat["connected"] == [] and cat["skills"]["media-kit"]["can_run_now"] is False


def test_core_server_over_stdio(brand_dir):
    replies = run_server("core.py", handshake(("fw_brand", {}), ("fw_save_report", {"topic": "Bad Topic", "stamp": "2026-10", "content": "x"})))
    init, tools, brand, bad = replies
    assert init["result"]["serverInfo"] == {"name": "funnelwise", "version": json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]}
    assert "read-only" in init["result"]["instructions"]
    assert len(tools["result"]["tools"]) == len(core.server.tools)
    assert json.loads(brand["result"]["content"][0]["text"])["brand"]["name"] == "Acme Outdoor"
    assert bad["result"]["isError"] and "lowercase" in bad["result"]["content"][0]["text"]
