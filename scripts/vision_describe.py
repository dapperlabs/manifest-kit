#!/usr/bin/env python3
"""
vision_describe.py — substrate vision bridge.

Given an image path (and optional prompt), call a vision-capable model to
describe/transcribe it. Used by the capability-bridge PostToolUse hook when a
text-only model returned "[image omitted: model does not support vision]".

Fallback chain (first key that's set + model that returns wins):
  1. Gemini      — gemini-2.0-flash / gemini-1.5-flash / gemini-1.5-pro
  2. OpenAI      — gpt-4o / gpt-4o-mini / gpt-4-vision-preview
  3. Anthropic   — claude-sonnet-4-5 / claude-3-5-sonnet / claude-3-opus

Env vars read: GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY

Output: the description text on stdout. Errors to stderr, exit non-zero only
on total failure (all providers exhausted). The hook decides what to inject.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
import urllib.request
from urllib.error import HTTPError, URLError

DEFAULT_PROMPT = (
    "You are a vision bridge for an AI coding agent whose main model cannot see "
    "images. Describe this image with total precision so the agent can act on it. "
    "Cover: (1) every text string verbatim, (2) layout and visual structure, "
    "(3) colors, shapes, positions, (4) icons and imagery, (5) the overall purpose "
    "and state the image conveys. Be exhaustive and literal — this is the agent's "
    "only source of truth for the image. Do not hedge; if something is unreadable, "
    "say '[unreadable]' for that element only."
)


def _b64(path: str) -> tuple[str, str]:
    raw = pathlib.Path(path).read_bytes()
    ext = pathlib.Path(path).suffix.lower().lstrip(".")
    mime = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
    }.get(ext, "image/png")
    return base64.b64encode(raw).decode(), mime


def _post(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def gemini(b64: str, mime: str, prompt: str) -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": mime, "data": b64}},
        ]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }
    for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            out = _post(url, body, {"Content-Type": "application/json"})
            return out["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[vision-bridge] gemini {model} failed: {e}", file=sys.stderr)
    return None


def openai_vision(b64: str, mime: str, prompt: str) -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    data_uri = f"data:{mime};base64,{b64}"
    for model in ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview"]:
        body = {
            "model": model, "max_tokens": 2000, "temperature": 0.2,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]}],
        }
        try:
            out = _post(url := "https://api.openai.com/v1/chat/completions", body,
                        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            return out["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[vision-bridge] openai {model} failed: {e}", file=sys.stderr)
    return None


def anthropic_vision(b64: str, mime: str, prompt: str) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    for model in ["claude-sonnet-4-5-20250929", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]:
        body = {
            "model": model, "max_tokens": 2048,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        }
        try:
            out = _post("https://api.anthropic.com/v1/messages", body, {
                "Content-Type": "application/json", "x-api-key": key,
                "anthropic-version": "2023-06-01",
            })
            return "".join(b.get("text", "") for b in out["content"])
        except Exception as e:
            print(f"[vision-bridge] anthropic {model} failed: {e}", file=sys.stderr)
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: vision_describe.py <image_path> [prompt]", file=sys.stderr)
        return 2
    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROMPT

    if not pathlib.Path(image_path).is_file():
        print(f"[vision-bridge] image not found: {image_path}", file=sys.stderr)
        return 2

    b64, mime = _b64(image_path)

    for provider in (gemini, openai_vision, anthropic_vision):
        result = provider(b64, mime, prompt)
        if result:
            print(result)
            return 0

    print("[vision-bridge] all providers exhausted or no API keys set", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
