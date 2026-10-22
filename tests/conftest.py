from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "servers"), str(ROOT / "servers" / "_vendor"), str(ROOT / "hooks")]

DEMO_BRAND = {
    "brand": {"name": "Acme Outdoor", "short": "Acme", "website": "https://www.acme-outdoor.example",
              "language": "en", "colors": {"primary": "#1F6F5C", "accent": "#F2A541"}},
    "connectors": {
        "ga4": {"via": "own", "property_id": "123456789"},
        "gsc": {"via": "own", "site_url": "https://www.acme-outdoor.example/"},
        "youtube": {"via": "metricool", "channel_id": "UCacme000000000000000000", "handle": "@acmeoutdoor"},
        "instagram": {"via": "metricool", "username": "acmeoutdoor"},
        "facebook": {"via": "metricool", "page_id": "100000000000001"},
        "tiktok": {"via": "own", "username": "acmeoutdoor"},
        "spotify": {"via": "own", "show_id": "0000000000000000000001"},
    },
    "competitors": [{"name": "Trailhead Gear", "youtube": "UCtrail00000000000000000", "spotify": "0000000000000000000099"}],
    "sponsorship": {"past_sponsors": ["Northwind Bikes"], "rate_card_currency": "EUR"},
}


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """No test may see the developer's real brand folder, active-brand marker or credentials."""
    for var in ("FUNNELWISE_BRAND_DIR", "FUNNELWISE_CREDENTIALS_DIR", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FUNNELWISE_HOME", str(tmp_path / "fwhome"))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    yield


@pytest.fixture
def brand_dir(tmp_path, monkeypatch) -> Path:
    d = tmp_path / "Funnelwise – Acme"
    for sub in ("reports", "data", "notes", ".credentials"):
        (d / sub).mkdir(parents=True)
    (d / "brand.yaml").write_text(yaml.safe_dump(DEMO_BRAND, sort_keys=False, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("FUNNELWISE_BRAND_DIR", str(d))
    return d


def write_creds(brand_dir: Path, name: str, data: dict) -> None:
    (brand_dir / ".credentials" / name).write_text(json.dumps(data), encoding="utf-8")


def run_server(script: str, messages: list, env: dict = None, args: list = ()) -> list:
    """Run a server script over stdio with newline-delimited JSON-RPC and return the replies."""
    proc = subprocess.run([sys.executable, str(ROOT / "servers" / script), *args],
                          input="".join(json.dumps(m) + "\n" for m in messages),
                          capture_output=True, text=True, timeout=60, env={**os.environ, **(env or {})})
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def handshake(*calls) -> list:
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    for i, (name, arguments) in enumerate(calls, start=3):
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    return msgs
