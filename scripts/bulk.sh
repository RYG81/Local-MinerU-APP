#!/bin/bash
# ============================================================
#  MinerU-Local BULK conversion (Linux/WSL2/macOS) - offline
#  Usage:  ./bulk.sh /path/to/folder [backend] [ocr-language]
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
  echo "Usage: ./bulk.sh <folder-or-file> [backend] [ocr-language]"
  echo "  backend: pipeline (default, fastest) | vlm-engine | hybrid-engine"
  echo "  OCR language: en (default) | devanagari for Hindi | ..."
  exit 1
fi

BACKEND="${2:-pipeline}"
LANGUAGE="${3:-en}"
exec "$VPY" "$(pwd)/scripts/bulk_convert.py" "$1" -b "$BACKEND" --lang "$LANGUAGE"
