"""Locate the active brand folder, load and validate its brand.yaml.

A brand folder (see templates/brand-folder/) holds brand.yaml, reports/,
data/ and notes/. Servers re-read brand.yaml on every tool call, so edits and
brand switches apply without restarting anything.

Lookup order for the brand folder:
  1. $FUNNELWISE_BRAND_DIR
  2. the current directory or $CLAUDE_PROJECT_DIR, or any parent of them,
     that contains brand.yaml
  3. the folder recorded in ~/.funnelwise/active-brand (written by
     fw_use_brand / fw_init_brand), for hosts that start servers elsewhere

Credentials never live in brand.yaml. Lookup order for the credentials folder:
  1. $FUNNELWISE_CREDENTIALS_DIR
  2. <brand folder>/.credentials/ if it exists
  3. ~/.funnelwise/credentials/<brand slug>/ if it exists
  4. new brands: <brand folder>/.credentials/ (hidden, git-ignored), unless the
     brand folder is synced to a cloud (iCloud, Dropbox, Google Drive,
     OneDrive): then ~/.funnelwise/credentials/<brand slug>/, so keys never
     leave this computer.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

from lib.mcp_stdio import ToolError

BRAND_FILE = "brand.yaml"
CONNECTORS = ("ga4", "gsc", "youtube", "instagram", "facebook", "tiktok", "spotify", "semrush")
VIA_OPTIONS = ("own", "windsor", "google-ga4-mcp", "semrush", "manual")
# The ID each connector is scoped to. Required when via == "own" (our servers
# enforce it); recommended otherwise so skills know which account is the brand's.
SCOPE_FIELDS = {
    "ga4": "property_id",
    "gsc": "site_url",
    "youtube": "channel_id",
    "instagram": "username",
    "facebook": "page_id",
    "tiktok": "username",
    "spotify": "show_id",
    "semrush": "domain",
}
OPTIONAL_FIELDS = {
    "youtube": ("handle",),
    "instagram": ("business_account_id",),
    "semrush": ("database",),
}
COMPETITOR_KEYS = {"name", "website", "youtube", "tiktok", "instagram", "spotify"}
# brand.channels: the public links of every channel the brand has, captured at onboarding
# whether or not the platform is connected yet. linkedin and x have no connector.
CHANNEL_KEYS = ("youtube", "instagram", "facebook", "tiktok", "spotify", "linkedin", "x")


def funnelwise_home() -> Path:
    return Path(os.environ.get("FUNNELWISE_HOME", str(Path.home() / ".funnelwise"))).expanduser()


def _active_brand_file() -> Path:
    return funnelwise_home() / "active-brand"


def _walk_up(start: Path) -> Optional[Path]:
    for d in [start, *start.parents]:
        if (d / BRAND_FILE).is_file():
            return d
    return None


def find_brand_dir() -> Optional[Path]:
    env = os.environ.get("FUNNELWISE_BRAND_DIR")
    if env:
        p = Path(env).expanduser()
        return p if (p / BRAND_FILE).is_file() else None
    starts = [Path.cwd()]
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        starts.insert(0, Path(os.environ["CLAUDE_PROJECT_DIR"]))
    for start in starts:
        found = _walk_up(start.resolve())
        if found:
            return found
    marker = _active_brand_file()
    if marker.is_file():
        p = Path(marker.read_text(encoding="utf-8").strip()).expanduser()
        if (p / BRAND_FILE).is_file():
            return p
    return None


def set_active_brand(brand_dir: Path) -> None:
    home = funnelwise_home()
    home.mkdir(parents=True, exist_ok=True)
    _active_brand_file().write_text(str(Path(brand_dir).expanduser().resolve()) + "\n", encoding="utf-8")


_SYNCED_PARTS = ("dropbox", "google drive", "googledrive", "my drive", "onedrive", "box", "pcloud drive", "icloud drive")


def synced_location(path: Path) -> Optional[str]:
    """The cloud service that syncs `path`, or None. Secrets must not be stored in such a folder."""
    p = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    for root, name in ((home / "Library" / "CloudStorage", "a cloud drive"),
                       (home / "Library" / "Mobile Documents", "iCloud Drive")):
        if root in p.parents or p == root:
            return name
    for part in p.parts:
        low = part.lower()
        if low in _SYNCED_PARTS or low.startswith(("onedrive", "dropbox")):
            return part
    # macOS "Desktop & Documents Folders" in iCloud keeps the usual paths but syncs them.
    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    for folder in ("Desktop", "Documents"):
        if (icloud / folder).is_dir() and (home / folder) in [p, *p.parents]:
            return f"iCloud Drive ({folder} sync)"
    return None


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "brand"


# ---------------------------------------------------------------------------
# Validation (mirrors schemas/brand.schema.json; tests keep the two in sync)
# ---------------------------------------------------------------------------

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LANG = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def validate_brand(data: object) -> List[str]:
    """Return a list of human-readable problems; empty means valid."""
    errors = []  # type: List[str]
    if not isinstance(data, dict):
        return ["brand.yaml must be a mapping with a `brand:` section"]
    unknown = set(data) - {"brand", "connectors", "competitors", "sponsorship"}
    errors += [f"unknown top-level key `{k}`" for k in sorted(unknown)]

    brand = data.get("brand")
    if not isinstance(brand, dict):
        errors.append("`brand:` section is missing")
    else:
        if not isinstance(brand.get("name"), str) or not brand["name"].strip():
            errors.append("brand.name is required")
        lang = brand.get("language")
        if not isinstance(lang, str) or not _LANG.match(lang):
            errors.append("brand.language must be a language code like `en`, `bg` or `pt-BR`")
        for key in ("short", "website", "logo"):
            if key in brand and not isinstance(brand[key], str):
                errors.append(f"brand.{key} must be text")
        if "website" in brand and isinstance(brand["website"], str) and not brand["website"].startswith(("http://", "https://")):
            errors.append("brand.website must start with https://")
        colors = brand.get("colors", {})
        if not isinstance(colors, dict):
            errors.append("brand.colors must be a mapping")
        else:
            for k, v in colors.items():
                if k not in ("primary", "accent") or not isinstance(v, str) or not _HEX.match(v):
                    errors.append(f"brand.colors.{k} must be `primary`/`accent` with a #RRGGBB value")
        channels = brand.get("channels", {})
        if not isinstance(channels, dict):
            errors.append("brand.channels must be a mapping like {youtube: https://youtube.com/@acme}")
        else:
            for k, v in channels.items():
                if k not in CHANNEL_KEYS:
                    errors.append(f"unknown channel brand.channels.{k} (known: {', '.join(CHANNEL_KEYS)})")
                elif not isinstance(v, str) or not v.strip():
                    errors.append(f"brand.channels.{k} must be the channel's link or handle")
        unknown = set(brand) - {"name", "short", "website", "language", "colors", "logo", "channels"}
        errors += [f"unknown key brand.{k}" for k in sorted(unknown)]

    connectors = data.get("connectors", {}) or {}
    if not isinstance(connectors, dict):
        errors.append("`connectors:` must be a mapping")
        connectors = {}
    for name, block in connectors.items():
        if name not in CONNECTORS:
            errors.append(f"unknown connector `{name}` (known: {', '.join(CONNECTORS)})")
            continue
        if not isinstance(block, dict):
            errors.append(f"connectors.{name} must be a mapping")
            continue
        via = block.get("via")
        if via not in VIA_OPTIONS:
            errors.append(f"connectors.{name}.via must be one of {', '.join(VIA_OPTIONS)}")
        field = SCOPE_FIELDS[name]
        value = block.get(field)
        if via == "own" and (value is None or str(value).strip() == ""):
            errors.append(f"connectors.{name}.{field} is required when via is `own`")
        if value is not None and not isinstance(value, (str, int)):
            errors.append(f"connectors.{name}.{field} must be text")
        if name == "gsc" and isinstance(value, str) and value and not value.startswith(("https://", "http://", "sc-domain:")):
            errors.append("connectors.gsc.site_url must be `https://…/` (URL-prefix property) or `sc-domain:…`")
        if name in ("tiktok", "instagram") and isinstance(value, str) and value.startswith("@"):
            errors.append(f"connectors.{name}.username must not start with @")
        allowed = {"via", field, *OPTIONAL_FIELDS.get(name, ())}
        errors += [f"unknown key connectors.{name}.{k}" for k in sorted(set(block) - allowed)]

    competitors = data.get("competitors", []) or []
    if not isinstance(competitors, list):
        errors.append("`competitors:` must be a list")
    else:
        for i, c in enumerate(competitors):
            if not isinstance(c, dict) or not c.get("name"):
                errors.append(f"competitors[{i}] needs a `name`")
            elif set(c) - COMPETITOR_KEYS:
                errors.append(f"competitors[{i}] has unknown keys: {', '.join(sorted(set(c) - COMPETITOR_KEYS))}")

    sponsorship = data.get("sponsorship", {}) or {}
    if not isinstance(sponsorship, dict):
        errors.append("`sponsorship:` must be a mapping")
    else:
        ps = sponsorship.get("past_sponsors", [])
        if not isinstance(ps, list) or not all(isinstance(x, str) for x in ps):
            errors.append("sponsorship.past_sponsors must be a list of names")
        cur = sponsorship.get("rate_card_currency")
        if cur is not None and (not isinstance(cur, str) or not re.match(r"^[A-Z]{3}$", cur)):
            errors.append("sponsorship.rate_card_currency must be a 3-letter code like EUR")
        errors += [f"unknown key sponsorship.{k}" for k in sorted(set(sponsorship) - {"past_sponsors", "rate_card_currency"})]
    return errors


# ---------------------------------------------------------------------------
# Brand object
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> object:
    import yaml  # vendored

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Brand:
    def __init__(self, directory: Path, data: dict):
        self.dir = Path(directory)
        self.data = data

    @property
    def name(self) -> str:
        return self.data["brand"]["name"]

    @property
    def language(self) -> str:
        return self.data["brand"]["language"]

    @property
    def slug(self) -> str:
        b = self.data["brand"]
        return slugify(b.get("short") or b["name"])

    @property
    def connectors(self) -> dict:
        return self.data.get("connectors") or {}

    def connector(self, name: str) -> dict:
        """The connector's block, or a ToolError saying it isn't set up."""
        block = self.connectors.get(name)
        if not block:
            raise ToolError(
                f"`{name}` is not connected for {self.name}: brand.yaml has no connectors.{name} block. "
                "Run the onboarding skill to connect it, or skip this platform."
            )
        return block

    def scope_id(self, name: str) -> str:
        block = self.connector(name)
        field = SCOPE_FIELDS[name]
        value = block.get(field)
        if value is None or str(value).strip() == "":
            raise ToolError(f"brand.yaml connectors.{name}.{field} is empty; it is needed to scope this connector.")
        return str(value).strip()

    def competitor_ids(self, platform: str) -> List[str]:
        return [str(c[platform]).strip() for c in self.data.get("competitors") or [] if c.get(platform)]

    def credentials_dir(self) -> Path:
        env = os.environ.get("FUNNELWISE_CREDENTIALS_DIR")
        if env:
            return Path(env).expanduser()
        local = self.dir / ".credentials"
        home = funnelwise_home() / "credentials" / self.slug
        if local.is_dir():
            return local
        if home.is_dir() or synced_location(self.dir):
            return home
        return local

    def credential(self, filename: str) -> Path:
        return self.credentials_dir() / filename

    def reports_dir(self) -> Path:
        return self.dir / "reports"

    def data_dir(self) -> Path:
        return self.dir / "data"

    def notes_dir(self) -> Path:
        return self.dir / "notes"


def load_brand(brand_dir: Optional[Path] = None) -> Brand:
    """Load and validate the active brand; ToolError with next steps if missing or invalid."""
    d = Path(brand_dir) if brand_dir else find_brand_dir()
    if d is None:
        raise ToolError(
            "No brand folder found. Open your brand folder (the one with brand.yaml) or say "
            "\"Set up my brand\" to create one. A folder can also be selected with fw_use_brand."
        )
    path = d / BRAND_FILE
    try:
        data = load_yaml(path)
    except FileNotFoundError:
        raise ToolError(f"{path} does not exist.")
    except Exception as e:  # yaml.YAMLError and friends
        raise ToolError(f"{path} is not valid YAML: {e}")
    errors = validate_brand(data)
    if errors:
        raise ToolError(f"{path} has problems:\n- " + "\n- ".join(errors))
    return Brand(d, data)  # type: ignore[arg-type]
