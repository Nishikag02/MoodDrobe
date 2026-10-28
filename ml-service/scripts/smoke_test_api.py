"""Check the running API end to end with real catalogue photos.

Start the API first (uvicorn recommend_server:app --port 8000), then in a
second window, from ml-service/:
    python -m scripts.smoke_test_api
    python -m scripts.smoke_test_api --image C:\\Users\\you\\Pictures\\outfit.jpg
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
import uuid
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config  # noqa: E402


def post_files(url: str, paths: list[Path], fields: dict) -> dict:
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for p in paths:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{p.name}"\r\n'
                 f"Content-Type: image/jpeg\r\n\r\n").encode() + p.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def show(title: str, res: dict) -> None:
    print(f"\n--- {title} ---")
    for key in ("inputs", "detected", "vibes", "attributes"):
        if res.get(key):
            print(f"{key}: {res[key]}")
    for section in ("your_style", "complete_the_look", "closest_matches"):
        items = res.get(section) or []
        if items:
            print(f"{section}: " + ", ".join(f"{i.get('category_name') or i.get('category')} ({i['score']:.2f})"
                                             for i in items[:8]))
    if res.get("timings_ms"):
        print(f"timings_ms: {res['timings_ms']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--image", type=Path, action="append", help="your own photo (repeat for a moodboard)")
    args = ap.parse_args()

    images = args.image
    if not images:
        products = catalogue.load_products()
        test = [p for p in products.values() if p.get("dataset_split") == "test"]
        random.Random(7).shuffle(test)
        images = []
        for p in test:
            path = catalogue.resolve_image_path(p["image_path"])
            if path:
                images.append(path)
                print(f"Using test image {p['product_id']} ({p.get('category')}): {path}")
                break
        if not images:
            raise SystemExit("No test images found on disk; pass --image <path>.")

    show("photo -> recommendations", post_files(f"{args.api}/recommend", images, {"k": 8}))
    show("vibe 'old money'", post_json(f"{args.api}/recommend/vibe", {"vibe": "old money", "k": 8}))
    show("vibe '90s grunge'", post_json(f"{args.api}/recommend/vibe", {"vibe": "90s grunge", "k": 8}))
    print("\nAll requests succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
