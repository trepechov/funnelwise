#!/usr/bin/env python3
"""Start every Funnelwise MCP server over stdio, do the MCP handshake, list tools,
and optionally call one tool per server. Uses the same interpreter as the host.

    python3 dev/smoke.py                       # handshake + tools/list for all servers
    python3 dev/smoke.py --call spotify spotify_get_show '{}'
    FUNNELWISE_BRAND_DIR=/path/to/brand python3 dev/smoke.py --live   # one read call per connected platform

--live makes real, read-only API calls with the brand's credentials.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]

LIVE_CALLS = {
    "funnelwise": ("fw_connection_status", {}),
    "ga4": ("ga_run_report", {"date_from": "7daysAgo", "date_to": "yesterday", "metrics": ["activeUsers", "sessions"]}),
    "search-console": ("gsc_site", {}),
    "spotify": ("spotify_get_show", {}),
    "tiktok": ("tiktok_get_profile", {}),
    "youtube": ("youtube_channel", {}),
    "instagram": ("instagram_profile", {}),
    "facebook": ("facebook_page", {}),
}


def rpc(name: str, calls: list) -> list:
    spec = CONFIG[name]
    args = [a.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)) for a in spec["args"]]
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    for i, (tool, arguments) in enumerate(calls, start=3):
        msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})
    proc = subprocess.run([sys.executable if spec["command"] == "python3" else spec["command"], *args],
                          input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True, text=True,
                          timeout=120, env=os.environ.copy())
    out = [json.loads(line) for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    if not out:
        raise RuntimeError(f"{name}: no output. stderr:\n{proc.stderr[-2000:]}")
    return out


def main() -> int:
    argv = sys.argv[1:]
    failures = 0
    if argv[:1] == ["--call"]:
        name, tool, arguments = argv[1], argv[2], json.loads(argv[3] if len(argv) > 3 else "{}")
        print(json.dumps(rpc(name, [(tool, arguments)])[-1], indent=2, ensure_ascii=False))
        return 0
    live = "--live" in argv
    for name in CONFIG:
        calls = [LIVE_CALLS[name]] if live and name in LIVE_CALLS else []
        try:
            replies = rpc(name, calls)
        except Exception as e:  # noqa: BLE001
            print(f"✗ {name}: {e}")
            failures += 1
            continue
        tools = next(r for r in replies if r.get("id") == 2)["result"]["tools"]
        server = replies[0]["result"]["serverInfo"]["name"]
        print(f"✓ {name:15} {server:38} {len(tools):2} tools: {', '.join(t['name'] for t in tools)}")
        for r in replies[2:]:
            res = r.get("result", {})
            text = res.get("content", [{}])[0].get("text", "")
            flag = "✗" if res.get("isError") else "✓"
            failures += res.get("isError", False)
            print(f"    {flag} {calls[0][0]} → {text[:300].replace(chr(10), ' ')}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
