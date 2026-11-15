#!/usr/bin/env bash
# Upload the app to PythonAnywhere and reload it.
# Needs Goals2026_PA_TOKEN (API token of the Goals2026 account). Never touches config.json or goals.db on the server.
set -euo pipefail
cd "$(dirname "$0")"
H="Authorization: Token ${Goals2026_PA_TOKEN:?set Goals2026_PA_TOKEN}"
B=https://www.pythonanywhere.com/api/v0/user/Goals2026
up() { curl -sf -o /dev/null -H "$H" -F "content=@$1" "$B/files/path/home/Goals2026/goals2026/$1" && echo "uploaded $1"; }
up app.py
for f in static/*; do up "$f"; done
curl -sf -X POST -H "$H" "$B/webapps/Goals2026.pythonanywhere.com/reload/" && echo " reloaded https://goals2026.pythonanywhere.com"
