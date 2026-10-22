#!/usr/bin/env python3
"""PreToolUse hook: keep credential files out of the conversation.

Denies Claude's file and shell tools (Read, Edit, Write, Grep, Glob, Bash, …)
when an argument points into a Funnelwise credentials folder: a brand's
`.credentials/` or `~/.funnelwise/credentials/`. The user fills those files in a
text editor (fw_prepare_credentials); Funnelwise's servers read them, and
fw_connection_status reports which fields are missing without showing values.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Iterator, Optional

CREDENTIAL_PATH = re.compile(r"(?:^|[^\w.-])\.credentials(?:[/\\'\"\s*]|$)|\.funnelwise[/\\]credentials", re.I)


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def decide(event: dict) -> Optional[str]:
    if event.get("tool_name", "").startswith("mcp__"):
        return None
    if any(CREDENTIAL_PATH.search(s) for s in _strings(event.get("tool_input") or {})):
        return ("Funnelwise keeps credential files out of the chat, so they can't be opened, searched or edited here. "
                "Use fw_connection_status to see which fields are still missing (it never shows values), or "
                "fw_prepare_credentials to open the file in the user's text editor for them to fill in.")
    return None


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    reason = decide(event)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
