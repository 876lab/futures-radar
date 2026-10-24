#!/usr/bin/env bash
# Run every check. Exit code 0 means safe to publish.
set -euo pipefail
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
python3 tests/extract.py index.html "$TMP/app.js"
node --check "$TMP/app.js" && echo "syntax ok"
node tests/engine.js "$TMP/app.js"
python3 -m json.tool changes.json > /dev/null && echo "changes.json ok"
python3 tests/news_delist.py
python3 tests/snapshot_test.py
node scripts/backtest.js index.html "$TMP/backtest.json" --demo
python3 tests/browser.py index.html
python3 tests/stress.py index.html
echo "ALL CHECKS PASSED"
