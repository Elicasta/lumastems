#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "FFmpeg is required. Install Homebrew first, then run: brew install ffmpeg"
    exit 1
  fi
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

echo
echo "LumaStems installed."
echo "Activate later with: source .venv/bin/activate"
echo "Download the worship model with: lumastems warm --preset worship"
echo "Start the local API with: lumastems serve"
