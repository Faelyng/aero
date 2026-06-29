#!/bin/bash
# Build Aero Mission Planner for Linux or macOS.
# Run from the project root with the venv active, or let it activate automatically.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/pyinstaller" ]; then
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYINSTALLER="pyinstaller"
fi

"$PYINSTALLER" aero.spec --noconfirm
echo ""
echo "Build complete: dist/Aero Mission Planner/"
