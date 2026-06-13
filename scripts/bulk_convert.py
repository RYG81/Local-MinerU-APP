#!/usr/bin/env python3
"""
Bulk converter for MinerU-Local. Converts a whole folder of documents
(PDF/images/DOCX/PPTX/XLSX) and packages everything into one ZIP:
markdown + content-list JSON + middle JSON + all extracted images.

Speed levers used:
  - single mineru invocation for the entire folder -> models load ONCE
  - pipeline backend batches pages across files on the GPU
  - tunable MINERU_MIN_BATCH_INFERENCE_SIZE

Usage (via bulk.bat, or directly):
  python scripts/bulk_convert.py <input_folder> [-o out] [-b pipeline|vlm-engine|hybrid-engine]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
             ".tiff", ".jp2", ".docx", ".pptx", ".xlsx"}

# ---------- logging ----------
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
LOG_FILE = LOGS / f"bulk_{datetime.now():%Y%m%d_%H%M%S}.log"


def log(msg, end="\n"):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, end=end, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + end)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="folder with documents (or a single file)")
    ap.add_argument("-o", "--out", default=str(ROOT / "output" / "bulk"))
    ap.add_argument("-b", "--backend", default="pipeline",
                    choices=["pipeline", "vlm-engine", "hybrid-engine"],
                    help="pipeline = fastest & lowest VRAM (default); "
                         "vlm-engine / hybrid-engine = higher quality, slower")
    ap.add_argument("--lang", default="en", help="OCR language hint (pipeline)")
    ap.add_argument("--no-zip", action="store_true", help="skip ZIP packaging")
    ap.add_argument("--batch-size", type=int, default=384,
                    help="MINERU_MIN_BATCH_INFERENCE_SIZE (higher = faster on "
                         "big GPUs; lower if you hit CUDA OOM)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"Input not found: {src}")

    files = ([src] if src.is_file()
             else sorted(p for p in src.rglob("*")
                         if p.suffix.lower() in SUPPORTED and p.is_file()))
    if not files:
        sys.exit(f"No supported documents under {src}")

    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    out_dir = Path(args.out) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"Bulk conversion started  |  log: {LOG_FILE}")
    log(f"  files   : {len(files)}")
    log(f"  backend : {args.backend}")
    log(f"  output  : {out_dir}")

    # offline + project-local env (same as run.bat)
    env = dict(os.environ)
    env.update({
        "MINERU_TOOLS_CONFIG_JSON": str(ROOT / "mineru.json"),
        "MINERU_MODEL_SOURCE": "local",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "MODELSCOPE_OFFLINE": "1",
        "HF_HOME": str(ROOT / "hf-cache"),
        "FTLANG_CACHE": str(ROOT / "models" / "fasttext"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        # speed: bigger inference batches (pipeline backend)
        "MINERU_MIN_BATCH_INFERENCE_SIZE": str(args.batch_size),
        "MINERU_LOG_LEVEL": "INFO",
    })

    # ONE mineru invocation for everything -> models load once
    t0 = time.time()
    cmd = [sys.executable, "-m", "mineru.cli.client",
           "-p", str(src), "-o", str(out_dir),
           "-b", args.backend, "--lang", args.lang]
    log(f"  running : {' '.join(cmd)}")
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
    took = time.time() - t0

    # collect results
    results, missing = [], []
    for f in files:
        stem_dir = out_dir / f.stem
        mds = list(stem_dir.rglob("*.md")) if stem_dir.exists() else []
        if mds:
            results.append((f, stem_dir))
        else:
            missing.append(f)

    log(f"Conversion finished in {took/60:.1f} min "
        f"({took/max(1,len(files)):.1f} s/file avg)")
    log(f"  succeeded: {len(results)}/{len(files)}")
    for f in missing:
        log(f"  FAILED   : {f.name}  (see log for the mineru error)")

    # summary json
    summary = {
        "started": stamp, "backend": args.backend,
        "files_total": len(files), "files_ok": len(results),
        "files_failed": [str(f) for f in missing],
        "seconds": round(took, 1), "output_dir": str(out_dir),
    }
    (out_dir / "_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    # ---- package one ZIP: md + json + images per document ----
    if not args.no_zip and results:
        zip_path = out_dir / f"bulk_result_{stamp}.zip"
        log(f"Packaging ZIP: {zip_path.name}")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f, stem_dir in results:
                for p in stem_dir.rglob("*"):
                    if p.is_file() and p.suffix.lower() in (
                            ".md", ".json", ".png", ".jpg", ".jpeg"):
                        zf.write(p, f"{f.stem}/{p.relative_to(stem_dir)}")
            zf.write(out_dir / "_summary.json", "_summary.json")
        log(f"ZIP ready: {zip_path}  ({zip_path.stat().st_size/1e6:.1f} MB)")

    log("Done.")
    if proc.returncode != 0:
        log(f"NOTE: mineru exited with code {proc.returncode}; check the log.")
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
