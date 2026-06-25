#!/usr/bin/env python3
"""
image_generate.py — substrate image-generation bridge.

For agents whose main model cannot generate images. Calls OpenAI's image API
(gpt-image-2 by default; override via CAPABILITY_BRIDGE_IMAGE_MODEL). Saves
the generated image to the requested path and prints the path on stdout.

Env: OPENAI_API_KEY (required)
     CAPABILITY_BRIDGE_IMAGE_MODEL  (default: gpt-image-2)
     OPENAI_IMAGE_BASE_URL          (default: https://api.openai.com/v1/images/generations)

Usage:
  image_generate.py <output_path> "<prompt>" [--size 1024x1024] [--quality high]

Exits 0 on success (prints path), non-zero on failure (error to stderr).
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
import urllib.request
from urllib.error import HTTPError

SIZES = {"1024x1024", "1024x1536", "1536x1024", "1:1", "2:3", "3:2", "3:4", "4:3", "9:16"}


def parse_args(argv: list[str]) -> tuple[str, str, str, str]:
    if len(argv) < 3:
        print("usage: image_generate.py <output_path> \"<prompt>\" [--size S] [--quality Q]",
              file=sys.stderr)
        sys.exit(2)
    out_path = argv[1]
    prompt = argv[2]
    size = "1024x1024"
    quality = "high"
    i = 3
    while i < len(argv):
        if argv[i] == "--size" and i + 1 < len(argv):
            size = argv[i + 1]; i += 2
        elif argv[i] == "--quality" and i + 1 < len(argv):
            quality = argv[i + 1]; i += 2
        else:
            i += 1
    return out_path, prompt, size, quality


def main() -> int:
    out_path, prompt, size, quality = parse_args(sys.argv)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("[image-bridge] OPENAI_API_KEY not set — cannot generate images", file=sys.stderr)
        return 1

    model = os.environ.get("CAPABILITY_BRIDGE_IMAGE_MODEL", "gpt-image-2")
    base = os.environ.get("OPENAI_IMAGE_BASE_URL", "https://api.openai.com/v1/images/generations")

    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
        # gpt-image-2 returns b64_json; dall-e-3 uses "url". Request b64 so we
        # can write directly to disk without a second fetch.
        "response_format": "b64_json",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    req = urllib.request.Request(base, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
    except HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        print(f"[image-bridge] HTTP {e.code}: {err[:500]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[image-bridge] request failed: {e}", file=sys.stderr)
        return 1

    # Response shape varies by model — handle b64_json and url.
    data_list = out.get("data") or []
    if not data_list:
        print(f"[image-bridge] empty response: {json.dumps(out)[:400]}", file=sys.stderr)
        return 1
    item = data_list[0]

    if item.get("b64_json"):
        img_bytes = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        import urllib.request as ur
        with ur.urlopen(item["url"], timeout=120) as r2:
            img_bytes = r2.read()
    else:
        print(f"[image-bridge] no image in response: {json.dumps(item)[:400]}", file=sys.stderr)
        return 1

    out_p = pathlib.Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_bytes(img_bytes)
    print(str(out_p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
