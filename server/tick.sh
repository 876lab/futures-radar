#!/usr/bin/env bash
# Runs every 5 minutes on the cloud server (systemd timer from server/cloud-init.yaml), as the unprivileged user "radar".
# 1. Brings the server's copy of the repo up to date with main (read-only copy; local changes are thrown away).
# 2. Runs whichever jobs in server/jobs/ are due. Each job publishes its own output to a data branch.
# Nothing here listens on the network; the server only makes outgoing requests.
set -uo pipefail
APP="${RADAR_APP:-$HOME/app}"
STATE="${RADAR_STATE:-$HOME/state}"
LOG="$STATE/tick.log"
mkdir -p "$STATE"
exec 9>"$STATE/tick.lock"; flock -n 9 || exit 0          # one tick at a time
log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG"; }
tail -n 2000 "$LOG" >"$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"   # keep the log small

if ! git -C "$APP" fetch -q --depth 1 origin main 2>>"$LOG"; then log "fetch failed"; exit 0; fi
git -C "$APP" reset -q --hard FETCH_HEAD && git -C "$APP" clean -qfdx
now=$(date -u +%s)
for job in "$APP"/server/jobs/*.sh; do
  [ -f "$job" ] || continue
  name=$(basename "$job" .sh)
  every=$(sed -n 's/^# every: *\([0-9]*\).*/\1/p' "$job" | head -1); every=${every:-60}   # minutes, from the job's header
  last=$(cat "$STATE/$name.last" 2>/dev/null || echo 0)
  [ $(( now - last )) -ge $(( every * 60 - 30 )) ] || continue
  echo "$now" >"$STATE/$name.last"
  log "run $name"
  if RADAR_APP="$APP" RADAR_STATE="$STATE" timeout 1800 bash "$job" >>"$LOG" 2>&1; then log "ok $name"; else log "FAILED $name ($?)"; fi
done
