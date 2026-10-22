"""Which credential files each connector needs, and safe import into the credentials folder.

File names match the layout of the single-brand repo this plugin grew out of,
so an existing `.credentials/` folder works unchanged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from lib.mcp_stdio import ToolError
from lib.workspace import Brand

# kind -> (file name, required keys; "a.b" means nested)
KINDS = {
    "google-service-account": ("google-service-account.json", ["type", "client_email", "private_key"]),
    "google-oauth-client": ("client_secret.json", ["installed.client_id", "installed.client_secret"]),
    "spotify": ("spotify.json", ["client_id", "client_secret"]),
    "tiktok": ("tiktok.json", ["client_key", "client_secret"]),
}

# For connectors running on our own/local servers: alternatives of required files.
# The first alternative whose files all exist wins.
NEEDS = {
    "ga4": [["google-service-account.json"]],
    "gsc": [["google-service-account.json"], ["client_secret.json", "gsc_token.json"]],
    "tiktok": [["tiktok.json", "tiktok_token.json"]],
    "spotify": [["spotify.json"]],
}

NEXT_STEP = {
    "google-service-account.json": "Create a Google service-account key (guide: reference/connector-guides/google.md) and import it with fw_import_credential kind=google-service-account.",
    "client_secret.json": "Create a Google OAuth client of type Desktop (legacy Search Console sign-in) and import it with kind=google-oauth-client.",
    "gsc_token.json": "Legacy Search Console sign-in; prefer the service account instead.",
    "tiktok.json": "Create a TikTok developer app (guide: reference/connector-guides/tiktok.md) and save its client key/secret with kind=tiktok.",
    "tiktok_token.json": "Sign in to TikTok once with the tiktok_login_start tool, as the brand's TikTok account.",
    "spotify.json": "Create a Spotify developer app (guide: reference/connector-guides/spotify.md) and save its client ID/secret with kind=spotify.",
}


def _missing_keys(data: dict, required: List[str]) -> List[str]:
    missing = []
    for key in required:
        node = data
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if node in (None, ""):
            missing.append(key)
    return missing


def check_kind(kind: str) -> tuple:
    if kind not in KINDS:
        raise ToolError(f"Unknown credential kind `{kind}`. Known: {', '.join(KINDS)}")
    return KINDS[kind]


def write_credential(brand: Brand, kind: str, data: dict) -> Path:
    filename, required = check_kind(kind)
    missing = _missing_keys(data, required)
    if missing:
        raise ToolError(f"This {kind} credential is missing: {', '.join(missing)}.")
    if kind == "google-service-account" and data.get("type") != "service_account":
        raise ToolError("That file is not a service-account key (type must be service_account).")
    d = brand.credentials_dir()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    path = d / filename
    tmp = d / (filename + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)
    return path


def import_credential_file(brand: Brand, kind: str, source_path: str) -> Path:
    src = Path(source_path).expanduser()
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"File not found: {src}")
    except ValueError:
        raise ToolError(f"{src} is not a JSON file.")
    if not isinstance(data, dict):
        raise ToolError(f"{src} does not contain a JSON object.")
    return write_credential(brand, kind, data)


def connector_credentials(brand: Brand, connector: str) -> Dict[str, object]:
    """Which files exist / are missing for a connector on the own-server path."""
    d = brand.credentials_dir()
    alternatives = NEEDS.get(connector, [])
    for files in alternatives:
        if all((d / f).is_file() for f in files):
            return {"ready": True, "files": files, "missing": [], "next_steps": []}
    first = alternatives[0] if alternatives else []
    missing = [f for f in first if not (d / f).is_file()]
    return {"ready": False, "files": first, "missing": missing,
            "next_steps": [NEXT_STEP[f] for f in missing if f in NEXT_STEP]}
