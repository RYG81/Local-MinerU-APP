#!/bin/bash
# ============================================================
#  MinerU-Local one-time setup for Linux / WSL2 (NVIDIA GPU)
#  Creates a project-local venv + downloads all models into this
#  folder. Needs internet ONCE. Then run_linux.sh is offline.
#
#  Requirements on the machine:
#    - Python 3.10-3.13 (e.g. apt install python3.12 python3.12-venv)
#    - NVIDIA driver R570+ (on WSL2: the *Windows* driver provides
#      CUDA to Linux automatically - do NOT install a driver inside WSL)
#
#  The big Linux win: vLLM acceleration for the VLM/Hybrid backends
#  (Linux-only). This script installs it by default; skip with:
#      ./setup_linux.sh --no-vllm
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

WITH_VLLM=1
[ "$1" = "--no-vllm" ] && WITH_VLLM=0

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
echo " [0/6] Pre-flight checks"
echo "============================================================"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
else
  echo "WARNING: nvidia-smi not found."
  echo "  Native Linux: install the NVIDIA driver (R570+)."
  echo "  WSL2: install/update the driver in WINDOWS, then restart WSL."
fi

echo "============================================================"
echo " [1/6] Finding Python 3.10-3.13"
echo "============================================================"
PY=""
for cand in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    v=$("$cand" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    case "$v" in 3.10|3.11|3.12|3.13) PY="$cand"; break;; esac
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: need Python 3.10-3.13."
  echo "  Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
  exit 1
fi
echo "Using $PY ($($PY --version))"

echo "============================================================"
echo " [2/6] Project-local virtual environment (./venv)"
echo "============================================================"
if [ ! -x "$ROOT/venv/bin/python" ]; then
  "$PY" -m venv "$ROOT/venv" || {
    echo "venv creation failed - on Ubuntu install: sudo apt install ${PY}-venv"
    exit 1
  }
fi
VPY="$ROOT/venv/bin/python"
"$VPY" -m pip install -U pip

echo "============================================================"
echo " [3/6] PyTorch (CUDA 12.8 build: covers RTX 20-50 series)"
echo "============================================================"
"$VPY" -m pip install "torch<3" torchvision --index-url https://download.pytorch.org/whl/cu128

echo "============================================================"
echo " [4/6] MinerU (pinned) + Gradio 5.x"
echo "============================================================"
"$VPY" -m pip install "mineru[core]==3.3.1"
# Gradio 6 has UI bugs with MinerU's app (dead Convert button etc.)
"$VPY" -m pip install "gradio==5.49.1" "gradio-pdf>=0.0.22"

if [ "$WITH_VLLM" = "1" ]; then
  echo "------------------------------------------------------------"
  echo " Installing vLLM acceleration (Linux-only; several GB)."
  echo " This makes the VLM/Hybrid backends MUCH faster."
  echo "------------------------------------------------------------"
  "$VPY" -m pip install "mineru[vllm]==3.3.1" || {
    echo "WARNING: vLLM install failed. The app still works - the VLM"
    echo "backend will use the slower transformers engine instead."
  }
fi

echo "Verifying imports..."
"$VPY" - <<'EOF'
import torch, transformers, gradio, cv2, onnxruntime, mineru
print("imports OK | torch", torch.__version__, "| CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
try:
    import vllm
    print("vLLM:", vllm.__version__, "(fast VLM engine available)")
except ImportError:
    print("vLLM: not installed (VLM backend will use transformers)")
EOF

echo "============================================================"
echo " [5/6] Downloading models into ./models (several GB)"
echo "============================================================"
"$VPY" "$ROOT/scripts/download_models.py"

echo "============================================================"
echo " [6/6] Offline smoke test (parses a real PDF, both backends)"
echo "============================================================"
"$VPY" "$ROOT/scripts/smoke_test.py"

echo
echo "============================================================"
echo " Setup complete and SMOKE-TESTED!"
echo "   Web UI : ./run_linux.sh"
echo "   Bulk   : ./bulk.sh <folder> [backend]"
echo " You may delete pip-cache/ to save disk space."
echo "============================================================"
