"""Data snapshots: the skill output contract (plan §6).

Every skill saves the numbers behind a report as
    <brand>/data/<topic>-<YYYY-MM>.json
    {"topic", "period": {"from", "to"}, "generated_at", "language",
     "metrics": {<metrics.yaml id>: number|null}, "source": {<id>: connector},
     "caveats": [..], "extra": {..}}
and the report itself as <brand>/reports/<topic>-<YYYY-MM>.{md,html}.
The previous snapshot of the same topic is what a new report diffs against.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from lib import PLUGIN_ROOT
from lib.mcp_stdio import ToolError
from lib.workspace import Brand, load_yaml

TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STAMP_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
METRICS_FILE = PLUGIN_ROOT / "reference" / "metrics.yaml"

_metrics_cache = {}  # type: Dict[str, dict]


def metrics_dictionary() -> Dict[str, dict]:
    if not _metrics_cache:
        _metrics_cache.update(load_yaml(METRICS_FILE)["metrics"])
    return _metrics_cache


def check_topic(topic: str) -> str:
    if not TOPIC_RE.match(topic or ""):
        raise ToolError("topic must be lowercase words joined by dashes, e.g. `media-kit` or `seo-opportunities`.")
    return topic


def check_stamp(stamp: str) -> str:
    if not STAMP_RE.match(stamp or ""):
        raise ToolError("stamp must be YYYY-MM (monthly snapshot) or YYYY-MM-DD (extra snapshot in the same month).")
    return stamp


def snapshot_path(brand: Brand, topic: str, stamp: str) -> Path:
    return brand.data_dir() / f"{check_topic(topic)}-{check_stamp(stamp)}.json"


def list_snapshots(brand: Brand, topic: str) -> List[Path]:
    """Snapshots of a topic, oldest first (YYYY-MM sorts before YYYY-MM-DD of the same month)."""
    check_topic(topic)
    d = brand.data_dir()
    if not d.is_dir():
        return []
    pat = re.compile(rf"^{re.escape(topic)}-(\d{{4}}-\d{{2}}(?:-\d{{2}})?)\.json$")
    found = [(m.group(1), p) for p in d.iterdir() if (m := pat.match(p.name))]
    return [p for _, p in sorted(found)]


def save_snapshot(brand: Brand, topic: str, stamp: str, period_from: str, period_to: str,
                  metrics: Dict[str, Optional[float]], source: Dict[str, str],
                  caveats: List[str], extra: Optional[dict] = None, overwrite: bool = False) -> Path:
    known = metrics_dictionary()
    unknown = sorted(set(metrics) - set(known))
    if unknown:
        raise ToolError(
            "Unknown metric ids: " + ", ".join(unknown)
            + ". Use ids from reference/metrics.yaml; put anything else under `extra`."
        )
    for mid, value in metrics.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ToolError(f"metrics.{mid} must be a number or null (got {value!r}).")
    for date in (period_from, period_to):
        try:
            dt.date.fromisoformat(date)
        except (TypeError, ValueError):
            raise ToolError(f"period dates must be YYYY-MM-DD (got {date!r}).")
    path = snapshot_path(brand, topic, stamp)
    if path.exists() and not overwrite:
        raise ToolError(f"{path.name} already exists. Pass overwrite=true to replace it, or use a YYYY-MM-DD stamp.")
    doc = {
        "topic": topic,
        "period": {"from": period_from, "to": period_to},
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "brand": brand.name,
        "language": brand.language,
        "metrics": metrics,
        "source": source,
        "caveats": caveats,
        "extra": extra or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def read_snapshot(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"Snapshot not found: {path}")
    except ValueError:
        raise ToolError(f"{path} is not valid JSON.")


def diff_snapshots(old: dict, new: dict) -> dict:
    """Per-metric change between two snapshots, with a good/bad verdict from metrics.yaml."""
    known = metrics_dictionary()
    rows = []
    for mid in sorted(set(old.get("metrics", {})) | set(new.get("metrics", {}))):
        a, b = old.get("metrics", {}).get(mid), new.get("metrics", {}).get(mid)
        meta = known.get(mid, {})
        row = {"metric": mid, "name": meta.get("name", mid), "previous": a, "current": b,
               "change": None, "change_pct": None, "verdict": "n/a"}
        if a is None and b is not None:
            row["verdict"] = "new"
        elif a is not None and b is None:
            row["verdict"] = "missing now"
        elif a is not None and b is not None:
            row["change"] = b - a
            row["change_pct"] = None if a == 0 else round((b - a) / abs(a) * 100, 1)
            if b == a:
                row["verdict"] = "flat"
            else:
                better = (b > a) == bool(meta.get("higher_is_better", True))
                row["verdict"] = "better" if better else "worse"
        rows.append(row)
    return {
        "previous_period": old.get("period"), "current_period": new.get("period"),
        "rows": rows, "markdown": _markdown(rows),
    }


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 1 else f"{v:,.1f}"
    return f"{int(v):,}"


def _markdown(rows: List[dict]) -> str:
    arrows = {"better": "▲ better", "worse": "▼ worse", "flat": "= flat", "new": "new", "missing now": "missing", "n/a": ""}
    lines = ["| Metric | Previous | Current | Change | |", "|---|---:|---:|---:|---|"]
    for r in rows:
        pct = "" if r["change_pct"] is None else f"{r['change_pct']:+.1f}%"
        lines.append(f"| {r['name']} | {_fmt(r['previous'])} | {_fmt(r['current'])} | {pct} | {arrows[r['verdict']]} |")
    return "\n".join(lines)
