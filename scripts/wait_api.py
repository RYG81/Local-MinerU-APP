# Waits until the local mineru-api /health endpoint responds (or times out).
import sys
import time
import urllib.request

url = sys.argv[1].rstrip("/") + "/health"
deadline = time.time() + float(sys.argv[2] if len(sys.argv) > 2 else 180)
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            if r.status == 200:
                print(f"mineru-api is up: {url}")
                sys.exit(0)
    except Exception:
        pass
    time.sleep(1.5)
print(f"ERROR: mineru-api did not become healthy at {url}")
sys.exit(1)
