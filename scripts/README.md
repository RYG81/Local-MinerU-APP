# MinerU-Local — fully offline, portable MinerU web app

A self-contained, offline version of the Hugging Face Space
[opendatalab/MinerU](https://huggingface.co/spaces/opendatalab/MinerU)
(same Gradio UI, same backends) that lives entirely in this one folder:

```
MinerU-Local\
├── setup.bat            ← run ONCE with internet
├── run.bat              ← run anytime, 100% offline
├── mineru.json          ← auto-generated config (project-local model paths)
├── python\              ← private embedded Python 3.12 + all packages
├── models\
│   ├── pipeline\        ← PDF-Extract-Kit-1.0 (layout/OCR/formula/table)
│   ├── vlm\             ← MinerU2.5-Pro-2605-1.2B (VLM backend)
│   └── fasttext\        ← language-detection model
├── scripts\             ← helper scripts (download/config/check)
├── hf-cache\            ← HF bookkeeping (kept inside folder)
└── output\              ← your conversion results land here
```

No system-wide Python, no conda, nothing written to `%USERPROFILE%`,
no registry changes. Delete the folder = fully uninstalled.

## Requirements (target machine)

**Windows** (primary target):
- Windows 10/11 x64
- NVIDIA GPU — tested target: **RTX 5060 12 GB** (Blackwell, sm_120)
- A recent **NVIDIA driver** (R570 or newer — required for CUDA 12.8).
  This is the *only* thing that must be installed on the machine itself.
- ~25 GB free disk during setup (~15 GB after deleting `pip-cache\`)
- Internet **once**, for `setup.bat` only

**macOS** (Apple Silicon M1/M2/M3/M4 or Intel):
- Python 3.10–3.13 installed (`brew install python@3.12`)
- Use `./setup_mac.sh` once (internet), then `./run_mac.sh` (offline)
- On Apple Silicon the VLM backend uses MPS/MLX instead of CUDA.
  16 GB unified memory recommended for the VLM backend; the Pipeline
  backend is fine on 8 GB.
- Note: the macOS folder is portable across Macs of the same
  architecture (arm64→arm64), but a venv is not movable between
  macOS and Windows — run the matching setup script per OS.

**Linux / WSL2** (NVIDIA GPU — the fastest option):
- Python 3.10–3.13 (`sudo apt install python3.12 python3.12-venv`)
- NVIDIA driver R570+. On **WSL2**: install/update the driver in
  *Windows* only — never install a GPU driver inside WSL; the Windows
  driver exposes CUDA to Linux automatically.
- `./setup_linux.sh` once (internet) → `./run_linux.sh` (offline UI)
  and `./bulk.sh <folder> [backend]` (offline bulk → ZIP)
- **Why Linux is fastest:** it's the only OS where MinerU's **vLLM**
  engine installs (`setup_linux.sh` includes it by default; skip with
  `--no-vllm`). With vLLM, the VLM/Hybrid backends run several times
  faster than the Windows transformers path — sub-second per page on
  a 4070-class GPU instead of seconds.
- WSL2 tip: keep the project folder inside the Linux filesystem
  (e.g. `~/MinerU-Local`), not under `/mnt/c/...` — NTFS passthrough
  slows file I/O dramatically.
- The `models/` folder is byte-identical across OSes: you can copy it
  from a Windows install into a Linux install to skip re-downloading.

## Google Cloud deployment (team server)

Recommended VM: `g2-standard-8` (1× **L4 24 GB**, great
price/performance for this workload) or any N1 + T4 for budget. Use the
**"Deep Learning VM" image (Debian/Ubuntu, CUDA 12.x)** so the NVIDIA
driver is preinstalled; otherwise install driver R570+ yourself first.

```bash
# on the VM
git/scp/rsync the MinerU-Local folder to ~/MinerU-Local
cd ~/MinerU-Local
./setup_linux.sh                 # installs vLLM too (Linux = fast path)
./install_service.sh             # systemd service, survives reboots/SSH
journalctl -u mineru -f          # live logs
```

**Team access — two options:**

1. *(safest, default)* Keep the service on `127.0.0.1`; each team member
   runs an SSH tunnel:
   ```bash
   gcloud compute ssh <vm-name> -- -L 7860:localhost:7860
   # then open http://localhost:7860
   ```
   Nothing is exposed to the internet; access = whoever has IAM/SSH
   access to the VM. No firewall changes needed.

2. *(convenient, riskier)* `HOST=0.0.0.0 ./install_service.sh`, then add
   a GCP firewall rule for port 7860 **restricted to your office IPs**.
   The Gradio UI has **no authentication** — never expose it to
   0.0.0.0/0. For anything broader, put it behind GCP Identity-Aware
   Proxy or an nginx reverse proxy with basic auth.

**Bulk on the VM:** `./bulk.sh ~/papers pipeline` — output ZIP lands in
`output/bulk/<timestamp>/`; copy back with
`gcloud compute scp --recurse <vm>:~/MinerU-Local/output/bulk/... .`

**Cost note:** GPU VMs bill while running. For batch-style usage, stop
the VM when idle (`gcloud compute instances stop <vm>`) — the folder,
models and service all persist on the boot disk and resume on start.

## Install (once, with internet)

1. Copy this folder anywhere, e.g. `D:\MinerU-Local`
2. Double-click **`setup.bat`** and wait (downloads ≈ 8–10 GB:
   embedded Python, PyTorch cu128, MinerU, and all models).
3. When it prints `ALL GOOD`, you're done. Optionally delete
   `pip-cache\` to reclaim disk space.

## Use (offline forever after)

Double-click **`run.bat`** → browser opens at
`http://127.0.0.1:7860`.

- Upload a PDF / image / DOCX / PPTX / XLSX
- Pick a **Backend**:
  - **Pipeline** — classic multi-model chain, lowest VRAM, best for
    multilingual OCR (choose OCR language in Advanced options)
  - **VLM** — MinerU2.5 1.2B vision-language model, highest accuracy
    for Chinese/English; comfortable on 12 GB VRAM
  - **Hybrid** — combines both, highest quality (a bit slower)
- Click **Convert** → get rendered Markdown, raw Markdown, content-list
  JSON, and a ZIP with everything (incl. extracted images).

For exam/quiz PDFs, open **Advanced options** and enable **Repair quiz
extraction**. Keep **Options per question** set to **Auto** for normal
and bulk use; it infers four-, five-, or mixed-option sections from
nearby questions. Manual 2-8 overrides are available when the source has
unusual formatting. When validation succeeds, the Markdown and JSON
tabs show the repaired result. The downloaded ZIP contains both MinerU's
original files and the `*_quiz_repaired*` files for comparison.

`run.bat` sets `MINERU_MODEL_SOURCE=local`, `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1` etc., so nothing ever phones home or tries to
download — if a model file were missing it fails loudly instead of
silently fetching it.

## Bulk conversion (folder → one ZIP)

```bat
bulk.bat C:\path\to\folder            # pipeline backend (fastest)
bulk.bat C:\path\to\folder vlm-engine # higher quality, slower
bulk.bat C:\path\to\hindi pipeline devanagari
```
or just **drag & drop a folder onto `bulk.bat`**.

- One `mineru` invocation for the whole folder → **models load once**,
  not per file (the single biggest speed win for batches)
- Output per document: markdown, content-list JSON, middle JSON, images
- Everything packaged into **one ZIP** (`bulk_result_<timestamp>.zip`)
  organized as `<docname>/...`
- `_summary.json` + per-run log file in `logs\`
- Failed files are listed explicitly at the end

### Improving extraction quality

- **Scanned Hindi/Devanagari documents:** use Pipeline with the
  `devanagari` OCR language. In the UI choose **Pipeline**, set OCR
  Language to Devanagari, and enable **Force OCR** only when auto mode
  produces poor text.
- **Clean text extraction:** keep Hybrid effort at **Medium** or disable
  **Image analysis**. High/image analysis can add prose describing QR
  codes, logos, and decorative graphics to the Markdown.
- **Charts and meaningful figures:** use Hybrid **High** with Image
  analysis enabled. This is useful for visual documents, but less clean
  for exam papers and forms.
- **Born-digital PDFs:** leave Force OCR off. Native PDF text is usually
  more accurate than OCR.

The direct bulk command exposes all quality controls:

```bat
python\python.exe scripts\bulk_convert.py C:\docs -b pipeline --lang devanagari --method ocr
python\python.exe scripts\bulk_convert.py C:\docs -b hybrid-engine --effort high --image-analysis
python\python.exe scripts\bulk_convert.py C:\quizzes -b hybrid-engine --quiz-repair
```

For born-digital quiz PDFs, `--quiz-repair` audits MinerU's question
sequence and option completeness. It compares normal PDF text order with
coordinate-based 1-4 column reconstruction, selects the better-scoring
result, and writes validated Markdown, structured quiz JSON, and repaired
content-list files beside the regular MinerU output. Scanned PDFs still
need OCR because they do not contain a native text layer.

## Logging

Both the UI (`run.bat`) and bulk runs write timestamped logs to `logs\`.
Follow a live log from another window with:
```powershell
powershell Get-Content -Wait logs\ui_<timestamp>.log
```
`run.bat` also disables console QuickEdit mode — previously, clicking
inside the console window silently PAUSED the whole server (the
"nothing happens until I press a key" trap).

## Performance tuning

| Lever | Where | Effect |
|---|---|---|
| `MINERU_MIN_BATCH_INFERENCE_SIZE=384` | set in `run.bat`/`bulk.bat` | bigger GPU batches; raise to 512 on 12 GB cards if no OOM, lower to 128 if OOM |
| Backend choice | UI dropdown / `bulk.bat` arg | pipeline ≫ faster than vlm/hybrid; use vlm only where quality demands |
| Keep server running | — | model load is the slow part; the 2nd+ conversions are much faster |
| `--max-convert-pages` | UI slider | cap pages for quick previews |

## Portability

The whole folder is relocatable:

- Move/rename it on the same machine → just works (`run.bat` rewrites
  `mineru.json` with the new absolute paths on every launch).
- Copy to another Windows x64 machine with an NVIDIA GPU + R570+ driver
  → just works, no internet needed. (The cu128 PyTorch build also runs
  on older RTX 20/30/40 cards, not only the 5060.)

## CLI usage (optional, also offline)

```bat
cd /d <this folder>
set MINERU_TOOLS_CONFIG_JSON=%CD%\mineru.json
set MINERU_MODEL_SOURCE=local
python\python.exe -m mineru.cli.client -p input.pdf -o output -b pipeline
python\python.exe -m mineru.cli.client -p input.pdf -o output -b vlm-engine
```

## What's identical to the HF Space, and what's not

Identical — it is literally the same `mineru-gradio` app the Space runs:
- Backend selector (Hybrid / Pipeline / VLM), hybrid effort level
- Max pages slider, force-OCR, OCR language list (90+ languages)
- Formula / table / image-analysis toggles
- PDF & image preview, Markdown rendering / raw text / JSON tabs
- ZIP download with markdown + images + content-list JSON

Differences when fully offline:
- **Speed**: the Space uses a datacenter GPU with vLLM (Linux-only).
  On Windows the VLM backend runs via transformers — same output
  quality, slower (seconds per page on an RTX 5060 instead of
  sub-second). Pipeline backend speed is comparable.
- **Office preview pane**: DOCX/PPTX/XLSX preview uses Microsoft's
  online viewer and won't render offline. *Conversion of these files
  still works fully offline* — only the preview panel is blank.
- Header fonts/star badge don't load offline (cosmetic).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `CUDA NOT AVAILABLE` in check | Update NVIDIA driver to R570+ (CUDA 12.8). |
| `no kernel image ... sm_120` | PyTorch wasn't installed from the cu128 index — rerun step 3 of `setup.bat`. |
| VLM backend slow / OOM | 12 GB is plenty for the 1.2B model; close other GPU apps, or use Pipeline backend. |
| Port 7860 busy | Edit `run.bat`, change `--server-port`. |
| Convert button does nothing / Advanced options hidden | Gradio 6.x UI bugs with MinerU's app. Run `fix_ui.bat` once (pins Gradio 5.49.1), then `run.bat`. |
| Convert seems stuck on first use | First conversion loads models into VRAM (pipeline ~30s, VLM a few minutes). Watch the console window for progress. |
| Want to update models later | Re-run `setup.bat` (needs internet); offline use is untouched otherwise. |
