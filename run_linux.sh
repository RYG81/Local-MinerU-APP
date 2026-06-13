#!/bin/bash
# ============================================================
#  MinerU-Local launcher for Linux / WSL2 / cloud VMs - OFFLINE
#  Web UI:  http://127.0.0.1:7860   (local only, default)
#  Logs :   logs/ui_<timestamp>.log
#
#  Remote/server use (e.g. Google Cloud VM):
#    HOST=0.0.0.0 ./run_linux.sh      # listen on all interfaces
#    PORT=8860   ./run_linux.sh       # custom port
#  SECURITY: prefer keeping the default 127.0.0.1 and reaching it
#  via an SSH tunnel (see README, "Google Cloud deployment").
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
VPY="$ROOT/venv/bin/python"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-7860}"

if [ ! -x "$VPY" ]; then
  echo "venv not found. Run ./setup_linux.sh first."
  exit 1
fi

# ---- Offline + project-local environment ----
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
export NO_PROXY="localhost,127.0.0.1"
# ---- Logging & performance ----
export MINERU_LOG_LEVEL=INFO
export MINERU_MIN_BATCH_INFERENCE_SIZE=384

# Regenerate mineru.json relative to this folder (keeps it portable)
"$VPY" "$ROOT/scripts/make_config.py"

mkdir -p "$ROOT/logs"
LOGFILE="$ROOT/logs/ui_$(date +%Y%m%d_%H%M%S).log"

echo
echo " MinerU local web UI starting (fully offline)..."
echo "   UI  : http://$HOST:$PORT"
if [ "$HOST" = "0.0.0.0" ]; then
  echo "   (listening on ALL interfaces - make sure access is restricted"
  echo "    by firewall rules or use an SSH tunnel instead)"
fi
echo "   Log : $LOGFILE   (follow with: tail -f $LOGFILE)"
echo
echo " First conversion after launch loads models into the GPU"
echo " (pipeline ~30s; vlm: with vLLM installed the engine start"
echo "  takes a couple of minutes once, then requests are fast)."
echo

# open browser if available (ignore failures on headless/WSL/servers)
if [ "$HOST" = "127.0.0.1" ]; then
  ( sleep 8 && (xdg-open "http://127.0.0.1:$PORT" 2>/dev/null || \
    (command -v wslview >/dev/null 2>&1 && wslview "http://127.0.0.1:$PORT")) ) &
fi

exec "$VPY" -u -m mineru.cli.gradio_app \
    --server-name "$HOST" \
    --server-port "$PORT" \
    --enable-example false \
    --enable-api false 2>&1 | tee "$LOGFILE"
