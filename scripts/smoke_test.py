# End-to-end OFFLINE smoke test, run at the end of setup.
# Creates a tiny PDF, then parses it with BOTH backends via the
# official `mineru` CLI, using the exact same offline environment
# that run.bat uses. If this passes, the app demonstrably works
# offline on this machine's GPU.
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYEXE = sys.executable


def load_neighbor(name):
    """Import a module from this script's folder by explicit path.
    (Embedded Python with a ._pth file does not put the script dir
    on sys.path, so a plain `import` would fail.)"""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# --- the exact offline environment run.bat uses --------------------
env = dict(os.environ)
env.update({
    "MINERU_TOOLS_CONFIG_JSON": str(ROOT / "mineru.json"),
    "MINERU_MODEL_SOURCE": "local",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "MODELSCOPE_OFFLINE": "1",
    "HF_HOME": str(ROOT / "hf-cache"),
    "FTLANG_CACHE": str(ROOT / "models" / "fasttext"),
    "HF_HUB_DISABLE_TELEMETRY": "1",
})

# make sure config exists
make_config = load_neighbor("make_config")
make_config.write_config()

# --- build a small test PDF ----------------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

test_dir = ROOT / "output" / "_smoke_test"
test_dir.mkdir(parents=True, exist_ok=True)
pdf_path = test_dir / "smoke.pdf"
c = canvas.Canvas(str(pdf_path), pagesize=A4)
c.setFont("Helvetica-Bold", 18)
c.drawString(72, 770, "MinerU Offline Smoke Test")
c.setFont("Helvetica", 12)
c.drawString(72, 740, "This paragraph verifies text extraction end to end.")
c.drawString(72, 720, "A tiny table below:")
y = 690
for row in [("Name", "Value"), ("alpha", "1"), ("beta", "2")]:
    c.drawString(72, y, f"{row[0]:<10} {row[1]}")
    y -= 18
c.save()


def find_markdown(out_dir: Path) -> bool:
    return any(out_dir.rglob("*.md"))


failures = []
for label, backend in [("pipeline", "pipeline"), ("vlm", "vlm-engine")]:
    print(f"\n=== Smoke test: {label} backend (offline) ===", flush=True)
    out_dir = test_dir / f"out_{label}"
    cmd = [
        PYEXE, "-m", "mineru.cli.client",
        "-p", str(pdf_path),
        "-o", str(out_dir),
        "-b", backend,
    ]
    try:
        proc = subprocess.run(cmd, env=env, timeout=1800)
        if proc.returncode != 0 or not find_markdown(out_dir):
            failures.append(label)
            print(f"{label} backend FAILED (exit={proc.returncode})")
        else:
            print(f"{label} backend: OK -> markdown produced")
    except Exception as e:
        failures.append(label)
        print(f"{label} backend FAILED: {e}")

print("\n" + "=" * 60)
if failures:
    print("SMOKE TEST FAILED for:", ", ".join(failures))
    print("Fix the errors above before relying on run.bat.")
    sys.exit(1)
print("SMOKE TEST PASSED - both backends parsed a real PDF fully")
print("offline on this machine. run.bat is good to go.")
sys.exit(0)
