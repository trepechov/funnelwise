#!/usr/bin/env python3
"""SessionStart hook: tell Claude which brand folder is active and what it is scoped to.

Replaces prose scoping rules in a project CLAUDE.md: the IDs now come from brand.yaml, and this summary puts
them in front of the model at the start of every session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servers"))


def summary() -> str:
    from lib import bootstrap

    bootstrap()
    from lib.mcp_stdio import ToolError
    from lib.workspace import SCOPE_FIELDS, find_brand_dir, load_brand

    d = find_brand_dir()
    if d is None:
        return ("Funnelwise is installed, but this folder is not a Funnelwise brand folder (no brand.yaml). "
                "If the user asks for marketing reports, media kits or SEO/social analysis, offer the "
                "`onboarding` skill (\"Set up my brand\") or ask which brand folder to use (fw_use_brand).")
    try:
        brand = load_brand(d)
    except ToolError as e:
        return f"Funnelwise brand folder {d} has a brand.yaml problem; fix it before running reports:\n{e}"

    lines = [f"Funnelwise brand: {brand.name} (folder: {brand.dir}). Write reports in language `{brand.language}`."]
    if brand.connectors:
        lines.append("Connected platforms and the ONLY accounts to use:")
        for name, block in brand.connectors.items():
            lines.append(f"- {name}: {block.get(SCOPE_FIELDS[name], '(no ID)')} via {block.get('via')}")
    else:
        lines.append("No platforms connected yet: suggest the `onboarding` skill.")
    lines.append("Rules: read-only (never post, reply, delete or message on a platform); never use other accounts "
                 "a credential can see; save numbers with fw_save_snapshot and reports with fw_save_report; "
                 "for YouTube pass the channel ID, never `mine: true`.")
    profile = brand.notes_dir() / "profile.md"
    if profile.is_file():
        text = profile.read_text(encoding="utf-8").strip()
        lines.append("User profile (notes/profile.md), use it silently to shape suggestions:\n" + text[:1500])
    else:
        lines.append("No user profile yet (notes/profile.md): the onboarding skill captures role and goal.")
    return "\n".join(lines)


def main() -> None:
    try:
        context = summary()
    except Exception as e:  # never break session start
        context = f"Funnelwise could not read the brand folder: {type(e).__name__}: {e}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))


if __name__ == "__main__":
    main()
