#!/usr/bin/env python3
"""Funnelwise core MCP server: brand folder, credentials, snapshots and reports.

No platform data here. This server is what lets skills work the same way in
Claude Desktop and Claude Code: it creates and reads the brand folder, imports
credentials without a terminal, saves data snapshots and reports under the
naming contract, and diffs a snapshot against the previous one.
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import PLUGIN_ROOT, bootstrap  # noqa: E402

bootstrap()
import yaml  # noqa: E402  (vendored)

from lib import credentials as creds  # noqa: E402
from lib import snapshots  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import (BRAND_FILE, CONNECTORS, SCOPE_FIELDS, Brand, funnelwise_home,  # noqa: E402
                           load_brand, load_yaml, set_active_brand, synced_location, validate_brand)

VERSION = load_yaml(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")["version"]  # JSON is valid YAML
CATALOG_FILE = PLUGIN_ROOT / "reference" / "skill-catalog.yaml"
FOLDERS = ("reports", "data", "notes")
OWN_PATH = ("ga4", "gsc", "spotify", "tiktok", "youtube", "instagram", "facebook")

server = Server("funnelwise", VERSION, instructions=(
    "Funnelwise core tools. Call fw_brand first in every Funnelwise workflow: it returns the active brand "
    "folder, its language and the scoped account IDs. Every report must use only those IDs. Save the numbers "
    "behind every report with fw_save_snapshot and the report with fw_save_report, then offer fw_diff_snapshot "
    "against the previous snapshot. Funnelwise is read-only: never post, reply, delete or message on any platform."
))


def _brand_summary(brand: Brand) -> dict:
    profile = brand.notes_dir() / "profile.md"
    connectors = {}
    for name in CONNECTORS:
        block = brand.connectors.get(name)
        if block:
            connectors[name] = {"via": block.get("via"), SCOPE_FIELDS[name]: block.get(SCOPE_FIELDS[name]),
                                **{k: v for k, v in block.items() if k not in ("via", SCOPE_FIELDS[name])}}
    return {
        "brand_dir": str(brand.dir),
        "brand": brand.data["brand"],
        "connectors": connectors,
        "not_connected": [c for c in CONNECTORS if c not in connectors],
        # Channels the brand has (brand.channels) that no connector reads yet: onboarding's to-do list.
        "channels_not_connected": [c for c in (brand.data["brand"].get("channels") or {})
                                   if c in CONNECTORS and c not in connectors],
        "competitors": brand.data.get("competitors") or [],
        "sponsorship": brand.data.get("sponsorship") or {},
        "credentials_dir": str(brand.credentials_dir()),
        "profile": profile.read_text(encoding="utf-8") if profile.is_file() else None,
        "folders": {f: str(brand.dir / f) for f in FOLDERS},
    }


def _write_brand_yaml(directory: Path, data: dict) -> None:
    errors = validate_brand(data)
    if errors:
        raise ToolError("Not saved, brand.yaml would be invalid:\n- " + "\n- ".join(errors))
    header = ("# Funnelwise brand settings. Edited by the onboarding skill; safe to edit by hand.\n"
              "# Never put passwords, tokens or keys in this file (they live in the credentials folder).\n")
    text = header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    tmp = directory / (BRAND_FILE + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(directory / BRAND_FILE)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Brand folder
# ---------------------------------------------------------------------------

@server.tool()
def fw_brand() -> dict:
    """Return the active brand: folder, name, language, colours, connected platforms with the account ID each
    is scoped to, competitors, sponsorship info, the credentials folder and the saved user profile
    (notes/profile.md). Call this first in every Funnelwise workflow."""
    return _brand_summary(load_brand())


@server.tool()
def fw_use_brand(folder: str) -> dict:
    """Make an existing brand folder the active one (for hosts that don't start in the brand folder).

    Args:
        folder: Absolute path of a folder that contains brand.yaml.
    """
    d = Path(folder).expanduser()
    brand = load_brand(d)
    set_active_brand(d)
    return {"active": str(d), "brand": brand.name}


@server.tool()
def fw_init_brand(folder: str, name: str, language: str, website: str = "", short: str = "",
                  colors: Optional[dict] = None, channels: Optional[dict] = None) -> dict:
    """Create a brand folder: brand.yaml plus reports/, data/ and notes/. Makes it the active brand.
    Connect platforms afterwards with fw_set_connector. Fails if brand.yaml already exists.

    Args:
        folder: Absolute path of the brand folder, e.g. "/Users/ana/Documents/Funnelwise – Acme". Created if missing.
        name: Brand name as it should appear in reports.
        language: Report language code, e.g. "en", "bg", "de".
        website: Brand website, starting with https:// (optional).
        short: Short name or abbreviation (optional).
        colors: Optional {"primary": "#RRGGBB", "accent": "#RRGGBB"} for HTML reports.
        channels: Public link or handle of each channel the brand has, connected or not, e.g.
            {"youtube": "https://www.youtube.com/@acme", "instagram": "https://www.instagram.com/acme/"}.
            Keys: youtube, instagram, facebook, tiktok, spotify, linkedin, x.
    """
    d = Path(folder).expanduser()
    if (d / BRAND_FILE).exists():
        raise ToolError(f"{d / BRAND_FILE} already exists. Use fw_use_brand to select it, or fw_update_brand to change it.")
    brand = {"name": name, "language": language}
    if short:
        brand["short"] = short
    if website:
        brand["website"] = website
    if colors:
        brand["colors"] = colors
    if channels:
        brand["channels"] = {k: v.strip() if isinstance(v, str) else v for k, v in channels.items()}
    data = {"brand": brand, "connectors": {}, "competitors": [], "sponsorship": {"past_sponsors": []}}
    errors = validate_brand(data)
    if errors:
        raise ToolError("Not created:\n- " + "\n- ".join(errors))
    d.mkdir(parents=True, exist_ok=True)
    skeleton = PLUGIN_ROOT / "templates" / "brand-folder"
    for f in FOLDERS:
        (d / f).mkdir(exist_ok=True)
    for src in skeleton.rglob("README.md"):
        dest = d / src.relative_to(skeleton)
        if not dest.exists():
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _write_brand_yaml(d, data)
    gitignore = d / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".credentials/\n*.tmp\n", encoding="utf-8")
    set_active_brand(d)
    return _brand_summary(load_brand(d))


@server.tool()
def fw_update_brand(patch: dict) -> dict:
    """Change brand.yaml's brand, competitors or sponsorship sections. `patch` is merged into the file;
    a key set to null is removed. Lists (competitors, past_sponsors) are replaced as a whole.
    Use fw_set_connector for connectors.

    Args:
        patch: e.g. {"brand": {"colors": {"primary": "#0A5"}}, "sponsorship": {"past_sponsors": ["Acme"]}}
    """
    if "connectors" in patch:
        raise ToolError("Use fw_set_connector / fw_remove_connector to change connectors.")
    brand = load_brand()
    _write_brand_yaml(brand.dir, _deep_merge(brand.data, patch))
    return _brand_summary(load_brand(brand.dir))


@server.tool()
def fw_set_connector(connector: str, via: str, scope_id: str = "", extra: Optional[dict] = None) -> dict:
    """Connect a platform in brand.yaml: how it is connected and which account it is scoped to.

    Args:
        connector: One of ga4, gsc, youtube, instagram, facebook, tiktok, spotify, semrush.
        via: "own" (Funnelwise's local server with your own credentials: the normal path for every platform),
            "windsor", "google-ga4-mcp", "semrush" or "manual" (numbers typed in or exported by hand).
        scope_id: The one account this brand uses: GA4 property ID, Search Console site URL
            (https://www.example.com/ or sc-domain:example.com), YouTube channel ID (UC…), Instagram or
            TikTok username (no @), Facebook Page ID, Spotify show ID, Semrush domain.
        extra: Optional extra fields: youtube.handle, instagram.business_account_id, semrush.database.
    """
    if connector not in CONNECTORS:
        raise ToolError(f"Unknown connector `{connector}`. Known: {', '.join(CONNECTORS)}")
    brand = load_brand()
    block = {"via": via}
    if scope_id:
        block[SCOPE_FIELDS[connector]] = scope_id.strip()
    block.update(extra or {})
    data = copy.deepcopy(brand.data)
    data.setdefault("connectors", {})
    data["connectors"] = data["connectors"] or {}
    data["connectors"][connector] = block
    _write_brand_yaml(brand.dir, data)
    return {"saved": {connector: block}, "status": _connection_status(load_brand(brand.dir))[connector]}


@server.tool()
def fw_remove_connector(connector: str) -> dict:
    """Disconnect a platform: remove its block from brand.yaml. Credential files are left untouched.

    Args:
        connector: One of ga4, gsc, youtube, instagram, facebook, tiktok, spotify, semrush.
    """
    brand = load_brand()
    data = copy.deepcopy(brand.data)
    if not (data.get("connectors") or {}).pop(connector, None):
        raise ToolError(f"`{connector}` is not connected.")
    _write_brand_yaml(brand.dir, data)
    return {"removed": connector}


# ---------------------------------------------------------------------------
# Connections and credentials
# ---------------------------------------------------------------------------

def _connection_status(brand: Brand) -> Dict[str, dict]:
    out = {}
    for name in CONNECTORS:
        block = brand.connectors.get(name)
        if not block:
            out[name] = {"connected": False}
            continue
        status = {"connected": True, "via": block["via"], "scope_id": block.get(SCOPE_FIELDS[name])}
        if block["via"] == "own" and name in OWN_PATH:
            status["credentials"] = creds.connector_credentials(brand, name)
        elif block["via"] == "manual":
            status["note"] = "Numbers come from files or exports the user adds; no live connection."
        else:
            status["note"] = (f"Connected through the {block['via']} connector, which the user adds in Claude's "
                              "connector settings. Check it is enabled before running a report.")
        out[name] = status
    return out


@server.tool()
def fw_connection_status() -> dict:
    """For every platform: is it connected in brand.yaml, how, which account it is scoped to, and (for
    Funnelwise's own servers) whether the credential files are in place, with the next step if not.
    Makes no network calls; the connection-check skill does the live test."""
    brand = load_brand()
    out = {"brand": brand.name, "credentials_dir": str(brand.credentials_dir()), "connectors": _connection_status(brand)}
    synced = synced_location(brand.credentials_dir())
    if synced:
        out["warning"] = (f"The credentials folder is synced by {synced}, so the keys in it leave this computer. "
                          f"Move it to {funnelwise_home() / 'credentials' / brand.slug}.")
    return out


def _open_in_editor(path: str) -> bool:
    cmd = {"darwin": ["open", "-t", path], "win32": ["notepad", path]}.get(sys.platform, ["xdg-open", path])
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


@server.tool()
def fw_prepare_credentials(connector: str, open_in_editor: bool = True) -> dict:
    """Create the credential file(s) a platform needs, filled with "<paste …>" placeholders, in the brand's
    private credentials folder (mode 600, never overwrites a file). The user replaces the placeholders in a
    text editor and saves; the secrets never pass through the chat. Check progress with fw_connection_status
    (it names fields that are still placeholders, never values). Never read these files yourself.

    Args:
        connector: youtube, instagram, facebook (Instagram and Facebook share one file), spotify, tiktok.
            ga4/gsc use a downloaded key: fw_import_credential.
        open_in_editor: Open each new or unfinished file in the computer's text editor.
    """
    brand = load_brand()
    out = creds.prepare_templates(brand, connector)
    if open_in_editor:
        for f in out["files"]:
            if f["to_fill"]:
                f["opened_in_editor"] = _open_in_editor(f["file"])
    return out


@server.tool()
def fw_import_credential(kind: str, source_path: str) -> dict:
    """Copy a downloaded credential file (e.g. a Google service-account key) into this brand's private
    credentials folder, check it has the right fields, and lock it to this user (mode 600).
    Preferred over fw_save_credential because the secret never passes through the chat.

    Args:
        kind: google-service-account, google-oauth-client, meta, spotify or tiktok.
        source_path: Absolute path of the downloaded .json file, e.g. ~/Downloads/acme-1234.json.
    """
    brand = load_brand()
    path = creds.import_credential_file(brand, kind, source_path)
    result = {"saved_to": str(path)}
    if kind == "google-service-account":
        email = load_yaml(path)["client_email"]
        result["next_step"] = (f"Add {email} as a user: in Google Analytics (Admin > Property access management, "
                               "role Viewer) and in Search Console (Settings > Users and permissions, Restricted).")
        result["service_account_email"] = email
    result["delete_the_download"] = f"You can now delete the original file: {source_path}"
    return result


@server.tool()
def fw_save_credential(kind: str, values: dict) -> dict:
    """Save credential values (e.g. a Spotify client ID and secret) to this brand's private credentials folder.
    Values typed into the chat are part of the conversation: prefer fw_prepare_credentials (the user fills a
    file) or fw_import_credential (a downloaded file). Use this only if the user insists.

    Args:
        kind: spotify ({client_id, client_secret}), tiktok ({client_key, client_secret}), meta ({access_token}).
        values: The fields listed for the kind.
    """
    if kind in ("google-service-account", "google-oauth-client"):
        raise ToolError("Google credentials come as a downloaded file: use fw_import_credential.")
    brand = load_brand()
    return {"saved_to": str(creds.write_credential(brand, kind, values))}


# ---------------------------------------------------------------------------
# Snapshots and reports
# ---------------------------------------------------------------------------

@server.tool()
def fw_save_snapshot(topic: str, stamp: str, period_from: str, period_to: str, metrics: dict,
                     source: Optional[dict] = None, caveats: Optional[List[str]] = None,
                     extra: Optional[dict] = None, overwrite: bool = False) -> dict:
    """Save the numbers behind a report to data/<topic>-<stamp>.json. Metric ids must come from
    reference/metrics.yaml (see fw_metrics); anything else (tables, top posts, query lists) goes in `extra`.

    Args:
        topic: Report topic, lowercase-with-dashes, normally the skill name, e.g. "media-kit".
        stamp: YYYY-MM for the monthly snapshot, or YYYY-MM-DD for an extra one in the same month.
        period_from: First day the numbers cover, YYYY-MM-DD.
        period_to: Last day the numbers cover, YYYY-MM-DD.
        metrics: {metric id: number or null}. Use null when a metric could not be fetched.
        source: {metric id: connector/tool it came from}, e.g. {"youtube.subscribers": "youtube_get_channel"}.
        caveats: Data limitations the report mentions, e.g. "TikTok not connected".
        extra: Any other structured data the report used, kept for custom reports later.
        overwrite: Replace an existing snapshot with the same topic and stamp.
    """
    brand = load_brand()
    path = snapshots.save_snapshot(brand, topic, stamp, period_from, period_to, metrics, source or {},
                                   caveats or [], extra, overwrite)
    earlier = [p for p in snapshots.list_snapshots(brand, topic) if p != path and p.name < path.name]
    return {"saved_to": str(path), "previous_snapshot": earlier[-1].name if earlier else None}


@server.tool()
def fw_list_snapshots(topic: str = "") -> dict:
    """List saved data snapshots, optionally for one topic, oldest first, with the period each covers.

    Args:
        topic: Optional topic, e.g. "media-kit". Empty lists every snapshot in data/.
    """
    brand = load_brand()
    d = brand.data_dir()
    if topic:
        paths = snapshots.list_snapshots(brand, topic)
    else:
        paths = sorted(d.glob("*.json")) if d.is_dir() else []
    out = []
    for p in paths:
        try:
            doc = snapshots.read_snapshot(p)
            out.append({"file": p.name, "topic": doc.get("topic"), "period": doc.get("period"),
                        "metrics": len(doc.get("metrics", {}))})
        except ToolError:
            out.append({"file": p.name, "error": "unreadable"})
    return {"data_dir": str(d), "snapshots": out}


@server.tool()
def fw_read_snapshot(file: str) -> dict:
    """Read one snapshot from data/ (for custom reports that reuse earlier numbers).

    Args:
        file: File name in data/, e.g. "media-kit-2026-10.json".
    """
    brand = load_brand()
    path = (brand.data_dir() / file).resolve()
    if brand.data_dir().resolve() not in path.parents:
        raise ToolError("Only files inside the brand's data/ folder can be read.")
    return snapshots.read_snapshot(path)


@server.tool()
def fw_diff_snapshot(topic: str, stamp: str = "", against: str = "") -> dict:
    """Compare a snapshot with an earlier one of the same topic: per-metric change, % change and whether it
    moved in the good direction, plus a ready-made markdown table for the report's "What changed" section.

    Args:
        topic: e.g. "media-kit".
        stamp: The newer snapshot's stamp; empty = the latest.
        against: The older snapshot's stamp; empty = the one just before `stamp`.
    """
    brand = load_brand()
    paths = snapshots.list_snapshots(brand, topic)
    if not paths:
        raise ToolError(f"No snapshots for `{topic}` yet.")
    by_stamp = {p.name[len(topic) + 1:-5]: p for p in paths}
    new_path = by_stamp.get(stamp) if stamp else paths[-1]
    if new_path is None:
        raise ToolError(f"No `{topic}` snapshot with stamp {stamp}. Available: {', '.join(by_stamp)}")
    if against:
        old_path = by_stamp.get(against)
        if old_path is None:
            raise ToolError(f"No `{topic}` snapshot with stamp {against}. Available: {', '.join(by_stamp)}")
    else:
        earlier = paths[:paths.index(new_path)]
        if not earlier:
            return {"first_snapshot": True, "message": f"{new_path.name} is the first `{topic}` snapshot; nothing to compare yet."}
        old_path = earlier[-1]
    result = snapshots.diff_snapshots(snapshots.read_snapshot(old_path), snapshots.read_snapshot(new_path))
    result.update({"previous": old_path.name, "current": new_path.name})
    return result


@server.tool()
def fw_save_report(topic: str, stamp: str, content: str, format: str = "md", overwrite: bool = False) -> dict:
    """Save a finished report to reports/<topic>-<stamp>.<md|html> in the brand folder.

    Args:
        topic: Same topic as the snapshot, e.g. "media-kit". A variant may add a suffix, e.g. "media-kit-onepager-tiktok".
        stamp: YYYY-MM or YYYY-MM-DD, same as the snapshot.
        content: The full report (Markdown, or a complete self-contained HTML document).
        format: "md" or "html".
        overwrite: Replace an existing report with the same name.
    """
    if format not in ("md", "html"):
        raise ToolError("format must be md or html.")
    brand = load_brand()
    snapshots.check_topic(topic)
    snapshots.check_stamp(stamp)
    path = brand.reports_dir() / f"{topic}-{stamp}.{format}"
    if path.exists() and not overwrite:
        raise ToolError(f"{path.name} already exists. Pass overwrite=true, or use a YYYY-MM-DD stamp.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"saved_to": str(path)}


# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------

@server.tool()
def fw_metrics(ids: Optional[List[str]] = None, platform: str = "") -> dict:
    """Look up KPI definitions from reference/metrics.yaml: name, funnel stage, unit, formula, caveats.

    Args:
        ids: Optional list of metric ids, e.g. ["youtube.engagement_rate"].
        platform: Optional platform filter: ga4, gsc, youtube, instagram, facebook, tiktok, spotify, cross.
    """
    allm = snapshots.metrics_dictionary()
    if ids:
        missing = [i for i in ids if i not in allm]
        if missing:
            raise ToolError(f"Unknown metric ids: {', '.join(missing)}")
        return {i: allm[i] for i in ids}
    return {k: v for k, v in allm.items() if not platform or v["platform"] == platform}


def _needs_met(needs: dict, connected: set) -> bool:
    if needs.get("all_of") and not set(needs["all_of"]) <= connected:
        return False
    if needs.get("any_of") and not set(needs["any_of"]) & connected:
        return False
    return True


@server.tool()
def fw_skill_catalog(role: str = "") -> dict:
    """The Funnelwise skill catalog with what each skill needs, whether it can run with the brand's current
    connections, and the suggested skills for a role. Drives onboarding, `start` and next-step hints.

    Args:
        role: Optional role id: marketing-manager, social-media-manager, seo-specialist,
            sponsorship-specialist, data-analyst, developer, other.
    """
    catalog = load_yaml(CATALOG_FILE)
    try:
        connected = set(load_brand().connectors)
    except ToolError:
        connected = set()
    skills = {}
    for sid, s in catalog["skills"].items():
        needs = s.get("needs") or {}
        missing = sorted(set(needs.get("all_of", [])) - connected)
        if needs.get("any_of") and not set(needs["any_of"]) & connected:
            missing.append("one of: " + ", ".join(needs["any_of"]))
        skills[sid] = {**s, "can_run_now": s["status"] == "available" and _needs_met(needs, connected),
                       "missing_connections": missing}
    result = {"connected": sorted(connected), "skills": skills, "roles": catalog["roles"]}
    if role:
        if role not in catalog["roles"]:
            raise ToolError(f"Unknown role `{role}`. Known: {', '.join(catalog['roles'])}")
        r = catalog["roles"][role]
        order = [r["first"], *r["then"]]
        available = [s for s in order if skills.get(s, {}).get("status") == "available"]
        fallback = [s for s in catalog["mvp_fallback_order"] if skills[s]["can_run_now"] and s not in available]
        result["for_role"] = {"role": role, "suggested_order": order, "available_now": available,
                              "fallback_mvp_skills": fallback}
    return result


if __name__ == "__main__":
    server.run()
