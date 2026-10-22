"""Shared code for the Funnelwise local MCP servers.

Everything here is standard library only and runs on Python 3.9, because the
Claude desktop app launches plugin servers with the system `python3` (see
docs/spikes/0.2-server-packaging.md). Third-party pure-Python libraries live in
servers/_vendor/ and are put on sys.path by `bootstrap()`.
"""
from __future__ import annotations

import sys
from pathlib import Path

SERVERS_DIR = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SERVERS_DIR.parent
VENDOR_DIR = SERVERS_DIR / "_vendor"


def bootstrap() -> None:
    """Make `lib.*` and the vendored packages importable from any server script."""
    for p in (str(SERVERS_DIR), str(VENDOR_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
