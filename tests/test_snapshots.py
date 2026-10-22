from __future__ import annotations

import json

import pytest

from conftest import ROOT
from lib.mcp_stdio import ToolError
from lib.snapshots import diff_snapshots, list_snapshots, metrics_dictionary, read_snapshot, save_snapshot
from lib.workspace import load_brand


def save(brand, stamp, metrics, **kw):
    return save_snapshot(brand, "media-kit", stamp, "2026-09-01", "2026-09-30", metrics, {}, [], **kw)


def test_metrics_dictionary_is_complete():
    m = metrics_dictionary()
    assert len(m) >= 30
    for mid, meta in m.items():
        assert mid.split(".")[0] == meta["platform"] or meta["platform"] == "cross", mid
        assert meta["stage"] in {"Awareness", "Engagement", "Traffic", "Conversion", "Loyalty"}, mid
        assert meta["unit"] in {"count", "ratio", "seconds", "hours", "position", "days", "money"}, mid
        assert isinstance(meta["higher_is_better"], bool), mid
        assert meta["formula"] and isinstance(meta["caveats"], list), mid
        assert meta["benchmark"] is None or meta["benchmark"].get("source"), f"{mid}: benchmark needs a source"


def test_save_list_and_order(brand_dir):
    b = load_brand()
    save(b, "2026-09", {"youtube.subscribers": 100})
    save(b, "2026-10-15", {"youtube.subscribers": 120})
    save(b, "2026-10", {"youtube.subscribers": 110})
    (brand_dir / "data" / "media-kit-onepager-tiktok-2026-10.json").write_text("{}")  # other topic, ignored
    assert [p.name for p in list_snapshots(b, "media-kit")] == [
        "media-kit-2026-09.json", "media-kit-2026-10.json", "media-kit-2026-10-15.json"]
    doc = read_snapshot(brand_dir / "data" / "media-kit-2026-09.json")
    assert doc["language"] == "en" and doc["brand"] == "Acme Outdoor" and doc["period"]["to"] == "2026-09-30"


def test_save_validation(brand_dir):
    b = load_brand()
    with pytest.raises(ToolError, match="Unknown metric ids: youtube.made_up"):
        save(b, "2026-09", {"youtube.made_up": 1})
    with pytest.raises(ToolError, match="must be a number"):
        save(b, "2026-09", {"youtube.subscribers": "1k"})
    with pytest.raises(ToolError, match="must be a number"):
        save(b, "2026-09", {"youtube.subscribers": True})
    with pytest.raises(ToolError, match="stamp"):
        save(b, "Sept", {})
    with pytest.raises(ToolError, match="topic"):
        save_snapshot(b, "Media Kit", "2026-09", "2026-09-01", "2026-09-30", {}, {}, [])
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        save_snapshot(b, "media-kit", "2026-09", "Sept 1", "2026-09-30", {}, {}, [])
    save(b, "2026-09", {"youtube.subscribers": None})
    with pytest.raises(ToolError, match="already exists"):
        save(b, "2026-09", {})
    save(b, "2026-09", {"youtube.subscribers": 5}, overwrite=True)
    assert read_snapshot(brand_dir / "data" / "media-kit-2026-09.json")["metrics"] == {"youtube.subscribers": 5}


def test_diff_verdicts_follow_higher_is_better():
    old = {"period": {"from": "a"}, "metrics": {"youtube.subscribers": 100, "gsc.avg_position": 10.0,
                                                "gsc.ctr": 0.05, "tiktok.followers": None, "ga4.sessions": 0,
                                                "instagram.reach": 50}}
    new = {"period": {"from": "b"}, "metrics": {"youtube.subscribers": 150, "gsc.avg_position": 8.0,
                                                "gsc.ctr": 0.05, "tiktok.followers": 10, "ga4.sessions": 5}}
    rows = {r["metric"]: r for r in diff_snapshots(old, new)["rows"]}
    assert rows["youtube.subscribers"]["verdict"] == "better" and rows["youtube.subscribers"]["change_pct"] == 50.0
    assert rows["gsc.avg_position"]["verdict"] == "better"  # lower position is better
    assert rows["gsc.ctr"]["verdict"] == "flat"
    assert rows["tiktok.followers"]["verdict"] == "new"
    assert rows["ga4.sessions"]["change_pct"] is None and rows["ga4.sessions"]["verdict"] == "better"
    assert rows["instagram.reach"]["verdict"] == "missing now"


def test_diff_markdown_on_demo_brand():
    data = ROOT / "examples" / "demo-brand" / "data"
    d = diff_snapshots(json.loads((data / "media-kit-2026-09.json").read_text()),
                       json.loads((data / "media-kit-2026-10.json").read_text()))
    md = d["markdown"]
    assert md.startswith("| Metric | Previous | Current | Change | |")
    assert "| YouTube subscribers | 18,400 | 19,650 | +6.8% | ▲ better |" in md
    assert "| Instagram reach | 52,000 | 47,800 | -8.1% | ▼ worse |" in md
    assert "| YouTube engagement rate | 0.041 | 0.038 | -7.3% | ▼ worse |" in md
