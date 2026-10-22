"""Plugin layout, catalog consistency, and the release rules from plan §1 (no customer identifiers)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

import pytest
import yaml

from conftest import ROOT
from lib.snapshots import metrics_dictionary

CATALOG = yaml.safe_load((ROOT / "reference" / "skill-catalog.yaml").read_text())
SKILL_DIRS = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    return yaml.safe_load(m.group(1))


def test_available_skills_match_skill_folders():
    available = sorted(k for k, v in CATALOG["skills"].items() if v["status"] == "available")
    assert available == SKILL_DIRS


@pytest.mark.parametrize("skill", SKILL_DIRS)
def test_skill_frontmatter(skill):
    fm = frontmatter(ROOT / "skills" / skill / "SKILL.md")
    assert fm["name"] == skill
    assert 80 <= len(fm["description"]) <= 1024


def test_catalog_references_resolve():
    metrics = metrics_dictionary()
    skills = CATALOG["skills"]
    for sid, s in skills.items():
        assert s["status"] in ("available", "planned"), sid
        for mid in s.get("metrics", []):
            assert mid in metrics, f"{sid}: unknown metric {mid}"
        needs = s.get("needs") or {}
        assert set(needs) <= {"any_of", "all_of"}, sid
        for n in s.get("next", []):
            assert n["skill"] in skills and n["why"], f"{sid}: bad next {n}"
        for role in s.get("roles", []):
            assert role == "all" or role in CATALOG["roles"], f"{sid}: unknown role {role}"
    for rid, r in CATALOG["roles"].items():
        for sid in [r["first"], *r["then"]]:
            assert sid in skills, f"role {rid}: unknown skill {sid}"
    assert all(skills[s]["status"] == "available" for s in CATALOG["mvp_fallback_order"])


def test_skill_files_only_name_real_tools_and_files():
    """Every `fw_*`/`gsc_*`/`ga_*`/`tiktok_*`/`spotify_*` tool a skill mentions must exist, and every repo path too."""
    import core
    import ga4
    import search_console
    import spotify
    import tiktok
    tools = set()
    for mod in (core, ga4, search_console, spotify, tiktok):
        tools |= set(mod.server.tools)
    texts = {p: p.read_text() for p in list((ROOT / "skills").glob("*/SKILL.md")) + list((ROOT / "reference").rglob("*.md"))}
    for path, text in texts.items():
        for name in set(re.findall(r"\b((?:fw|gsc|ga|tiktok|spotify)_[a-z_]+)\(", text)) | set(re.findall(r"`((?:fw|gsc|ga|tiktok|spotify)_[a-z_]+)`", text)):
            assert name in tools, f"{path.relative_to(ROOT)} mentions unknown tool {name}"
        for ref in re.findall(r"`((?:reference|docs|templates|schemas|skills)/[^`*<>]+?\.(?:md|yaml|json))`", text):
            assert (ROOT / ref).exists(), f"{path.relative_to(ROOT)} links missing {ref}"


def test_manifests():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["name"] == "funnelwise" == market["plugins"][0]["name"]
    assert plugin["version"] == market["plugins"][0]["version"]
    assert not (ROOT / "bin").exists(), "a top-level bin/ blocks installation in Cowork"
    mcp = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]
    for name, spec in mcp.items():
        assert spec["command"] == "python3", name
        assert (ROOT / spec["args"][0].replace("${CLAUDE_PLUGIN_ROOT}/", "")).is_file(), name


# First 16 hex chars of sha256(lowercased token) for the first customer's names, account IDs and the
# owner's e-mail, so the identifiers themselves never enter the repo. Add more with:
#   python3 -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].lower().encode()).hexdigest()[:16])" <id>
FORBIDDEN_HASHES = {"4ccb0b5b70eb863a", "ffe47267cc675deb", "e7086e23c66b5e91", "8c9d2fbe281f887f",
                    "78b00895c18958ee", "332f3bdddb890ecf", "b2129a05faa0d5b2"}
TOKEN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[a-z0-9]+")


def forbidden_tokens(line):
    return [t for t in TOKEN.findall(line.lower())
            if hashlib.sha256(t.encode()).hexdigest()[:16] in FORBIDDEN_HASHES]


def test_forbidden_token_matcher(monkeypatch):
    monkeypatch.setattr(__import__(__name__), "FORBIDDEN_HASHES",
                        {hashlib.sha256(b"acme").hexdigest()[:16], hashlib.sha256(b"ana@acme.example").hexdigest()[:16]})
    assert forbidden_tokens("see https://www.ACME.example/x, Ana@acme.example") == ["acme", "ana@acme.example"]
    assert forbidden_tokens("Acmer Coffee, property 123456789") == []


def test_no_customer_identifiers_in_product():
    """Plan §1 success criterion 5. Scans every tracked-or-new file, not just servers/."""
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    assert files, "git file list is empty"
    hits = []
    for f in files:
        p = ROOT / f
        if f.startswith("memory/") or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if forbidden_tokens(line):
                hits.append(f"{f}:{i}: {line.strip()[:100]}")
    assert not hits, "Customer identifiers found:\n" + "\n".join(hits)


SECRET = re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----\n[A-Za-z0-9+/]{40}|EAA[A-Za-z0-9]{40,}|ya29\.[A-Za-z0-9_-]{30,}|"
                    r"\"client_secret\"\s*:\s*\"[A-Za-z0-9_-]{20,}\"|AIza[0-9A-Za-z_-]{35}")


def test_no_secrets_committed():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    hits = [f for f in files if (ROOT / f).is_file() and not f.startswith("servers/_vendor/")
            and SECRET.search((ROOT / f).read_text(encoding="utf-8", errors="ignore"))]
    assert not hits, f"possible secrets in: {hits}"


def test_internal_notes_are_not_packaged():
    script = (ROOT / "dev" / "package.sh").read_text()
    assert "memory/" in script and "CLAUDE" in script
