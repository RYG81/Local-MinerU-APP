#!/bin/bash
# ============================================================
#  MinerU-Local launcher for macOS - 100% OFFLINE
#  Web UI at http://127.0.0.1:7860
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
VPY="$ROOT/venv/bin/python"

if [ ! -x "$VPY" ]; then
  echo "venv not found. Run ./setup_mac.sh first."
  exit 1
fi

# Pin MinerU to this folder & block all network access attempts
export MINERU_TOOLS_CONFIG_JSON="$ROOT/mineru.json"
export MINERU_MODEL_SOURCE=local
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export MODELSCOPE_OFFLINE=1
export HF_HOME="$ROOT/hf-cache"
export FTLANG_CACHE="$ROOT/models/fasttext"
export HF_HUB_DISABLE_TELEMETRY=1
export GRADIO_ANALYTICS_ENABLED=False
export DO_NOT_TRACK=1
# On Apple Silicon, let MPS fall back to CPU for any unsupported op
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Regenerate config with paths relative to wherever this folder is now
"$VPY" "$ROOT/scripts/make_config.py"

echo
echo " MinerU local web UI starting..."
echo " Open http://127.0.0.1:7860 (opens automatically in a moment)."
echo " Press Ctrl+C to stop."
echo
( sleep 8 && open "http://127.0.0.1:7860" ) &

exec "$VPY" -m mineru.cli.gradio_app \
    --server-name 127.0.0.1 \
    --server-port 7860 \
    --enable-example false \
    --enable-api false
