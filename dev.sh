#!/usr/bin/env bash
# Launch the FastAPI backend and the Angular frontend together for local development.
#
# Usage:
#   ./dev.sh
#
# Stops both servers on Ctrl+C (or if either one exits/crashes).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

cleanup() {
    echo
    echo "Stopping dev servers..."
    [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
    [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend on http://localhost:8000 ..."
uv run --group api uvicorn api.main:app --reload --port 8000 &
API_PID=$!

echo "Starting Angular frontend on http://localhost:4200 ..."
(
    cd webapp
    # Use the Node version pinned in webapp/.nvmrc if nvm is available, so the
    # correct Angular CLI-compatible runtime is used regardless of the shell's
    # default/active Node version.
    if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
        # shellcheck disable=SC1091
        source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
        nvm use --silent >/dev/null || nvm install >/dev/null
    fi
    pnpm start
) &
WEB_PID=$!

wait "$API_PID" "$WEB_PID"
