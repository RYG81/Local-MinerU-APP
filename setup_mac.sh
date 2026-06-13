#!/bin/bash
# ============================================================
#  MinerU-Local one-time setup for macOS (Apple Silicon & Intel)
#  Creates a project-local venv + downloads all models into
#  this folder. Needs internet ONCE. Then run_mac.sh is offline.
#
#  Requirement: Python 3.10-3.13 installed (e.g. `brew install
#  python@3.12` or from python.org).
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

# Keep all caches inside the project folder
export HF_HOME="$ROOT/hf-cache"
export PIP_CACHE_DIR="$ROOT/pip-cache"
export FTLANG_CACHE="$ROOT/models/fasttext"
export HF_HUB_DISABLE_TELEMETRY=1
export GRADIO_ANALYTICS_ENABLED=False
export DO_NOT_TRACK=1
export MINERU_MODEL_SOURCE=huggingface
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE

echo "============================================================"
echo " [1/5] Finding Python 3.10-3.13"
echo "============================================================"
PY=""
for cand in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    v=$("$cand" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    case "$v" in
      3.10|3.11|3.12|3.13) PY="$cand"; break;;
    esac
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: need Python 3.10-3.13. Install with: brew install python@3.12"
  exit 1
fi
echo "Using $PY ($($PY --version))"

echo "============================================================"
echo " [2/5] Project-local virtual environment (./venv)"
echo "============================================================"
if [ ! -x "$ROOT/venv/bin/python" ]; then
  "$PY" -m venv "$ROOT/venv"
fi
VPY="$ROOT/venv/bin/python"
"$VPY" -m pip install -U pip

echo "============================================================"
echo " [3/5] Installing MinerU (pinned) + Apple Silicon extras"
echo "============================================================"
# Default pip torch on macOS already supports MPS (Apple GPU).
"$VPY" -m pip install "mineru[core]==3.3.1"
if [ "$(uname -m)" = "arm64" ]; then
  echo "Apple Silicon detected -> installing MLX acceleration for the VLM backend"
  "$VPY" -m pip install "mineru[mlx]==3.3.1" || \
    echo "WARNING: mlx extras failed to install; VLM will use transformers+MPS (slower but works)."
fi

echo "Verifying imports..."
"$VPY" -c "import torch, transformers, gradio, cv2, onnxruntime, mineru; print('imports OK; MPS available:', torch.backends.mps.is_available())"

echo "============================================================"
echo " [4/5] Downloading models into ./models (several GB)"
echo "============================================================"
"$VPY" "$ROOT/scripts/download_models.py"

echo "============================================================"
echo " [5/5] Offline smoke test (parses a real PDF, both backends)"
echo "============================================================"
"$VPY" "$ROOT/scripts/smoke_test.py"

echo
echo "============================================================"
echo " Setup complete and smoke-tested!"
echo " Start the app with:  ./run_mac.sh   (fully offline)"
echo " You may delete pip-cache/ to save disk space."
echo "============================================================"
