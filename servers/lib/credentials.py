"""Which credential files each connector needs, placeholder templates, and safe import.

File names match the layout of the single-brand repo this plugin grew out of,
so an existing `.credentials/` folder works unchanged.

Secrets never pass through the chat: fw_prepare_credentials writes a template
(mode 600) whose values are "<paste …>" placeholders, the user fills it in a
text editor, and the connection status reports which fields are still
placeholders without ever returning a value.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from lib.mcp_stdio import ToolError
from lib.workspace import Brand, synced_location

# kind -> (file name, required keys; "a.b" means nested)
KINDS = {
    "google-service-account": ("google-service-account.json", ["type", "client_email", "private_key"]),
    "google-oauth-client": ("client_secret.json", ["installed.client_id", "installed.client_secret"]),
    "spotify": ("spotify.json", ["client_id", "client_secret"]),
    "tiktok": ("tiktok.json", ["client_key", "client_secret"]),
    "meta": ("meta.json", ["access_token"]),
}

PLACEHOLDER = "<paste"
HELP_KEY = "_how_to"
# kind -> template written by fw_prepare_credentials. Every "<paste …>" value is for the user to replace.
TEMPLATES = {
    "google-oauth-client": {
        HELP_KEY: "Replace the two <paste …> values with your Google OAuth client (type Desktop app), keep the "
                  "quotes, save. Or replace this whole file with the client_secret_….json you downloaded. "
                  "Guide: reference/connector-guides/youtube.md",
        "installed": {
            "client_id": "<paste the Client ID here, it ends with .apps.googleusercontent.com>",
            "client_secret": "<paste the Client secret here>",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        },
    },
    "meta": {
        HELP_KEY: "Replace the <paste …> value with a Meta System User access token (read permissions only), keep "
                  "the quotes, save. It covers both Instagram and Facebook. Guide: reference/connector-guides/meta.md",
        "access_token": "<paste the System User access token here, it starts with EAA>",
    },
    "spotify": {
        HELP_KEY: "Replace the two <paste …> values from your Spotify app's Settings page, keep the quotes, save. "
                  "Guide: reference/connector-guides/spotify.md",
        "client_id": "<paste the Client ID here>",
        "client_secret": "<paste the Client secret here>",
    },
    "tiktok": {
        HELP_KEY: "Replace the two <paste …> values from your TikTok app's page, keep the quotes, save. "
                  "Guide: reference/connector-guides/tiktok.md",
        "client_key": "<paste the Client key here>",
        "client_secret": "<paste the Client secret here>",
    },
}
# connector -> template kinds it needs (Google service accounts are downloaded files: no template)
CONNECTOR_KINDS = {
    "youtube": ["google-oauth-client"],
    "instagram": ["meta"],
    "facebook": ["meta"],
    "spotify": ["spotify"],
    "tiktok": ["tiktok"],
    "ga4": [],
    "gsc": [],
}
FILE_KIND = {KINDS[k][0]: k for k in KINDS}

# For connectors running on our own/local servers: alternatives of required files.
# The first alternative whose files all exist wins.
NEEDS = {
    "ga4": [["google-service-account.json"]],
    "gsc": [["google-service-account.json"], ["client_secret.json", "gsc_token.json"]],
    "tiktok": [["tiktok.json", "tiktok_token.json"]],
    "spotify": [["spotify.json"]],
    "youtube": [["client_secret.json", "token.json"]],
    # meta.json covers both; instagram.json / facebook.json are the single-brand repo's layout.
    "instagram": [["meta.json"], ["instagram.json"]],
    "facebook": [["meta.json"], ["facebook.json"]],
}

NEXT_STEP = {
    "google-service-account.json": "Create a Google service-account key (guide: reference/connector-guides/google.md) and import it with fw_import_credential kind=google-service-account.",
    "client_secret.json": "Create a Google OAuth client of type Desktop app (guide: reference/connector-guides/youtube.md), then fill in the template from fw_prepare_credentials youtube, or import the downloaded file with kind=google-oauth-client.",
    "token.json": "Sign in to Google once with youtube_login_start, as an Owner or Manager of the brand's YouTube channel.",
    "meta.json": "Create a Meta System User token (guide: reference/connector-guides/meta.md) and paste it into the template from fw_prepare_credentials instagram (one file for Instagram and Facebook).",
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
        if node in (None, "") or is_placeholder(node):
            missing.append(key)
    return missing


def is_placeholder(value: object) -> bool:
    return isinstance(value, str) and value.strip().startswith(PLACEHOLDER)


def unfilled_fields(path: Path) -> Optional[List[str]]:
    """Fields of a known credential file still empty or "<paste …>"; None if the file isn't a known kind."""
    kind = FILE_KIND.get(path.name)
    if not kind:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["(the file is not valid JSON: check the quotes and commas)"]
    return _missing_keys(data, KINDS[kind][1]) if isinstance(data, dict) else ["(not a JSON object)"]


def _secure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    ignore = d / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")


def prepare_templates(brand: Brand, connector: str) -> Dict[str, object]:
    """Write placeholder files for a connector (never overwriting); report what the user must fill in."""
    if connector not in CONNECTOR_KINDS:
        raise ToolError(f"No credential files to prepare for `{connector}`. Known: {', '.join(CONNECTOR_KINDS)}")
    d = brand.credentials_dir()
    _secure_dir(d)
    files = []
    for kind in CONNECTOR_KINDS[connector]:
        filename = KINDS[kind][0]
        path = d / filename
        created = False
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(TEMPLATES[kind], f, indent=2)
                f.write("\n")
            created = True
        files.append({"file": str(path), "created": created, "to_fill": unfilled_fields(path)})
    out = {"credentials_dir": str(d), "files": files}  # type: Dict[str, object]
    if connector in ("ga4", "gsc"):
        out["note"] = ("Google Analytics and Search Console use a downloaded service-account key file: import it "
                       "with fw_import_credential kind=google-service-account (no template to fill).")
    synced = synced_location(d)
    if synced:
        out["warning"] = f"This folder is synced by {synced}; keys stored here leave this computer. Move it out."
    return out


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
    _secure_dir(d)
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
        if all((d / f).is_file() and not unfilled_fields(d / f) for f in files):
            return {"ready": True, "files": files, "missing": [], "next_steps": []}
    first = alternatives[0] if alternatives else []
    missing = [f for f in first if not (d / f).is_file()]
    to_fill = {f: unfilled_fields(d / f) for f in first if (d / f).is_file() and unfilled_fields(d / f)}
    steps = [f"Fill in {', '.join(fields)} in {d / f} (replace the <paste …> text), then save the file."
             for f, fields in to_fill.items()]
    return {"ready": False, "files": first, "missing": missing, "to_fill": to_fill,
            "next_steps": steps + [NEXT_STEP[f] for f in missing if f in NEXT_STEP]}
