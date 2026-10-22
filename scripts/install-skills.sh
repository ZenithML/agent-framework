#!/bin/bash
# install-skills.sh — copy the sdd harness directly into a consuming project's
# .claude/ directory (skills, agents, standards, templates, config, hook).
#
# Unlike vendor.sh (which installs the plugin via a local marketplace), this
# "flat" install commits the harness as plain repo-committed .claude/skills/ and
# .claude/agents/ so they load in EVERY session type — local, claude.ai/code,
# and CI — with no marketplace install step. This is the recommended method.
# Skills install WITHOUT the sdd: namespace, so they are invoked as /ship,
# /spec, /sdd-init, etc.
#
# Pass --with-render to additionally install the render plugin (perceptual
# verification: capture endpoint, named observation set, traps). Its skills also
# install without a namespace, so they are invoked as /frames, /tune, /trap,
# /render-init. Omit it for projects with no visual output.
#
# --harness picks which agent CLIs the project is wired for (default: claude,agy).
# .claude/ is always the canonical copy. agy / Antigravity and Codex both read
# skills from .agents/skills, which links to .claude/skills. codex additionally
# generates .codex/agents/*.toml from the agents and, when the project has a
# .mcp.json, mirrors its servers into .codex/config.toml (scripts/codex_adapt.py).
#
# Re-running over an earlier install updates it. Harness files the project has
# edited since are kept, not overwritten (see step 2); pass --overwrite-local to
# replace them with the new release anyway.
#
# Usage:
#   scripts/install-skills.sh [--dry-run] [--force] [--with-render] [--overwrite-local] [--harness LIST] <target-project-dir>

set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HARNESS_DIR/plugins/sdd"
RENDER_DIR="$HARNESS_DIR/plugins/render"
DRY_RUN=false
FORCE=false
WITH_RENDER=false
OVERWRITE_LOCAL=false
HARNESSES="claude,agy"

usage() {
  cat <<'USAGE' >&2
Usage: scripts/install-skills.sh [--dry-run] [--force] [--with-render] [--overwrite-local] [--harness LIST] <target-project-dir>
  --dry-run, -d     Show actions without copying or writing files
  --force, -f       Install even if the target .claude/ has non-harness skills/agents
  --with-render     Also install the render plugin (perceptual verification)
  --overwrite-local Replace harness files edited in the target with the new release
  --harness LIST    Comma list of claude, agy, codex (default: claude,agy; .claude/ is always installed)
USAGE
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-d) DRY_RUN=true; shift ;;
    --force|-f) FORCE=true; shift ;;
    --with-render) WITH_RENDER=true; shift ;;
    --overwrite-local) OVERWRITE_LOCAL=true; shift ;;
    --harness) HARNESSES="${2:-}"; [ -n "$HARNESSES" ] || usage; shift 2 ;;
    --help|-h) usage ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) TARGET="$1"; shift; break ;;
  esac
done

[ -n "${TARGET:-}" ] || usage
[ -d "$TARGET" ] || { echo "Error: '$TARGET' is not a directory." >&2; exit 1; }

WANT_AGY=false; WANT_CODEX=false
HARNESSES="${HARNESSES//[[:space:]]/}"
IFS=',' read -ra _H <<< "$HARNESSES"
for h in "${_H[@]}"; do
  case "$h" in
    claude) ;;
    agy) WANT_AGY=true ;;
    codex) WANT_CODEX=true ;;
    *) echo "Error: unknown harness '$h' (expected claude, agy, codex)." >&2; exit 1 ;;
  esac
done
# Codex discovers skills at .agents/skills, the same path agy uses.
[ "$WANT_CODEX" = true ] && WANT_AGY=true

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found in PATH." >&2
  exit 1
fi

CLAUDE_DIR="$TARGET/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"
HARNESS_VERSION="$(python3 -c "import json;print(json.load(open('$PLUGIN_DIR/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo unknown)"

echo "Installing sdd harness v${HARNESS_VERSION} into $TARGET/.claude/ (flat copy)..."

if [ "$DRY_RUN" = true ]; then
  echo "DRY-RUN: no changes will be made."
  echo "Planned actions:"
  echo "  - copy plugins/sdd/{skills,agents,standards,templates/docs,config,hooks} into $CLAUDE_DIR/"
  [ "$WITH_RENDER" = true ] && echo "  - copy plugins/render/{skills,standards} into $CLAUDE_DIR/"
  echo "  - rewrite \${CLAUDE_PLUGIN_ROOT} -> .claude and /sdd:<skill> -> /<skill> in copied markdown"
  echo "  - keep harness files edited since the last install (manifest: $CLAUDE_DIR/sdd/.harness-manifest)"
  echo "  - declare the SessionStart hook in $SETTINGS"
  [ "$WANT_AGY" = true ] && echo "  - symlink $TARGET/.agents/skills -> ../.claude/skills (for agy / Antigravity / Codex)"
  [ "$WANT_CODEX" = true ] && echo "  - generate $TARGET/.codex/agents/*.toml from the agents, and mirror .mcp.json into $TARGET/.codex/config.toml"
  echo "  - write $CLAUDE_DIR/sdd/.harness-version ($HARNESS_VERSION)"
  echo "Re-run without --dry-run to apply."
  exit 0
fi

# Guard against clobbering a .claude/ that this script did not create. A prior
# harness install leaves a version stamp, so re-running over it is a normal
# update and proceeds. Without that stamp, an existing skills/ or agents/ dir
# means a foreign .claude/ — abort unless the caller passes --force.
if [ "$FORCE" = false ] && [ ! -f "$CLAUDE_DIR/sdd/.harness-version" ] \
   && { [ -d "$CLAUDE_DIR/skills" ] || [ -d "$CLAUDE_DIR/agents" ]; }; then
  echo "Error: $CLAUDE_DIR already has skills/ or agents/ but no harness version" >&2
  echo "stamp — this looks like a non-harness .claude/ directory. Re-run with" >&2
  echo "--force to install anyway (existing same-named files will be overwritten)." >&2
  exit 1
fi

# 1. Stage the harness in a temp dir: copy skills, agents, standards, templates,
#    config schema/examples and hook, then rewrite them for a flat install. The
#    staged tree is synced into the target in step 2, which is what lets a re-run
#    tell an upstream change apart from a local edit.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
S="$STAGE/.claude"
mkdir -p "$S/skills" "$S/agents" "$S/standards" "$S/templates/docs" "$S/sdd" "$S/hooks"
cp -r "$PLUGIN_DIR/skills/." "$S/skills/"
cp -r "$PLUGIN_DIR/agents/." "$S/agents/"
cp -r "$PLUGIN_DIR/standards/." "$S/standards/"
cp -r "$PLUGIN_DIR/templates/docs/." "$S/templates/docs/"
cp "$PLUGIN_DIR/config/"*.json "$S/sdd/"
cp "$PLUGIN_DIR/hooks/remote-session-start.sh" "$S/hooks/"

# 1b. The render plugin is opt-in: most projects have nothing to look at.
if [ "$WITH_RENDER" = true ]; then
  cp -r "$RENDER_DIR/skills/." "$S/skills/"
  cp -r "$RENDER_DIR/standards/." "$S/standards/"
fi

# 1c. Rewrite the staged markdown for a flat install. Done in Python for
#     portability — BSD/macOS `sed -i` is incompatible with GNU.
#     - ${CLAUDE_PLUGIN_ROOT} -> repo-relative .claude/ paths. Order matters: the
#       /config special case must run before the generic rule. A plugin-root
#       line that becomes a copy of a line already in the same fenced block (a
#       list naming both .claude/skills/ and the plugin's skills/) is dropped.
#     - /sdd:<skill> and /render:<skill> -> /<skill>: flat-installed skills
#       carry no namespace. A note that names the namespaced form on purpose
#       ("or `/sdd:x` when installed as a plugin") is left as is.
python3 - "$S" <<'PYEOF'
import os, re, sys
root = sys.argv[1]
NAMESPACE = re.compile(r'/(?:sdd|render):(?=[a-z<])(?![\w-]+` when installed as a plugin)')

def rewrite(text):
    out, block, in_fence = [], set(), False
    for line in text.split('\n'):
        if line.lstrip().startswith('```'):
            in_fence, block = not in_fence, set()
            out.append(line)
            continue
        new = line.replace('${CLAUDE_PLUGIN_ROOT}/config', '.claude/sdd')
        new = new.replace('${CLAUDE_PLUGIN_ROOT}', '.claude')
        if in_fence and new != line and new in block:
            continue
        if in_fence:
            block.add(new)
        out.append(NAMESPACE.sub('/', new))
    return '\n'.join(out)

for sub in ('skills', 'agents', 'standards'):
    for dirpath, _dirs, files in os.walk(os.path.join(root, sub)):
        for name in files:
            if not name.endswith('.md'):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            new = rewrite(text)
            if new != text:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(new)
PYEOF

# 2. Sync the staged tree into the target. .claude/sdd/.harness-manifest records
#    the sha256 of every file as this script installed it, so a re-run can tell
#    a local edit (target differs from the manifest) from an upstream change
#    (staged file differs from the manifest):
#    - unedited files are updated to the new release;
#    - a locally edited file is kept. If upstream also changed it, the new
#      upstream copy goes to .claude/sdd/upstream/<path> for a manual merge,
#      unless --overwrite-local is given;
#    - a file the new release no longer ships is deleted, unless edited locally.
#    With no manifest (first install, or an install that predates it) every
#    harness file is overwritten, as before.
python3 - "$S" "$CLAUDE_DIR" "$OVERWRITE_LOCAL" <<'PYEOF'
import hashlib, json, os, shutil, sys
stage, dest, overwrite_local = sys.argv[1], sys.argv[2], sys.argv[3] == 'true'
manifest_path = os.path.join(dest, 'sdd', '.harness-manifest')
upstream_dir = os.path.join(dest, 'sdd', 'upstream')

def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()

old = None
if os.path.exists(manifest_path):
    with open(manifest_path) as fh:
        old = json.load(fh).get('files', {})
shutil.rmtree(upstream_dir, ignore_errors=True)

new, kept, conflicts, removed = {}, [], [], []
for dirpath, _dirs, files in os.walk(stage):
    for name in files:
        src = os.path.join(dirpath, name)
        rel = os.path.relpath(src, stage)
        dst = os.path.join(dest, rel)
        new[rel] = sha(src)
        if os.path.exists(dst):
            current = sha(dst)
            if current == new[rel]:
                continue
            edited = old is not None and rel in old and current != old[rel]
            if edited and not overwrite_local:
                kept.append(rel)
                if new[rel] != old[rel]:
                    conflicts.append(rel)
                    os.makedirs(os.path.dirname(os.path.join(upstream_dir, rel)), exist_ok=True)
                    shutil.copy2(src, os.path.join(upstream_dir, rel))
                continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

for rel, digest in (old or {}).items():
    dst = os.path.join(dest, rel)
    if rel in new or not os.path.exists(dst):
        continue
    if sha(dst) != digest and not overwrite_local:
        kept.append(rel)
        continue
    os.remove(dst)
    removed.append(rel)
    parent = os.path.dirname(dst)
    while parent != dest and not os.listdir(parent):
        os.rmdir(parent)
        parent = os.path.dirname(parent)

with open(manifest_path, 'w') as fh:
    json.dump({'files': dict(sorted(new.items()))}, fh, indent=2)
    fh.write('\n')

print('  Synced harness files into .claude/')
if old is None:
    print('  No .harness-manifest found: harness files were overwritten. Review `git diff`')
    print('  for local edits to re-apply; later re-runs keep them automatically.')
for rel in removed:
    print(f'  Removed {rel} (no longer shipped)')
for rel in sorted(set(kept) - set(conflicts)):
    print(f'  Kept local edits: {rel}')
if conflicts:
    print('  Kept local edits, but upstream changed these too — merge by hand from', file=sys.stderr)
    print('  .claude/sdd/upstream/ (do not commit that dir), or re-run with --overwrite-local:', file=sys.stderr)
    for rel in conflicts:
        print(f'    {rel}', file=sys.stderr)
PYEOF

# 3. Declare the SessionStart hook in settings.json (no plugin to auto-load it).
python3 - "$SETTINGS" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
settings = {}
if os.path.exists(path):
    with open(path) as fh:
        settings = json.load(fh)
# bash, not sh: the hook script uses `set -o pipefail`, which dash (/bin/sh on
# Debian/Ubuntu) rejects.
cmd = 'bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/remote-session-start.sh"'
script = 'remote-session-start.sh'
hooks = settings.setdefault('hooks', {}).setdefault('SessionStart', [])
# Match on the script path so a re-run replaces an older or hand-edited
# invocation (e.g. `sh ...`) instead of appending a duplicate.
found = False
for entry in hooks:
    for h in entry.get('hooks', []):
        if script in h.get('command', ''):
            h['command'] = cmd
            found = True
if not found:
    hooks.append({'hooks': [{'type': 'command', 'command': cmd}]})
with open(path, 'w') as fh:
    json.dump(settings, fh, indent=2)
    fh.write('\n')
print(f"  Updated {path}")
PYEOF

# 4. Expose the skills to Antigravity (agy) and Codex, which scan .agents/skills/
#    and not .claude/skills/. A relative symlink keeps a single copy of the skills.
#    Never clobber an existing .agents/skills that is not already our link.
if [ "$WANT_AGY" = true ]; then
LINK="$TARGET/.agents/skills"
EXPECTED="../.claude/skills"
if [ -L "$LINK" ]; then
  if [ "$(readlink "$LINK")" = "$EXPECTED" ]; then
    echo "  .agents/skills symlink already in place"
  else
    mkdir -p "$TARGET/.agents"
    rm -f "$LINK"
    ln -s "$EXPECTED" "$LINK"
    echo "  Updated .agents/skills -> $EXPECTED (agy / Antigravity discovery)"
  fi
elif [ -e "$LINK" ]; then
  echo "  Warning: $LINK exists and is not a symlink to $EXPECTED; left as is." >&2
  echo "           agy / Codex will not see the sdd skills until you link or copy them there." >&2
else
  mkdir -p "$TARGET/.agents"
  ln -s "$EXPECTED" "$LINK"
  echo "  Linked .agents/skills -> $EXPECTED (agy / Antigravity / Codex discovery)"
fi
fi

# 4b. Codex: custom subagents are TOML files in .codex/agents/, generated from
#     the installed (already path-rewritten) agents so the two cannot drift. The
#     project's .mcp.json is mirrored into .codex/config.toml, since Codex does
#     not read .mcp.json and ignores mcp_servers inside an agent file.
if [ "$WANT_CODEX" = true ]; then
  python3 "$HARNESS_DIR/scripts/codex_adapt.py" agents "$CLAUDE_DIR/agents" "$TARGET/.codex/agents"
  python3 "$HARNESS_DIR/scripts/codex_adapt.py" mcp "$TARGET/.mcp.json" "$TARGET/.codex/config.toml"
fi

# 5. Write a version stamp so consumers can detect when an update is available.
printf '%s\n' "$HARNESS_VERSION" > "$CLAUDE_DIR/sdd/.harness-version"

echo ""
if [ "$WITH_RENDER" = true ]; then
  echo "Done. sdd harness v${HARNESS_VERSION} + render plugin installed into .claude/."
else
  echo "Done. sdd harness v${HARNESS_VERSION} installed into .claude/ (skills, agents, standards, templates, config, hook)."
fi
echo ""
echo "Next steps:"
echo "  cd \"$(realpath "$TARGET")\""
echo "  git add .claude/ $([ "$WANT_AGY" = true ] && echo .agents/) $([ "$WANT_CODEX" = true ] && echo .codex/)"
echo "  git commit -m 'chore: install sdd harness (flat) v${HARNESS_VERSION}'"
echo ""
if [ "$WANT_CODEX" = true ]; then
  echo "Commit .codex/ and .agents/ too. Codex loads project .codex/ config only for a trusted project."
  echo "Then open Claude Code or Codex and run /sdd-init (Codex: \$sdd-init)."
else
  echo "Then open Claude Code and run /sdd-init."
fi
echo "To update later, re-run this script from an updated harness checkout."
