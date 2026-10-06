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
# Usage:
#   scripts/install-skills.sh [--dry-run] [--force] [--with-render] <target-project-dir>

set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HARNESS_DIR/plugins/sdd"
RENDER_DIR="$HARNESS_DIR/plugins/render"
DRY_RUN=false
FORCE=false
WITH_RENDER=false

usage() {
  cat <<'USAGE' >&2
Usage: scripts/install-skills.sh [--dry-run] [--force] [--with-render] <target-project-dir>
  --dry-run, -d     Show actions without copying or writing files
  --force, -f       Install even if the target .claude/ has non-harness skills/agents
  --with-render     Also install the render plugin (perceptual verification)
USAGE
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-d) DRY_RUN=true; shift ;;
    --force|-f) FORCE=true; shift ;;
    --with-render) WITH_RENDER=true; shift ;;
    --help|-h) usage ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) TARGET="$1"; shift; break ;;
  esac
done

[ -n "${TARGET:-}" ] || usage
[ -d "$TARGET" ] || { echo "Error: '$TARGET' is not a directory." >&2; exit 1; }

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
  echo "  - rewrite \${CLAUDE_PLUGIN_ROOT} -> .claude in copied skills/agents/standards"
  echo "  - declare the SessionStart hook in $SETTINGS"
  echo "  - symlink $TARGET/.agents/skills -> ../.claude/skills (for agy / Antigravity)"
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

# 1. Copy skills, agents, standards, templates, config schema/examples, and hook
mkdir -p "$CLAUDE_DIR/skills" "$CLAUDE_DIR/agents" "$CLAUDE_DIR/standards" \
         "$CLAUDE_DIR/templates/docs" "$CLAUDE_DIR/sdd" "$CLAUDE_DIR/hooks"
cp -r "$PLUGIN_DIR/skills/." "$CLAUDE_DIR/skills/"
cp -r "$PLUGIN_DIR/agents/." "$CLAUDE_DIR/agents/"
cp -r "$PLUGIN_DIR/standards/." "$CLAUDE_DIR/standards/"
cp -r "$PLUGIN_DIR/templates/docs/." "$CLAUDE_DIR/templates/docs/"
cp "$PLUGIN_DIR/config/"*.json "$CLAUDE_DIR/sdd/"
cp "$PLUGIN_DIR/hooks/remote-session-start.sh" "$CLAUDE_DIR/hooks/"
echo "  Copied harness files into .claude/"

# 1b. The render plugin is opt-in: most projects have nothing to look at.
if [ "$WITH_RENDER" = true ]; then
  cp -r "$RENDER_DIR/skills/." "$CLAUDE_DIR/skills/"
  cp -r "$RENDER_DIR/standards/." "$CLAUDE_DIR/standards/"
  echo "  Copied render plugin files into .claude/"
fi

# 2. Rewrite ${CLAUDE_PLUGIN_ROOT} references to repo-relative .claude/ paths.
#    Done in Python for portability — BSD/macOS `sed -i` is incompatible with GNU.
#    Order matters: the /config special case must run before the generic rule.
python3 - "$CLAUDE_DIR" <<'PYEOF'
import os, sys
root = sys.argv[1]
for sub in ('skills', 'agents', 'standards'):
    for dirpath, _dirs, files in os.walk(os.path.join(root, sub)):
        for name in files:
            if not name.endswith('.md'):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            new = text.replace('${CLAUDE_PLUGIN_ROOT}/config', '.claude/sdd')
            new = new.replace('${CLAUDE_PLUGIN_ROOT}', '.claude')
            if new != text:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(new)
PYEOF
echo "  Rewrote \${CLAUDE_PLUGIN_ROOT} path references to .claude/"

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

# 4. Expose the skills to Antigravity (agy), which scans .agents/skills/ and not
#    .claude/skills/. A relative symlink keeps a single copy of the skills.
#    Never clobber an existing .agents/skills that is not already our link.
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
  echo "           agy will not see the sdd skills until you link or copy them there." >&2
else
  mkdir -p "$TARGET/.agents"
  ln -s "$EXPECTED" "$LINK"
  echo "  Linked .agents/skills -> $EXPECTED (agy / Antigravity discovery)"
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
echo "  git add .claude/"
echo "  git commit -m 'chore: install sdd harness (flat) v${HARNESS_VERSION}'"
echo ""
echo "Then open Claude Code and run /sdd-init."
echo "To update later, re-run this script from an updated harness checkout."
