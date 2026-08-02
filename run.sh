#!/usr/bin/env bash
# ============================================================================
#  IncidentIQ - one-click launcher for macOS and Linux.
#
#  Run:  ./run.sh          (you may need  chmod +x run.sh  once)
#
#  Sets everything up on first run and opens the app in your browser.
# ============================================================================

set -euo pipefail
cd "$(dirname "$0")"

echo
echo "  IncidentIQ"
echo "  =========="
echo

# --- 1. Python present? -----------------------------------------------------
PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
    echo "  [X] Python 3 was not found."
    echo "      Install Python 3.10 or newer, then run this script again."
    exit 1
fi

# --- 2. Virtual environment -------------------------------------------------
if [ ! -x ".venv/bin/python" ]; then
    echo "  [1/4] Creating a virtual environment (first run only)..."
    "$PYTHON" -m venv .venv
else
    echo "  [1/4] Virtual environment found."
fi

# --- 3. Dependencies --------------------------------------------------------
echo "  [2/4] Installing dependencies (this may take a minute the first time)..."
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

# --- 4. Local configuration -------------------------------------------------
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

echo "  [3/4] Local configuration ready."

# Refuse to open an older server that is already listening on the same port.
if ! .venv/bin/python -m app.portcheck --host 127.0.0.1 --port 8000; then
    exit 1
fi

echo "  [4/4] Starting the server..."
echo
echo "  -------------------------------------------------------------"
echo "   IncidentIQ is starting at  http://127.0.0.1:8000"
echo "   Your browser will open automatically in a few seconds."
echo "   Leave this window open. Press Ctrl+C to stop."
echo "  -------------------------------------------------------------"
echo

# Open the browser once the server has had a moment to bind the port.
(
    sleep 4
    if command -v open >/dev/null; then
        open 'http://127.0.0.1:8000/?commit=12'
    elif command -v xdg-open >/dev/null; then
        xdg-open 'http://127.0.0.1:8000/?commit=12'
    fi
) >/dev/null 2>&1 &

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
