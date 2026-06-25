# ManifestIt

A grab bag of substrate ergonomic fixes for [Claude Code](https://docs.claude.com/en/docs/claude-code). Small fixes that the agent substrate should just handle — so no session dead-ends on a missing capability or ships a bare file path.

> **manifest** · *noun*: a shipping manifest of fixes.
> **manifest it** · *verb*: make a capability appear that the model lacks.

Four things, bundled because they're all "the substrate should just handle this":

1. **Vision bridge** — a `PostToolUse` hook on `Read` that auto-describes images a text-only model can't see. When Claude Code returns `[image omitted: model does not support vision]`, the bridge calls a vision-capable model (Gemini → gpt-4o → Claude Opus fallback chain) and injects the description back into context. No agent opt-in. No more "I can't see images" dead-ends.
2. **Image-gen bridge** — a script that routes image generation to OpenAI `gpt-image-2` for text-only models that need to produce artwork. Env-overridable model.
3. **ForceLink** — a `Stop` hook (from [roham/forcelink](https://github.com/roham/forcelink)) that blocks any turn from ending if the final message contains a bare file path in prose. Forces clickable `file://` / GitHub blob URLs instead. Structural, not advisory — CLAUDE.md rules get ignored, the gate doesn't negotiate.
4. **Distilled operating ethos** — a sanitized, portable a16z/Garry Tan hybrid `CLAUDE.md` in `skills/manifest-it/references/ethos.md`. Principles, not essays.

## Install

### As a Claude Code plugin (recommended)

Copy this repo into your plugins directory and enable it. Hooks load at session start.

```bash
git clone https://github.com/roham/manifest-it.git ~/.claude/plugins/manifest-it
```

Then add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/plugins/manifest-it/hooks/vision_bridge_hook.py", "timeout": 130 }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "bash ~/.claude/plugins/manifest-it/hooks/forcelink.sh", "timeout": 15 }
        ]
      }
    ]
  }
}
```

Restart Claude Code. Done.

### Hooks only (no plugin system)

If you just want ForceLink or the vision bridge without the plugin wrapper, copy the individual scripts:

```bash
# ForceLink
curl -o ~/.claude/hooks/forcelink.sh https://raw.githubusercontent.com/roham/manifest-it/main/hooks/forcelink.sh
chmod +x ~/.claude/hooks/forcelink.sh

# Vision bridge
curl -o ~/.claude/hooks/vision_bridge_hook.py https://raw.githubusercontent.com/roham/manifest-it/main/hooks/vision_bridge_hook.py
curl -o ~/.claude/scripts/vision_describe.py https://raw.githubusercontent.com/roham/manifest-it/main/scripts/vision_describe.py
```

## Requirements

- **python3** (pre-installed on macOS, most Linux distros)
- **jq** (optional — ForceLink falls back gracefully if not installed)
- For the vision bridge: at least one of `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- For the image-gen bridge: `OPENAI_API_KEY`

## Configuration

| Env var | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | Vision bridge provider 1 | — |
| `OPENAI_API_KEY` | Vision bridge provider 2 / image-gen | — |
| `ANTHROPIC_API_KEY` | Vision bridge provider 3 | — |
| `CAPABILITY_BRIDGE_IMAGE_MODEL` | Image-gen model | `gpt-image-2` |
| `SKIP_URL_GATE` | `1` to bypass ForceLink | — |

## How it works

### Vision bridge

`PostToolUse` on `Read` → detects the omission marker on image files → calls `vision_describe.py` (3-provider fallback) → injects description as `systemMessage`. The agent never knows it couldn't see.

### ForceLink

`Stop` hook → reads the last assistant message from the transcript → strips code blocks/inline code/existing URLs → scans prose for bare paths (absolute, `~/`, relative-with-extension) → generates the correct clickable URL for each → blocks the Stop with a remediation list until every path is clickable.

## Test

```bash
git clone https://github.com/roham/manifest-it.git
cd manifest-it
# ForceLink tests (from the original forcelink repo)
bash hooks/forcelink.sh < test-fixtures/bare-path.json
```

## License

MIT — see [LICENSE](LICENSE). ForceLink is also MIT, bundled unmodified in logic.
