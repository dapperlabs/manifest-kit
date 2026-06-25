#!/usr/bin/env python3
"""
vision_bridge_hook.py — PostToolUse hook on Read.

When a text-only model reads an image, Claude Code returns a tool result like:
  "[image omitted: model does not support vision]"

This hook detects that marker, extracts the image path from the tool input,
calls vision_describe.py to get a real description from a vision-capable model,
and injects it back into the agent's context via systemMessage. The agent never
sees a dead end — it gets the image's content automatically.

Input (stdin, PostToolUse): JSON with tool_name, tool_input (path), tool_response.
Output (stdout): JSON with systemMessage carrying the description, continue=true.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

# The exact marker Claude Code emits when a model can't process an image.
# Match generously — the wording may vary ("model does not support vision",
# "vision returned no usable text", etc.) but the "[image ...]" prefix is stable.
OMISSION_RE = re.compile(
    r"\[image[^\]]*(?:omitted|unreadable|not supported|cannot|no usable)[^\]]*\]",
    re.IGNORECASE,
)

# Image extensions we'll bridge. Conservative — only true raster image types.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _find_image_path(tool_input: dict) -> str | None:
    """Extract an image filesystem path from the Read tool input."""
    path = tool_input.get("path") or tool_input.get("file_path")
    if not path:
        return None
    # Internal URIs (local://, artifact://) resolve to FS paths; only bridge
    # real image files on disk.
    if "://" in path:
        return None
    ext = pathlib.Path(path).suffix.lower()
    if ext not in IMAGE_EXTS:
        return None
    if not pathlib.Path(path).is_file():
        return None
    return path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Malformed input is not our problem — let the tool result pass through.
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name != "Read":
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    tool_response = payload.get("tool_response", "")

    # tool_response may be a dict (structured) or a string. Normalize to text.
    if isinstance(tool_response, dict):
        response_text = json.dumps(tool_response)
    else:
        response_text = str(tool_response or "")

    if not OMISSION_RE.search(response_text):
        return 0  # Not a vision-omission case — nothing to bridge.

    image_path = _find_image_path(tool_input)
    if not image_path:
        return 0  # No bridgable image path — let the agent handle it.

    bridge = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "vision_describe.py"
    try:
        result = subprocess.run(
            [sys.executable, str(bridge), image_path],
            capture_output=True, text=True, timeout=120,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        _emit("Vision bridge timed out describing the image. Treat the image as unavailable.")
        return 0
    except Exception as e:
        _emit(f"Vision bridge failed to start: {e}")
        return 0

    description = result.stdout.strip()
    if not description or result.returncode != 0:
        err = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown"
        _emit(f"Vision bridge could not describe the image ({err}). Treat the image as unavailable.")
        return 0

    # Inject the description back into the agent's context as a system message.
    # The agent now "sees" the image via this bridge — no dead end.
    _emit(
        "VISION BRIDGE — your main model cannot see images, so a vision-capable "
        "model described the image for you. Treat this as the image's content:\n\n"
        f"Image: {image_path}\n\n{description}\n\n"
        "You now have the image's content. Proceed as if you could see it — "
        "do not tell the user you cannot see images."
    )
    return 0


def _emit(system_message: str) -> None:
    """Emit the standard hook output JSON with a systemMessage for the agent."""
    out = {
        "continue": True,
        "suppressOutput": False,
        "systemMessage": system_message,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    sys.exit(main())
