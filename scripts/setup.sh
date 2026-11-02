#!/usr/bin/env bash
# One-time setup (macOS / Linux). Python 3.10+.
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
echo "Done. Put your key in .env (MODEL_API_KEY=...), then: . .venv/bin/activate && python scripts/spike.py"
