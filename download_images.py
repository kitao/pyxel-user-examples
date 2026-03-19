#!/usr/bin/env python3
"""Download images from the original JSON and save as images/{id}.gif."""
import json
import os
import urllib.request

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT_DIR, "images")
JSON_PATH = "/Users/takashi/repos/pyxel/scripts/user-examples.json"


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    with open(JSON_PATH) as f:
        data = json.load(f)

    total = len(data["entries"])
    for i, entry in enumerate(data["entries"], 1):
        eid = entry["id"]
        url = entry["image"]
        dest = os.path.join(IMAGES_DIR, f"{eid}.gif")

        if os.path.exists(dest):
            print(f"  [{i}/{total}] #{eid} already exists, skipping")
            continue

        print(f"  [{i}/{total}] #{eid} downloading...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            size = os.path.getsize(dest)
            print(f"OK ({size // 1024}KB)")
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nDone. Images saved to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
