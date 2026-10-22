from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from conftest import DEMO_BRAND, ROOT
from lib.mcp_stdio import ToolError
from lib.workspace import find_brand_dir, load_brand, set_active_brand, slugify, validate_brand

SCHEMA = json.loads((ROOT / "schemas" / "brand.schema.json").read_text())


def mutate(**changes) -> dict:
    d = copy.deepcopy(DEMO_BRAND)
    for path, value in changes.items():
        node = d
        keys = path.split("__")
        for k in keys[:-1]:
            node = node[k]
        if value is KeyError:
            node.pop(keys[-1])
        else:
            node[keys[-1]] = value
    return d


VALID = [
    DEMO_BRAND,
    {"brand": {"name": "Solo", "language": "bg"}},
    {"brand": {"name": "Solo", "language": "pt-BR"}, "connectors": {}, "competitors": [], "sponsorship": {}},
    {"brand": {"name": "X", "language": "en"}, "connectors": {"instagram": {"via": "metricool"}}},
    {"brand": {"name": "X", "language": "en"}, "connectors": {"gsc": {"via": "own", "site_url": "sc-domain:x.com"}}},
    yaml.safe_load((ROOT / "templates" / "brand.example.yaml").read_text()),
    yaml.safe_load((ROOT / "examples" / "demo-brand" / "brand.yaml").read_text()),
]

INVALID = [
    ("not a mapping", ["a", "list"]),
    ("missing brand", {"connectors": {}}),
    ("missing name", mutate(brand__name=KeyError)),
    ("blank name", mutate(brand__name="  ")),
    ("bad language", mutate(brand__language="English")),
    ("bad colour", mutate(brand__colors={"primary": "green"})),
    ("unknown colour key", mutate(brand__colors={"secondary": "#000000"})),
    ("website without scheme", mutate(brand__website="acme.example")),
    ("unknown top key", {**DEMO_BRAND, "extra": 1}),
    ("unknown brand key", mutate(brand__tagline="hi")),
    ("unknown connector", mutate(connectors__linkedin={"via": "own"})),
    ("bad via", mutate(connectors__ga4={"via": "magic", "property_id": "1"})),
    ("own without id", mutate(connectors__ga4={"via": "own"})),
    ("own with empty id", mutate(connectors__spotify={"via": "own", "show_id": ""})),
    ("gsc url form", mutate(connectors__gsc={"via": "own", "site_url": "www.acme.example"})),
    ("tiktok @", mutate(connectors__tiktok={"via": "own", "username": "@acme"})),
    ("unknown connector key", mutate(connectors__ga4={"via": "own", "property_id": "1", "token": "x"})),
    ("competitor without name", mutate(competitors=[{"website": "https://x"}])),
    ("competitor unknown key", mutate(competitors=[{"name": "x", "linkedin": "y"}])),
    ("bad currency", mutate(sponsorship={"rate_card_currency": "euro"})),
    ("past sponsors not list", mutate(sponsorship={"past_sponsors": "Acme"})),
    ("unknown sponsorship key", mutate(sponsorship={"rate": 5})),
]


@pytest.mark.parametrize("data", VALID)
def test_valid_brands_pass_both_validators(data):
    assert validate_brand(data) == []
    jsonschema.validate(data, SCHEMA)


@pytest.mark.parametrize("label,data", INVALID, ids=[i[0] for i in INVALID])
def test_invalid_brands_fail_both_validators(label, data):
    assert validate_brand(data), label
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, SCHEMA)


def _write(d: Path, data=DEMO_BRAND) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "brand.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return d


def test_find_brand_dir_order(tmp_path, monkeypatch):
    assert find_brand_dir() is None
    marked = _write(tmp_path / "marked")
    set_active_brand(marked)
    assert find_brand_dir() == marked.resolve()
    walked = _write(tmp_path / "walk")
    (walked / "reports" / "deep").mkdir(parents=True)
    monkeypatch.chdir(walked / "reports" / "deep")
    assert find_brand_dir() == walked.resolve()  # cwd walk-up beats the marker
    project = _write(tmp_path / "project")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    assert find_brand_dir() == project.resolve()  # project dir beats cwd
    env = _write(tmp_path / "env")
    monkeypatch.setenv("FUNNELWISE_BRAND_DIR", str(env))
    assert find_brand_dir() == env  # explicit env beats everything
    monkeypatch.setenv("FUNNELWISE_BRAND_DIR", str(tmp_path / "missing"))
    assert find_brand_dir() is None  # explicit but wrong: don't silently fall back


def test_load_brand_errors(tmp_path):
    with pytest.raises(ToolError, match="No brand folder found"):
        load_brand()
    d = tmp_path / "bad"
    d.mkdir()
    (d / "brand.yaml").write_text("brand: [unclosed", encoding="utf-8")
    with pytest.raises(ToolError, match="not valid YAML"):
        load_brand(d)
    _write(d, {"brand": {"name": "x"}})
    with pytest.raises(ToolError, match="brand.language"):
        load_brand(d)


def test_brand_accessors_and_credentials_dir(brand_dir, tmp_path, monkeypatch):
    b = load_brand()
    assert b.name == "Acme Outdoor" and b.language == "en" and b.slug == "acme"
    assert b.scope_id("spotify") == "0000000000000000000001"
    assert b.competitor_ids("youtube") == ["UCtrail00000000000000000"]
    with pytest.raises(ToolError, match="not connected"):
        b.connector("semrush")
    assert b.credentials_dir() == brand_dir / ".credentials"  # dev path: folder exists
    (brand_dir / ".credentials").rmdir()
    assert b.credentials_dir() == tmp_path / "fwhome" / "credentials" / "acme"  # default: outside the folder
    monkeypatch.setenv("FUNNELWISE_CREDENTIALS_DIR", str(tmp_path / "c"))
    assert b.credentials_dir() == tmp_path / "c"


def test_slugify():
    assert slugify("Acme Coffee by Ana") == "acme-coffee-by-ana"
    assert slugify("Ünïcode Brand!") == "n-code-brand"
    assert slugify("!!!") == "brand"
