# Quick sanity check after setup: GPU visibility + model files present.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ok = True

print("\n--- Python:", sys.version.split()[0])

try:
    import torch
    print("--- PyTorch:", torch.__version__)
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"--- CUDA OK: {name} (sm_{cap[0]}{cap[1]}, {vram:.1f} GB)")
        if cap < (12, 0):
            print("    note: not a Blackwell GPU, but that's fine.")
        # tiny smoke test on GPU
        x = torch.rand(64, 64, device="cuda") @ torch.rand(64, 64, device="cuda")
        torch.cuda.synchronize()
        print("--- GPU matmul smoke test: OK")
    else:
        ok = False
        print("!!! CUDA NOT AVAILABLE - check NVIDIA driver (needs a recent")
        print("    driver supporting CUDA 12.8, e.g. 570+).")
except Exception as e:
    ok = False
    print("!!! PyTorch failed:", e)

try:
    import mineru
    print("--- MinerU:", getattr(mineru, "__version__", "installed"))
except Exception as e:
    ok = False
    print("!!! MinerU import failed:", e)

for sub, probe in [
    ("models/pipeline/models/Layout/PP-DocLayoutV2", None),
    ("models/pipeline/models/OCR/paddleocr_torch", None),
    ("models/vlm", "config.json"),
]:
    p = ROOT / sub
    exists = (p / probe).exists() if probe else (p.exists() and any(p.iterdir()))
    print(("--- found: " if exists else "!!! MISSING: ") + sub)
    ok = ok and exists

print("\nRESULT:", "ALL GOOD - run.bat is ready (offline)." if ok else "PROBLEMS FOUND - fix above before using run.bat.")
sys.exit(0 if ok else 1)
