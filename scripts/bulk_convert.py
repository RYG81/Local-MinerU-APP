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
    ap.add_argument("-m", "--method", default="auto",
                    choices=["auto", "txt", "ocr"],
                    help="auto detects text/scans; use ocr for scanned PDFs")
    ap.add_argument("--lang", default="en",
                    help="OCR language hint for pipeline, e.g. devanagari "
                         "for Hindi (default: en)")
    ap.add_argument("--effort", default="medium",
                    choices=["medium", "high"],
                    help="hybrid effort; medium avoids image/chart narration, "
                         "high enables deeper visual analysis")
    ap.add_argument(
        "--image-analysis",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="analyze images/charts with VLM (default: disabled for clean "
             "text extraction; use --image-analysis for visual documents)",
    )
    ap.add_argument("--formula", action=argparse.BooleanOptionalAction,
                    default=True, help="enable formula recognition")
    ap.add_argument("--table", action=argparse.BooleanOptionalAction,
                    default=True, help="enable table recognition")
    ap.add_argument(
        "--quiz-repair",
        action="store_true",
        help="audit born-digital quiz PDFs and generate validated native-text "
             "quiz artifacts beside MinerU output",
    )
    ap.add_argument(
        "--quiz-options",
        default="auto",
        choices=["auto", "2", "3", "4", "5", "6", "7", "8"],
        help="expected quiz options; auto detects per document/section",
    )
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
    temp_dir = ROOT / "output" / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    log(f"Bulk conversion started  |  log: {LOG_FILE}")
    log(f"  files   : {len(files)}")
    log(f"  backend : {args.backend}")
    log(f"  method  : {args.method}")
    log(f"  language: {args.lang}")
    log(f"  effort  : {args.effort}")
    log(f"  images  : {'analyze' if args.image_analysis else 'extract only'}")
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
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        # speed: bigger inference batches (pipeline backend)
        "MINERU_MIN_BATCH_INFERENCE_SIZE": str(args.batch_size),
        "MINERU_LOG_LEVEL": "INFO",
    })

    # ONE mineru invocation for everything -> models load once
    t0 = time.time()
    cmd = [sys.executable, "-m", "mineru.cli.client",
           "-p", str(src), "-o", str(out_dir),
           "-b", args.backend,
           "-m", args.method,
           "--lang", args.lang,
           "--effort", args.effort,
           "--image-analysis", str(args.image_analysis).lower(),
           "--formula", str(args.formula).lower(),
           "--table", str(args.table).lower()]
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

    quiz_repairs = []
    if args.quiz_repair:
        repair_script = ROOT / "scripts" / "repair_quiz_extraction.py"
        for source_file, stem_dir in results:
            if source_file.suffix.lower() != ".pdf":
                continue
            result_dirs = sorted(
                {path.parent for path in stem_dir.rglob("*_content_list_v2.json")}
            )
            if not result_dirs:
                continue
            result_dir = result_dirs[0]
            content_v2 = next(result_dir.glob("*_content_list_v2.json"))
            prefix = result_dir / f"{source_file.stem}_quiz_repaired"
            repair_cmd = [
                sys.executable, str(repair_script), str(source_file),
                "-o", str(prefix),
                "--expected-options", str(args.quiz_options),
                "--mineru-content-v2", str(content_v2),
            ]
            repair = subprocess.run(
                repair_cmd, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace",
            )
            report_path = prefix.with_name(f"{prefix.name}_report.json")
            if repair.returncode == 0 and report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                quiz_repairs.append({
                    "file": str(source_file),
                    "valid": report.get("valid", False),
                    "report": str(report_path),
                })
                log(
                    f"  quiz OK  : {source_file.name} "
                    f"({report['extracted_questions']} questions)"
                )
            else:
                quiz_repairs.append({
                    "file": str(source_file),
                    "valid": False,
                    "error": repair.stdout[-1000:],
                })
                log(f"  quiz skip: {source_file.name} (validation failed)")

    # summary json
    summary = {
        "started": stamp, "backend": args.backend,
        "method": args.method, "language": args.lang,
        "effort": args.effort, "image_analysis": args.image_analysis,
        "formula": args.formula, "table": args.table,
        "quiz_repairs": quiz_repairs,
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
