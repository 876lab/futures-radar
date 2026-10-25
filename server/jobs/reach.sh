#!/usr/bin/env bash
# every: 60
# Heartbeat and reach check: can this server get data from each exchange (and the SEC)?
# Publishes server-status.json to the server-data branch. GitHub's own servers are blocked by Binance, Bybit and the SEC,
# so this answers whether the cloud server can take over those jobs.
set -euo pipefail
OUT="$RADAR_STATE/out"; mkdir -p "$OUT"
python3 -I "$RADAR_APP/server/reach.py" "$OUT/server-status.json"
bash "$RADAR_APP/server/publish.sh" server-data "$OUT/server-status.json"
