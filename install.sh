#!/usr/bin/env bash
set -euo pipefail

echo "[DarkTrace X] Starting installation..."
PYTHON_BIN=${PYTHON_BIN:-python3}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python is not installed or not on PATH."
  exit 1
fi

PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))')
PYTHON_MAJOR=$($PYTHON_BIN -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$($PYTHON_BIN -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
  echo "ERROR: DarkTrace X requires Python 3.11 or higher. Found $PYTHON_VERSION"
  exit 1
fi

echo "[DarkTrace X] Using Python $PYTHON_VERSION"

echo "[DarkTrace X] Installing dependencies..."
$PYTHON_BIN -m pip install --upgrade pip setuptools wheel
$PYTHON_BIN -m pip install -r requirements.txt

echo "[DarkTrace X] Installing package..."
$PYTHON_BIN -m pip install .

echo "[DarkTrace X] Initializing configuration and database..."
$PYTHON_BIN -c "from darktracex.config import AppConfig; AppConfig.bootstrap(); print('Configuration initialized.')"

if [ $? -ne 0 ]; then
  echo "ERROR: Installation validation failed."
  exit 1
fi

echo "[DarkTrace X] Installation complete. Run 'darktrace' to launch."