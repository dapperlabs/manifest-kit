# Local Boot Ritual

The boot sequence for a team member's local Claude Code session. Governed by [SPEC-026](https://github.com/dapperlabs/agi-knowledge/blob/main/strategy/specs/026-local-boot-ritual/spec.md).

## The sequence (6 steps)

```
1. ~/.claude/CLAUDE.md loads          ← universal rules (the seed)
2. Project CLAUDE.md loads            ← if present at repo root (team-shared)
3. CLAUDE.local.md loads              ← if present (personal, gitignored)
4. worldmodel.md loads                ← if in a repo with worldmodel.md
5. Hooks fire                         ← manifest-kit hooks activate
6. Agent is oriented                  ← knows the rules, knows the room
```

That's it. No identity files, no memory retrieval, no wiki scan. The agent starts with rules + room context + active hooks.

## What loads at boot

| Source | What it provides | When |
|--------|-----------------|------|
| `~/.claude/CLAUDE.md` | Universal execution rules, accuracy bar, output format | Every session |
| `./CLAUDE.md` | Project-specific conventions, build commands, architecture | If present in repo |
| `./CLAUDE.local.md` | Personal project preferences (gitignored) | If present |
| `worldmodel.md` | Room identity, active specs, key commands, gotchas | If present in repo |
| manifest-kit hooks | ForceLink, vision bridge, agent-verify, locate-yourself | Every session (if installed) |

## What does NOT load at boot (pulled JIT)

| Source | When it loads |
|--------|--------------|
| HQ repo research (market-research/, datascience/) | When the task needs it |
| Product constitution | When the task needs it |
| Specs, plans, tasks | When the task needs it (or when spec-kit gate fires) |
| Personas, intelligence briefs | When the task needs it |
| ethos.md (deeper operating stance) | When the skill auto-loads it |

## CGS vs Local

This ritual is for **local agents** — a person + Claude Code on a laptop. CGS agents (Dexter, The General, Socrates) have a different, more complex boot sequence with identity, memory, voice-DNA, and session-state. Those are governed by the agent-specific specs, not this one.

| | Local (this doc) | CGS |
|--|---|---|
| Identity | None — `## You` is blank | Full identity (identity.md, origin-seed, voice-DNA) |
| Memory | None at boot | Wiki retrieval every turn |
| Session state | None | On-disk goal/DoD/active-deferred tasks |
| Boot steps | 6 | 7+ |
| Complexity | Simple | Complex |

## Installing the seed

```bash
# Via manifest-kit installer
git clone https://github.com/dapperlabs/manifest-kit.git
bash manifest-kit/bin/install.sh

# Or manually
cp manifest-kit/templates/CLAUDE.md ~/.claude/CLAUDE.md
# Then edit the ## You section
```

The installer won't overwrite an existing `~/.claude/CLAUDE.md`. It prints the template path and lets you decide.
