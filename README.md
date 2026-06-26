# manifest-kit

Roham's toolkit for AI behavior — structural hooks that make agents behave correctly. Vision bridge, image-gen bridge, ForceLink, locate-yourself gate, search-before-assert, finish-not-flag, deliverable-quality, model-stack-persistence, agent-verify cognitive verification, and a reconciliation checker. Spec: [SPEC-022](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/022-ai-behavior-toolkit/spec.md).

> Renamed from `manifest-it` / `ai-manifest-it` on 2026-06-26. The repo is now `dapperlabs/manifest-kit`.

## What it is

A Claude Code plugin that bundles every structural fix for agent behavior. Two components:

### Hooks (behavior guards)
The things the agent *can't do without help* and *shouldn't do wrong*:

1. **Vision bridge** — auto-describes images a text-only model can't see (PostToolUse on Read).
2. **Image-gen bridge** — routes image generation to OpenAI for text-only models.
3. **ForceLink** — blocks turns ending with bare file paths; forces clickable URLs.
4. **Distilled ethos** — portable operating principles (not essays).
5. **Locate-yourself** — SessionStart gate that tells the agent what room it's in (reads `worldmodel.md`).
6. **Non-main-branch** — blocks commits to non-main branches on non-boot repos.
7. **Search-before-assert** — blocks "doesn't exist" claims without search evidence.
8. **Finish-not-flag** — blocks "worth noting" when the task isn't actually done.
9. **Deliverable-quality** — asserts minimum quality for declared deliverables.
10. **agent-verify input check** — PreToolUse check that inputs contain real content, not metadata (from [roham/agent-verify](https://github.com/roham/agent-verify), wraps the council-verify ladder).
11. **agent-verify output check** — PostToolUse check that outputs contain actual value, not vacuous structure.

### Checker (reconciliation)
Merged from [SPEC-021](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/021-robocop-reconciliation/spec.md) (was: RoboCop). A deterministic cron job that checks:
- Are the hooks installed and working?
- Are specs stale or dropped?
- Is data in the wrong org?
- Is `worldmodel.md` present and consistent with the README?
- Is the deployed VM code committed?

Not an agent — a deterministic script. Runs on cadence, surfaces divergences, never remediates.

## Install

### As a Claude Code plugin (recommended)

```bash
git clone https://github.com/dapperlabs/manifest-kit.git ~/.claude/plugins/manifest-kit
```

Then add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/plugins/manifest-kit/hooks/vision_bridge_hook.py", "timeout": 130 }
        ]
      },
      {
        "matcher": "Bash|Task|Agent|Write",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/plugins/manifest-kit/hooks/agent_verify_post_check.py" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Read|Task|Agent",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/plugins/manifest-kit/hooks/agent_verify_pre_check.py" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "bash ~/.claude/plugins/manifest-kit/hooks/forcelink.sh", "timeout": 15 }
        ]
      }
    ]
  }
}
```

Restart Claude Code. Done.

### Hooks only (no plugin system)

```bash
# ForceLink
curl -o ~/.claude/hooks/forcelink.sh https://raw.githubusercontent.com/dapperlabs/manifest-kit/main/hooks/forcelink.sh
chmod +x ~/.claude/hooks/forcelink.sh

# Vision bridge
curl -o ~/.claude/hooks/vision_bridge_hook.py https://raw.githubusercontent.com/dapperlabs/manifest-kit/main/hooks/vision_bridge_hook.py
curl -o ~/.claude/scripts/vision_describe.py https://raw.githubusercontent.com/dapperlabs/manifest-kit/main/scripts/vision_describe.py

# agent-verify hooks (requires agent-verify library)
pip install git+https://github.com/roham/agent-verify.git
curl -o ~/.claude/hooks/agent_verify_pre_check.py https://raw.githubusercontent.com/dapperlabs/manifest-kit/main/hooks/agent_verify_pre_check.py
curl -o ~/.claude/hooks/agent_verify_post_check.py https://raw.githubusercontent.com/dapperlabs/manifest-kit/main/hooks/agent_verify_post_check.py
```

## Requirements

- **python3** (pre-installed on macOS, most Linux distros)
- **jq** (optional — ForceLink falls back gracefully if not installed)
- For the vision bridge: at least one of `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- For the image-gen bridge: `OPENAI_API_KEY`
- For agent-verify: the [council plugin](https://github.com/dapperlabs/dapper-claude-code-plugins) + `llm` CLI

## Configuration

| Env var | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | Vision bridge provider 1 | — |
| `OPENAI_API_KEY` | Vision bridge provider 2 / image-gen | — |
| `ANTHROPIC_API_KEY` | Vision bridge provider 3 | — |
| `CAPABILITY_BRIDGE_IMAGE_MODEL` | Image-gen model | `gpt-image-2` |
| `SKIP_URL_GATE` | `1` to bypass ForceLink | — |
| `SKIP_VISION_BRIDGE` | `1` to skip vision bridge | — |
| `DAPPER_TOOLKIT_ADVISORY` | `1` = force all guards to advisory (never block) | — |

## Related

- [agent-verify](https://github.com/roham/agent-verify) — cognitive verification library (council-verify ladder wrapper)
- [SPEC-022](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/022-ai-behavior-toolkit/spec.md) — the spec that governs this toolkit
- [SPEC-024](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/024-room-manifest/spec.md) — worldmodel.md spec
- [SPEC-021](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/021-robocop-reconciliation/spec.md) — reconciliation checker (merged into this repo)

## License

MIT — see [LICENSE](LICENSE). ForceLink is also MIT, bundled unmodified in logic.
