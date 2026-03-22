#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

python3 -m PyInstaller \
  --name memory-adventure \
  --onefile \
  --windowed \
  launch_adventure.py

echo "Build complete. Executable: dist/memory-adventure"
