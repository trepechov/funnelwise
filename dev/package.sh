#!/bin/bash
# Build dist/funnelwise-<version>.plugin (a zip) for uploading in Claude Desktop:
# Settings → Plugins → upload. Tests, dev tools and caches are left out.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')"
OUT="dist/funnelwise-$VERSION.plugin"
mkdir -p dist
rm -f "$OUT"
git ls-files --cached --others --exclude-standard \
  | grep -vE '^(tests/|dev/|dist/|memory/|CLAUDE\.md$|pyproject\.toml$|\.gitignore$)' \
  | zip -q "$OUT" -@
echo "Built $OUT ($(du -h "$OUT" | cut -f1))"
