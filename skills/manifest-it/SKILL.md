---
name: manifest-it
description: Substrate ergonomic-fix grab bag. Use PROACTIVELY when (a) the main model cannot see an image (returns "[image omitted: model does not support vision]") — the vision bridge auto-describes it; (b) a text-only model needs to generate an image — the image-gen bridge routes to gpt-image-2; (c) you are about to finish a turn referencing files by bare path — ForceLink will block you, always use clickable URLs; (d) you need the distilled operating ethos (a16z/Garry Tan hybrid). Never tell a user "I can't see images" or "I can't generate images" — the bridge handles it. Never end a turn with bare file paths.
version: 0.1.0
---

# ManifestIt

A shipping manifest of small substrate fixes that make every Claude Code
session more capable and more ergonomic. Four things, bundled because they're
all "the substrate should just handle this" fixes.

## 1. Vision bridge — automatic, no opt-in

A `PostToolUse` hook on `Read` watches for the omission marker Claude Code
emits when a model can't process an image:

> `[image omitted: model does not support vision]`

When it sees that marker on an image file, it automatically:

1. Extracts the image path from the `Read` tool input.
2. Calls a vision-capable model (Gemini → gpt-4o → Claude Opus fallback chain)
   to describe/transcribe the image with exhaustive precision.
3. Injects the description back into your context as a `systemMessage`.

**You do nothing.** The next turn, you "see" the image via the bridge's
description. Never tell a user "I can't see images" — you can, through the
bridge. Act on the description as if it were the image's content.

### When it fires
- Only on `Read` of a real image file on disk (`.png`, `.jpg`, `.jpeg`,
  `.webp`, `.gif`, `.bmp`).
- Only when the tool result contains an omission marker.
- Internal URIs (`local://`, `artifact://`) and non-image files are skipped.

### Manual vision call (advanced)
If you need a *different* description (e.g. a design-QA critique rather than a
transcription), call the bridge script directly with a custom prompt:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vision_describe.py" /path/to/image.png "Your custom prompt"
```

Fallback chain and API keys are resolved automatically from env:
`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (first set + working wins).

## 2. Image generation — routes to gpt-image-2

If your main model cannot generate images and a task requires one, use the
image-gen bridge. It routes to OpenAI's `gpt-image-2` by default (override via
`CAPABILITY_BRIDGE_IMAGE_MODEL` if a newer model ships — set the env var to
upgrade with no code change).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/image_generate.py" \
  /path/to/output.png \
  "A sleek glass toast notification, semi-transparent, refractive, dark obsidian" \
  --size 1024x1024 --quality high
```

- Saves the generated image to the path you specify (parents created).
- Prints the saved path on stdout.
- `--size`: `1024x1024` (default), `1024x1536`, `1536x1024`.
- `--quality`: `high` (default) | `medium` | `low`.
- Requires `OPENAI_API_KEY`.

## 3. ForceLink — never end a turn with bare file paths

A `Stop` hook blocks your turn from ending if your final message contains a
bare file path in prose (`/Users/foo/bar.ts`, `~/dapper/config.json`,
`src/index.ts`). It tells you exactly which paths to fix and what clickable URL
to use instead:

- **Local files** → `file:///absolute/path`
- **Pushed files** → `https://github.com/{owner}/{repo}/blob/{branch}/{path}`
- **Commits** → `https://github.com/{owner}/{repo}/commit/{sha}`

Paths inside code blocks, inline code, and existing URLs are skipped — only
prose is scanned. Override with `SKIP_URL_GATE=1` when bare paths are
intentional.

This is structural, not advisory. CLAUDE.md rules get ignored; ForceLink makes
the turn literally unable to end until every file reference is clickable. The
user consumes output by clicking, not by `cd`-ing into a terminal.

## 4. Operating ethos — distilled (a16z / Garry Tan hybrid)

A sanitized, portable distillation of the operating principles every agent on
this machine should carry. It's in `references/ethos.md` — read it when you
need to calibrate stance, tone, or decision-making posture. It is deliberately
short: principles, not essays.

## Principles across all four

1. **Never dead-end on capability.** If the main model lacks vision or
   image-gen, the bridge provides it. State what you're doing and proceed.
2. **The bridge is the substrate.** It runs for every session, every agent,
   every subagent. No per-agent wiring.
3. **Output is for humans.** Clickable links, not bare paths. The substrate
   enforces this — don't fight the gate.
4. **Cost-bounded.** Vision calls use fast/cheap models first (Gemini Flash,
   gpt-4o-mini) and only escalate to Opus if earlier providers fail.

## Failure modes

- **No API keys set at all** → vision bridge reports "all providers exhausted"
  and the agent treats the image as genuinely unavailable (rare; CLAUDE.md
  pre-authorizes Gemini/OpenAI/Anthropic keys on this machine).
- **Image file missing** → vision hook exits silently; the `Read` error already
  reached the agent.
- **Network timeout** → 120s cap; bridge emits a timeout message and the agent
  proceeds without the description.
- **ForceLink false positive** → override with `SKIP_URL_GATE=1` for that
  session; report the case so the detector can be tightened.
