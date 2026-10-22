# Third-party notices

## Vendored in this repository (`servers/_vendor/`)

| Component | Version | Licence | Licence file |
|---|---|---|---|
| PyYAML | 6.0.2 (pure-Python, no libyaml) | MIT | `servers/_vendor/licenses/PyYAML.LICENSE` |
| Jinja2 | 3.1.4 | BSD-3-Clause | `servers/_vendor/licenses/Jinja2.LICENSE` |
| MarkupSafe | 2.1.5 (pure-Python, C speedups removed) | BSD-3-Clause | `servers/_vendor/licenses/MarkupSafe.LICENSE` |

## Adapted code

| Component | Version | Licence | Where |
|---|---|---|---|
| mcp-google-search-console | 2.0.2 (PyPI) | MIT | `servers/gsc_audit/` (audit, HTML template, branding) and the tool set in `servers/search_console.py`. Changed: brand.yaml scoping, branding and output folder, standard-library auth. |

## Downloaded at runtime, not distributed (developer path, `servers/thirdparty.py`)

| Component | Pinned to | Licence | Source |
|---|---|---|---|
| youtube-studio-mcp | 0.1.0 (PyPI) | see package metadata | https://pypi.org/project/youtube-studio-mcp/ |
| ig-mcp | commit 549fbeedc7f4409556a88d9d462e5f7ea454ca6a | MIT | https://github.com/jlbadano/ig-mcp |
| facebook-mcp-server | commit 61b2128555d7582b19daf772186c03bc051c1c05 | MIT | https://github.com/HagaiHen/facebook-mcp-server |

These run in their own environments managed by `uv`, with their own dependencies (including the
`mcp` Python SDK, pinned `<2`).
