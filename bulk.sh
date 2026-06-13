#!/bin/bash
# ============================================================
#  MinerU-Local BULK conversion (Linux/WSL2/macOS) - offline
#  Usage:  ./bulk.sh /path/to/folder [pipeline|vlm-engine|hybrid-engine]
#  Output: output/bulk/<timestamp>/ + one ZIP with md/json/images
#  Log:    logs/bulk_<timestamp>.log
# ============================================================
set -e
cd "$(dirname "$0")"
VPY="$(pwd)/venv/bin/python"

if [ ! -x "$VPY" ]; then
  echo "venv not found. Run ./setup_linux.sh (or setup_mac.sh) first."
  exit 1
fi
if [ -z "$1" ]; then
  echo "Usage: ./bulk.sh <folder-or-file> [backend]"
  echo "  backend: pipeline (default, fastest) | vlm-engine | hybrid-engine"
  exit 1
fi

BACKEND="${2:-pipeline}"
exec "$VPY" "$(pwd)/scripts/bulk_convert.py" "$1" -b "$BACKEND"
