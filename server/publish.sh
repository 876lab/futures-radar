#!/usr/bin/env bash
# publish.sh BRANCH FILE...  -> replaces BRANCH on GitHub with a single commit holding FILE(s) (same pattern as the GitHub jobs).
# Uses the server's own deploy key (~/.ssh/radar_deploy); the key never leaves the server.
set -euo pipefail
BRANCH="$1"; shift
REPO="${RADAR_REPO:-git@github.com:876lab/futures-radar.git}"
case "$BRANCH" in main|master|gh-pages) echo "refusing to publish to $BRANCH" >&2; exit 1;; esac   # data branches only
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
for f in "$@"; do cp "$f" "$TMP/"; done
cd "$TMP"
git init -q -b "$BRANCH"
git config user.name "futures-radar server"
git config user.email "server@futures-radar.invalid"
git add -A
git commit -q -m "$BRANCH $(date -u +%Y-%m-%dT%H:%MZ)"
GIT_SSH_COMMAND="${RADAR_SSH:-ssh -i $HOME/.ssh/radar_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new}" \
  git push -q -f "$REPO" "$BRANCH"
