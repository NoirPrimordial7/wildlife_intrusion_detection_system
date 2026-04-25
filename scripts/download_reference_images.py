from __future__ import annotations

from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "assets" / "reference_images"

# Add approved public image URLs here if reference samples are needed.
REFERENCE_URLS: dict[str, str] = {}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not REFERENCE_URLS:
        print("No reference image URLs configured.")
        print(f"Reference folder ready: {OUTPUT_DIR}")
        return 0

    for name, url in REFERENCE_URLS.items():
        target = OUTPUT_DIR / name
        print(f"Downloading {url} -> {target}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        target.write_bytes(response.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

