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
