#!/usr/bin/env python3
"""Launch a pinned third-party MCP server (YouTube, Instagram, Facebook) for the active brand.

    python3 thirdparty.py youtube|instagram|facebook

These servers are Python packages that need `uv` (developer path, plan §5.2).
The launcher fills in credentials from the brand's credentials folder and the
scoped IDs from brand.yaml, then replaces itself with the real server.

When it can't start the real server (platform not set to `via: own`, no `uv`,
missing credentials), it runs a stub server instead with one tool that explains
what to do, so the marketer sees a clear next step rather than a failed connector.

The real servers also list write tools (post, reply, delete, DM). The
Funnelwise write guard hook (hooks/write_guard.py) blocks them.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, funnelwise_home, load_brand  # noqa: E402

IG_MCP_COMMIT = "549fbeedc7f4409556a88d9d462e5f7ea454ca6a"
FB_MCP_COMMIT = "61b2128555d7582b19daf772186c03bc051c1c05"
YOUTUBE_MCP_VERSION = "0.1.0"

EASY_PATH = {
    "youtube": "Connect YouTube through Metricool in Claude's connector settings (see reference/connector-guides/youtube.md).",
    "instagram": "Connect Instagram through Metricool in Claude's connector settings (see reference/connector-guides/meta.md).",
    "facebook": "Connect Facebook through Metricool in Claude's connector settings (see reference/connector-guides/meta.md).",
}


def _uv() -> Optional[str]:
    for c in (shutil.which("uv"), str(Path.home() / ".local/bin/uv"), "/opt/homebrew/bin/uv", "/usr/local/bin/uv"):
        if c and Path(c).exists():
            return c
    return None


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ToolError(f"Missing credential file {path}.")
    except ValueError:
        raise ToolError(f"{path} is not valid JSON.")


def _vendor_clone(repo: str, commit: str, name: str) -> Path:
    """Pinned checkout under ~/.funnelwise/vendor/ (no pyproject upstream, so not uv-installable)."""
    d = funnelwise_home() / "vendor" / name
    git = shutil.which("git")
    if not git:
        raise ToolError("git is needed to fetch the Facebook connector.")
    if not (d / ".git").is_dir():
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([git, "clone", "--quiet", repo, str(d)], check=True, stdout=sys.stderr)
    head = subprocess.run([git, "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        subprocess.run([git, "-C", str(d), "fetch", "--quiet", "origin", commit], check=True, stdout=sys.stderr)
        subprocess.run([git, "-C", str(d), "checkout", "--quiet", commit], check=True, stdout=sys.stderr)
    return d


def plan_launch(name: str, brand: Brand, uv: str) -> Tuple[List[str], Dict[str, str], Optional[Path]]:
    """Return (argv, extra env, cwd) for the real server. Raises ToolError with the reason if it can't start."""
    block = brand.connector(name)
    if block.get("via") != "own":
        raise ToolError(f"{name} is connected via {block.get('via')}, not Funnelwise's local server. "
                        f"Use the {block.get('via')} connector's tools for {name}.")
    d = brand.credentials_dir()
    if name == "youtube":
        if not (d / "client_secret.json").is_file():
            raise ToolError(f"Missing {d / 'client_secret.json'} (Google OAuth client).")
        env = {"YOUTUBE_MCP_CLIENT_SECRET": str(d / "client_secret.json"), "YOUTUBE_MCP_CONFIG_DIR": str(d),
               "OAUTHLIB_RELAX_TOKEN_SCOPE": "1"}
        return [uv, "tool", "run", "--with", "mcp<2", f"youtube-studio-mcp=={YOUTUBE_MCP_VERSION}"], env, None
    if name == "instagram":
        c = _read(d / "instagram.json")
        account = str(block.get("business_account_id") or c["business_account_id"])
        if str(c.get("business_account_id")) != account:
            raise ToolError("instagram.json belongs to a different business account than brand.yaml "
                            "connectors.instagram.business_account_id. Refusing to start.")
        env = {"INSTAGRAM_ACCESS_TOKEN": c["access_token"], "FACEBOOK_APP_ID": c["app_id"],
               "FACEBOOK_APP_SECRET": c["app_secret"], "INSTAGRAM_BUSINESS_ACCOUNT_ID": account}
        # The package's console script never awaits main(); run the module so its __main__ guard does.
        return [uv, "tool", "run", "--from", f"git+https://github.com/jlbadano/ig-mcp.git@{IG_MCP_COMMIT}",
                "--with", "mcp<2", "python", "-m", "src.instagram_mcp_server"], env, None
    if name == "facebook":
        c = _read(d / "facebook.json")
        page = brand.scope_id("facebook")
        if str(c.get("page_id")) != page:
            raise ToolError(f"facebook.json is for Page {c.get('page_id')}, but brand.yaml says {page}. Refusing to start.")
        repo = _vendor_clone("https://github.com/HagaiHen/facebook-mcp-server.git", FB_MCP_COMMIT, "facebook-mcp-server")
        env = {"FACEBOOK_ACCESS_TOKEN": c["access_token"], "FACEBOOK_PAGE_ID": page}
        return [uv, "run", "--quiet", "--with", "mcp[cli]<2", "--with", "python-dotenv", "--with", "requests",
                "mcp", "run", "server.py"], env, repo
    raise ToolError(f"Unknown third-party connector {name}")


def run_stub(name: str, reason: str) -> None:
    stub = Server(f"funnelwise-{name}-unavailable", instructions=f"The {name} connector is not running: {reason}")

    def explain() -> dict:
        return {"connector": name, "running": False, "reason": reason, "easy_path": EASY_PATH.get(name, ""),
                "developer_path": "Install uv (https://docs.astral.sh/uv/), set via: own in brand.yaml, add the "
                                  "credentials, then restart Claude."}

    explain.__name__ = f"{name}_connection_help"
    explain.__doc__ = f"Why the {name} connector isn't available on this computer and how to connect it."
    stub.tool()(explain)
    stub.run()


def main(name: str) -> None:
    try:
        brand = load_brand()
        uv = _uv()
        if not uv:
            raise ToolError("This computer has no `uv`, which the local YouTube/Instagram/Facebook connectors need.")
        argv, env, cwd = plan_launch(name, brand, uv)
    except (ToolError, subprocess.CalledProcessError) as e:
        run_stub(name, str(e))
        return
    if cwd:
        os.chdir(cwd)
    os.execvpe(argv[0], argv, {**os.environ, **env})


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in EASY_PATH:
        sys.exit("usage: thirdparty.py youtube|instagram|facebook")
    main(sys.argv[1])
