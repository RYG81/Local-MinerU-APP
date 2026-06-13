# (Re)writes the project-local mineru.json so all model paths point
# inside THIS folder. Run automatically by run.bat on every launch,
# which is what makes the folder fully portable (copy/move anywhere).
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "mineru.json"


def write_config() -> None:
    config = {
        "bucket_info": {},
        "latex-delimiter-config": {
            "display": {"left": "$$", "right": "$$"},
            "inline": {"left": "$", "right": "$"},
        },
        "llm-aided-config": {
            "title_aided": {
                "api_key": "",
                "base_url": "",
                "model": "",
                "enable_thinking": False,
                "enable": False,
            }
        },
        "models-dir": {
            "pipeline": str(ROOT / "models" / "pipeline"),
            "vlm": str(ROOT / "models" / "vlm"),
        },
        "config_version": "1.3.1",
    }
    CONFIG.write_text(
        json.dumps(config, indent=4, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {CONFIG}")


if __name__ == "__main__":
    write_config()
