#!/bin/bash
# ============================================================
#  Install MinerU-Local as a systemd service (Linux servers).
#  The UI then survives SSH disconnects and starts on boot.
#
#    ./install_service.sh            # service on 127.0.0.1:7860
#    HOST=0.0.0.0 ./install_service.sh
#
#  Manage afterwards:
#    sudo systemctl status mineru
#    sudo systemctl restart mineru
#    journalctl -u mineru -f          # live logs
#    sudo systemctl disable --now mineru   # uninstall
# ============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-7860}"
USER_NAME="$(whoami)"

if [ ! -x "$ROOT/venv/bin/python" ]; then
  echo "venv not found. Run ./setup_linux.sh first."
  exit 1
fi

UNIT=/etc/systemd/system/mineru.service
echo "Writing $UNIT (sudo needed)..."
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=MinerU-Local document parsing web UI (offline)
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
Environment=MINERU_TOOLS_CONFIG_JSON=$ROOT/mineru.json
Environment=MINERU_MODEL_SOURCE=local
Environment=HF_HUB_OFFLINE=1
Environment=TRANSFORMERS_OFFLINE=1
Environment=MODELSCOPE_OFFLINE=1
Environment=HF_HOME=$ROOT/hf-cache
Environment=FTLANG_CACHE=$ROOT/models/fasttext
Environment=HF_HUB_DISABLE_TELEMETRY=1
Environment=GRADIO_ANALYTICS_ENABLED=False
Environment=DO_NOT_TRACK=1
Environment=MINERU_LOG_LEVEL=INFO
Environment=MINERU_MIN_BATCH_INFERENCE_SIZE=384
ExecStartPre=$ROOT/venv/bin/python $ROOT/scripts/make_config.py
ExecStart=$ROOT/venv/bin/python -u -m mineru.cli.gradio_app --server-name $HOST --server-port $PORT --enable-example false --enable-api false
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mineru
echo
echo "Service installed and started."
echo "  Status : sudo systemctl status mineru"
echo "  Logs   : journalctl -u mineru -f"
echo "  UI     : http://$HOST:$PORT"
if [ "$HOST" = "127.0.0.1" ]; then
  echo
  echo "Reach it from your laptop via SSH tunnel:"
  echo "  gcloud compute ssh <vm-name> -- -L 7860:localhost:$PORT"
  echo "  then open http://localhost:7860 locally."
fi
