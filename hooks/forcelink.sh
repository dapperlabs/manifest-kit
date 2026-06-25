#!/bin/bash
# forcelink.sh — ForceLink: Claude Code Stop hook (URL enforcement gate)
# Bundled from https://github.com/roham/forcelink (MIT) into manifest-it.
#
# Forces agents to share file references as clickable URL links, never bare
# file paths. When the agent's final turn references a file by bare path in
# prose (not wrapped in a URL), the Stop is BLOCKED until every file reference
# is a clickable link.
#
# Detection:
#   - Reads the last assistant message from the transcript
#   - Extracts bare file paths from prose (absolute, ~/, relative with extensions)
#   - Skips paths inside code blocks, inline code, and paths already in URLs
#   - For each bare path, generates the correct clickable URL
#     (file:// for local, https://github.com/.../blob/... for git repos)
#   - Blocks Stop with a precise remediation list
#
# Override: SKIP_URL_GATE=1
#
# Requires: python3, jq (optional — falls back gracefully)
# License: MIT

set -euo pipefail

[ "${SKIP_URL_GATE:-0}" = "1" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat || true)

# Parse hook payload
if command -v jq >/dev/null 2>&1 && [ -n "$PAYLOAD" ]; then
  STOP_ACTIVE=$(echo "$PAYLOAD" | jq -r '.stop_hook_active // false' 2>/dev/null)
  TRANSCRIPT=$(echo "$PAYLOAD" | jq -r '.transcript_path // ""' 2>/dev/null)
  CWD=$(echo "$PAYLOAD" | jq -r '.cwd // ""' 2>/dev/null)
else
  STOP_ACTIVE="false"; TRANSCRIPT=""; CWD=""
fi
[ "$STOP_ACTIVE" = "true" ] && exit 0
[ -z "$CWD" ] && CWD="$PWD"

# --- extract the last assistant message, detect bare paths, output JSON ---
# All logic in one Python pass for clean JSON output (proper newline escaping).
python3 - "$TRANSCRIPT" "$CWD" <<'PYEOF'
import json, sys, os, re, subprocess

transcript_path = sys.argv[1]
cwd = sys.argv[2]

# --- Step 1: Extract last assistant message from transcript ---
last_msg = ""
if transcript_path and os.path.isfile(transcript_path):
    try:
        for line in open(transcript_path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "assistant" or o.get("role") == "assistant":
                msg = o.get("message", o)
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict)
                    )
                if content and content.strip():
                    last_msg = content
    except Exception:
        pass

if not last_msg:
    sys.exit(0)

# Only scan the last 8000 chars (long messages don't need full scan)
scan_text = last_msg[-8000:]

# --- Step 2: Remove code blocks, inline code, and existing URLs — only scan PROSE ---
prose = re.sub(r'```[\s\S]*?```', ' ', scan_text)
prose = re.sub(r'~~~[\s\S]*?~~~', ' ', prose)
prose = re.sub(r'`[^`\n]+`', ' ', prose)
# Remove existing clickable URLs so we don't flag paths inside them
prose = re.sub(r'https?://[^\s\)]+', ' ', prose)
prose = re.sub(r'file://[^\s\)]+', ' ', prose)

# --- Step 3: Detect bare file paths ---
# Absolute paths: /Users/..., /home/..., /opt/..., /tmp/..., etc.
abs_path_re = re.compile(
    r'(?<!file:)(?<!https:)(?<!http:)(?<!://)(?<!")(?<!\])'
    r'(/(?:Users|home|opt|tmp|var|etc|usr)/(?:[a-zA-Z0-9._-]+/){1,}[a-zA-Z0-9._-]+)'
)
# Tilde paths: ~/...
tilde_path_re = re.compile(
    r'(~/(?:[a-zA-Z0-9._-]+/){1,}[a-zA-Z0-9._-]+)'
)
# Relative paths with file extensions (at least one / separator)
ext_path_re = re.compile(
    r'(?<!/)(?<!\w)'
    r'((?:[a-zA-Z0-9._-]+/){1,}[a-zA-Z0-9._-]+'
    r'\.(?:md|ts|js|py|sh|json|yaml|yml|tsx|jsx|cdc|sql|tf|css|html|txt|toml|xml|env|cfg|conf))'
    r'(?![\w/])'
)

found_paths = set()
for m in abs_path_re.finditer(prose):
    if len(m.group(1)) >= 10:
        found_paths.add(m.group(1))
for m in tilde_path_re.finditer(prose):
    if len(m.group(1)) >= 8:
        found_paths.add(m.group(1))
for m in ext_path_re.finditer(prose):
    if len(m.group(1)) >= 8:
        found_paths.add(m.group(1))

if not found_paths:
    sys.exit(0)

# --- Step 4: Generate clickable URLs for each bare path ---
_git_cache = {}
def get_git_info(repo_dir):
    if repo_dir in _git_cache:
        return _git_cache[repo_dir]
    try:
        remote = subprocess.check_output(
            ["git", "-C", repo_dir, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        https_url = re.sub(r'git@github\.com:', 'https://github.com/', remote)
        https_url = re.sub(r'\.git$', '', https_url)
        https_url = re.sub(r'git@[^:]+:', 'https://', https_url)
        if 'github.com' not in https_url:
            _git_cache[repo_dir] = (None, None)
            return (None, None)
        branch = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        _git_cache[repo_dir] = (https_url, branch)
        return (https_url, branch)
    except Exception:
        _git_cache[repo_dir] = (None, None)
        return (None, None)

def find_git_root_from_cwd(cwd):
    check_dir = cwd
    for _ in range(15):
        if os.path.isdir(os.path.join(check_dir, ".git")):
            return check_dir
        parent = os.path.dirname(check_dir)
        if parent == check_dir:
            break
        check_dir = parent
    return None

def to_clickable(path, cwd):
    # Tilde paths → file://
    if path.startswith("~/"):
        return f"file://{os.path.expanduser(path)}"
    # Absolute paths → file://
    if path.startswith("/"):
        return f"file://{path}"
    # Relative paths → try GitHub URL, fall back to file://
    git_root = find_git_root_from_cwd(cwd)
    if git_root:
        https_url, branch = get_git_info(git_root)
        if https_url and branch:
            return f"{https_url}/blob/{branch}/{path}"
    # Fall back to file:// with absolute path
    return f"file://{os.path.realpath(os.path.join(cwd, path))}"

violations = []
for path in sorted(found_paths):
    clickable = to_clickable(path, cwd)
    violations.append(f"  BARE: {path}\n  → USE: {clickable}")

violation_text = "\n\n".join(violations)

# --- Step 5: Output block decision as valid JSON ---
reason = (
    "URL ENFORCEMENT GATE: Your final message contains bare file paths "
    "instead of clickable URL links. Always give clickable links, never "
    "bare file paths. Fix each one below before finishing:\n\n"
    f"{violation_text}\n\n"
    "Convert every bare path to its clickable form "
    "(file:// for local files, "
    "https://github.com/{owner}/{repo}/blob/{branch}/{path} for pushed files, "
    "https://github.com/{owner}/{repo}/commit/{sha} for commits). "
    "Then re-submit. Override: SKIP_URL_GATE=1."
)

print(json.dumps({"decision": "block", "reason": reason}))
PYEOF
exit 0
