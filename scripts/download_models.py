# Downloads all MinerU models INTO the project folder (./models).
# Run once with internet (setup.bat does this for you).
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
PIPELINE_DIR = MODELS / "pipeline"
VLM_DIR = MODELS / "vlm"

os.environ.setdefault("HF_HOME", str(ROOT / "hf-cache"))
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
# make sure offline switches are off during download
for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
    os.environ.pop(var, None)

from huggingface_hub import snapshot_download  # noqa: E402

PIPELINE_REPO = "opendatalab/PDF-Extract-Kit-1.0"
VLM_REPO = "opendatalab/MinerU2.5-Pro-2605-1.2B"

# The exact sub-models the pipeline backend needs (mirrors
# mineru-models-download / mineru.utils.enum_class.ModelPath)
PIPELINE_PATTERNS = []
for rel in [
    "models/Layout/PP-DocLayoutV2",
    "models/MFR/unimernet_hf_small_2503",
    "models/MFR/pp_formulanet_plus_m",
    "models/OCR/paddleocr_torch",
    "models/TabRec/SlanetPlus/slanet-plus.onnx",
    "models/TabRec/UnetStructure/unet.onnx",
    "models/TabCls/paddle_table_cls/PP-LCNet_x1_0_table_cls.onnx",
]:
    PIPELINE_PATTERNS += [rel, rel + "/*", rel + "/**"]


def fmt_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return f"{total / 1024**3:.2f} GB"


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Downloading pipeline models -> {PIPELINE_DIR}")
    snapshot_download(
        PIPELINE_REPO,
        allow_patterns=PIPELINE_PATTERNS,
        local_dir=str(PIPELINE_DIR),
    )
    print(f"    done ({fmt_size(PIPELINE_DIR)})")

    print(f"\n--- Downloading VLM model (MinerU2.5) -> {VLM_DIR}")
    snapshot_download(
        VLM_REPO,
        local_dir=str(VLM_DIR),
    )
    print(f"    done ({fmt_size(VLM_DIR)})")

    # Pre-fetch the small fasttext language-detection model used by
    # fast-langdetect so it never tries to download at runtime.
    print("\n--- Pre-fetching language-detection model")
    os.environ["FTLANG_CACHE"] = str(MODELS / "fasttext")
    try:
        from fast_langdetect import detect
        detect("hello world")
        print("    done")
    except Exception as e:  # non-fatal
        print(f"    warning: could not pre-fetch langdetect model: {e}")

    # Write the project-local mineru.json (load by explicit path:
    # embedded Python does not put the script dir on sys.path)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_config", ROOT / "scripts" / "make_config.py")
    make_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_config)
    make_config.write_config()

    print("\nAll models downloaded into the project folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
