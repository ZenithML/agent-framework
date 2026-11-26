#!/bin/bash
# install-skills.sh — copy the sdd harness directly into a consuming project's
# .claude/ directory (skills, agents, standards, templates, config, hook).
#
# Unlike vendor.sh (which installs the plugin via a local marketplace), this
# "flat" install commits the harness as plain repo-committed .claude/skills/ and
# .claude/agents/ so they load in EVERY session type — local, claude.ai/code,
# and CI — with no marketplace install step. This is the recommended method.
# Skills install WITHOUT the sdd: namespace but with a flat prefix, so they are
# invoked as /sdd-ship, /sdd-spec, /sdd-init, etc. and never shadow a built-in.
#
# Pass --with-render to additionally install the render plugin (perceptual
# verification: capture endpoint, named observation set, traps). Its skills also
# install with a flat prefix, so they are invoked as /render-frames,
# /render-tune, /render-trap, /render-init. Omit it for projects with no visual output.
#
# --harness picks which agent CLIs the project is wired for (default: claude,agy).
# .claude/ is always the canonical copy. agy / Antigravity and Codex both read
# skills from .agents/skills, which links to .claude/skills. codex additionally
# reads canonical Markdown roles directly through native subagent delegation.
# Its MCP definitions are synchronized from .mcp.json into .codex/config.toml.
#
# Re-running over an earlier install updates it. Harness files the project has
# edited since are kept, not overwritten (see step 2); pass --overwrite-local to
# replace them with the new release anyway.
#
# Pass --local to try the harness in a project without committing it. Every path
# the install writes is added to the repository's shared .git/info/exclude (so
# linked worktrees see the same exclusions), the SessionStart hook goes into
# .claude/settings.local.json instead of settings.json, and no AGENTS.md is
# seeded. It refuses to run if git already tracks any of those paths.
#
# Usage:
#   scripts/install-skills.sh [--dry-run] [--force] [--with-render] [--overwrite-local] [--local] [--harness LIST] <target-project-dir>

set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HARNESS_DIR/plugins/sdd"
RENDER_DIR="$HARNESS_DIR/plugins/render"
DRY_RUN=false
FORCE=false
WITH_RENDER=false
OVERWRITE_LOCAL=false
LOCAL=false
HARNESSES="claude,agy"

usage() {
  cat <<'USAGE' >&2
Usage: scripts/install-skills.sh [--dry-run] [--force] [--with-render] [--overwrite-local] [--local] [--harness LIST] <target-project-dir>
  --dry-run, -d     Show actions without copying or writing files
  --force, -f       Install even if the target .claude/ has non-harness skills/agents
  --with-render     Also install the render plugin (perceptual verification)
  --overwrite-local Replace harness files edited in the target with the new release
  --local           Personal trial install: git-excluded, hook in settings.local.json, nothing to commit
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
    --local) LOCAL=true; shift ;;
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

# --local: every path this install writes, relative to the project root. They
# go into .git/info/exclude, so they must not already be tracked.
LOCAL_PATHS=()
EXCLUDE_FILE=""
if [ "$LOCAL" = true ]; then
  if [ "$(git -C "$TARGET" rev-parse --show-toplevel 2>/dev/null)" != "$(cd "$TARGET" && pwd -P)" ]; then
    echo "Error: --local needs '$TARGET' to be the root of a git working tree." >&2
    exit 1
  fi
  SETTINGS="$CLAUDE_DIR/settings.local.json"
  EXCLUDE_FILE="$(git -C "$TARGET" rev-parse --path-format=absolute --git-common-dir)/info/exclude"
  LOCAL_PATHS=(.claude/skills .claude/agents .claude/standards .claude/scripts .claude/templates
               .claude/sdd .claude/hooks .claude/settings.local.json)
  [ "$WANT_AGY" = true ] && LOCAL_PATHS+=(.agents/skills)
  [ "$WANT_CODEX" = true ] && LOCAL_PATHS+=(.codex/config.toml)
  TRACKED="$(git -C "$TARGET" ls-files -- "${LOCAL_PATHS[@]}")"
  if [ -n "$TRACKED" ]; then
    echo "Error: --local would change files git already tracks:" >&2
    printf '%s\n' "$TRACKED" | sed 's/^/  /' >&2
    echo "Install without --local and commit the result instead." >&2
    exit 1
  fi
  # With nothing under .claude/ tracked, exclude .claude itself too, so a linked
  # worktree can symlink its .claude to this one and still show a clean status.
  [ -z "$(git -C "$TARGET" ls-files -- .claude)" ] && LOCAL_PATHS+=(.claude)
fi

echo "Installing sdd harness v${HARNESS_VERSION} into $TARGET/.claude/ (flat copy)..."

if [ "$DRY_RUN" = true ]; then
  echo "DRY-RUN: no changes will be made."
  echo "Planned actions:"
  echo "  - copy plugins/sdd/{skills,agents,standards,scripts,templates/docs,config,hooks} into $CLAUDE_DIR/"
  [ "$WITH_RENDER" = true ] && echo "  - copy plugins/render/{skills,standards} into $CLAUDE_DIR/"
  echo "  - rewrite \${CLAUDE_PLUGIN_ROOT} -> .claude and /sdd:<skill> -> /sdd-<skill> in copied markdown"
  echo "  - keep harness files edited since the last install (manifest: $CLAUDE_DIR/sdd/.harness-manifest)"
  echo "  - declare the SessionStart hook in $SETTINGS"
  [ "$WANT_AGY" = true ] && echo "  - symlink $TARGET/.agents/skills -> ../.claude/skills (for agy / Antigravity / Codex)"
  [ "$WANT_CODEX" = true ] && echo "  - use shared Markdown roles and synchronize .mcp.json into $TARGET/.codex/config.toml"
  if [ "$LOCAL" = true ]; then
    echo "  - add ${LOCAL_PATHS[*]} to $EXCLUDE_FILE; seed no AGENTS.md"
  else
    echo "  - seed AGENTS.md routing only if absent; preserve existing project guidance"
  fi
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

# Validate shared MCP input before writing any consumer files.
if [ "$WANT_CODEX" = true ]; then
  python3 - "$HARNESS_DIR/scripts" "$TARGET" <<'PYMCP'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sync_mcp import plan
plan(Path(sys.argv[2]))
PYMCP
fi

# 1. Stage the harness in a temp dir: copy skills, agents, standards, templates,
#    config schema/examples and hook, then rewrite them for a flat install. The
#    staged tree is synced into the target in step 2, which is what lets a re-run
#    tell an upstream change apart from a local edit.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
S="$STAGE/.claude"
mkdir -p "$S/skills" "$S/agents" "$S/standards" "$S/templates/docs" "$S/sdd" "$S/hooks" "$S/scripts"
cp -r "$PLUGIN_DIR/skills/." "$S/skills/"
cp -r "$PLUGIN_DIR/agents/." "$S/agents/"
cp -r "$PLUGIN_DIR/standards/." "$S/standards/"
cp -r "$PLUGIN_DIR/scripts/." "$S/scripts/"
cp -r "$PLUGIN_DIR/templates/." "$S/templates/"
cp "$PLUGIN_DIR/config/"*.json "$S/sdd/"
cp "$PLUGIN_DIR/hooks/remote-session-start.sh" "$S/hooks/"
cp "$HARNESS_DIR/scripts/sync_mcp.py" "$S/sdd/"

# 1b. The render plugin is opt-in: most projects have nothing to look at.
if [ "$WITH_RENDER" = true ]; then
  cp -r "$RENDER_DIR/skills/." "$S/skills/"
  cp -r "$RENDER_DIR/standards/." "$S/standards/"
fi

# 1b2. Flat skills carry their plugin prefix: <skill> -> <plugin>-<skill> (unless
#      it already starts with it). Rename the staged dirs, set the frontmatter
#      name:, and record the map in $S/../renames.json (never installed).
python3 - "$S" "$STAGE/renames.json" "$WITH_RENDER" "$PLUGIN_DIR/skills" "$RENDER_DIR/skills" <<'PYEOF'
import json, os, re, sys
root, out, with_render, sdd_src, render_src = sys.argv[1:6]
plugins = [('sdd', sdd_src)] + ([('render', render_src)] if with_render == 'true' else [])
renames = {}
for plugin, src in plugins:
    for skill in sorted(os.listdir(src)):
        if not os.path.isdir(os.path.join(src, skill)):
            continue
        flat = skill if skill.startswith(plugin + '-') else plugin + '-' + skill
        if flat == skill:
            continue
        renames[skill] = flat
        old = os.path.join(root, 'skills', skill)
        os.rename(old, os.path.join(root, 'skills', flat))
        md = os.path.join(root, 'skills', flat, 'SKILL.md')
        if os.path.isfile(md):
            with open(md, encoding='utf-8', newline='') as fh:
                text = fh.read()
            text = re.sub(r'(?m)\A(---\r?\n(?:(?!---).*\r?\n)*?)name:[ \t]*[^\r\n]*', lambda m: m.group(1) + 'name: ' + flat, text, count=1)
            with open(md, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text)
with open(out, 'w') as fh:
    json.dump(renames, fh, indent=2, sort_keys=True)
    fh.write('\n')
PYEOF

# 1c. Rewrite the staged markdown for a flat install. Done in Python for
#     portability — BSD/macOS `sed -i` is incompatible with GNU.
#     - ${CLAUDE_PLUGIN_ROOT} -> repo-relative .claude/ paths. Order matters: the
#       /config special case must run before the generic rule. A plugin-root
#       line that becomes a copy of a line already in the same fenced block (a
#       list naming both .claude/skills/ and the plugin's skills/) is dropped.
#     - Skill paths .claude/skills/<skill>/ -> .claude/skills/<flat>/.
#     - Invocations /<skill>, $<skill>, /sdd:<skill>, /render:<skill> ->
#       /<flat>, $<flat>: flat-installed skills carry no namespace but a prefix.
#       A note that names the namespaced form on purpose ("or `/sdd:x` when
#       installed as a plugin") is left as is.
python3 - "$S" "$STAGE/renames.json" <<'PYEOF'
import json, os, re, sys
root = sys.argv[1]
with open(sys.argv[2]) as fh:
    RENAMES = json.load(fh)
_skills = sorted(set(RENAMES) | set(RENAMES.values()), key=len, reverse=True)
_alt = '|'.join(re.escape(n) for n in _skills)
INVOKE = re.compile(r"(?<![^\s`(\['\"])([/$])(?:(?:sdd|render):)?(" + _alt + r")(?![\w/-]|\.\w)")
PLACEHOLDER = re.compile(r"(?<![^\s`(\['\"])([/$])(sdd|render):(?=<)")
PATH = re.compile(r'\.claude/skills/(' + _alt + r')/')
PLUGIN_NOTE = '` when installed as a plugin'

def invoke(m, text):
    if m.group(0)[1:].startswith(('sdd:', 'render:')) and text.startswith(PLUGIN_NOTE, m.end()):
        return m.group(0)
    return m.group(1) + RENAMES.get(m.group(2), m.group(2))

def rewrite(text):
    out, block, in_fence = [], set(), False
    for line in text.split('\n'):
        if 'pre-0.20 marker' in line:  # names the old unprefixed path on purpose
            out.append(line)
            continue
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
        new = PATH.sub(lambda m: '.claude/skills/' + RENAMES.get(m.group(1), m.group(1)) + '/', new)
        new = INVOKE.sub(lambda m: invoke(m, new), new)
        new = PLACEHOLDER.sub(lambda m: m.group(1) + m.group(2) + '-', new)
        out.append(new)
    return '\n'.join(out)

targets = []
for sub in ('skills', 'agents', 'standards'):
    for dirpath, _dirs, files in os.walk(os.path.join(root, sub)):
        targets += [os.path.join(dirpath, n) for n in files if n.endswith('.md')]
targets.append(os.path.join(root, 'templates', 'agent-routing.md'))
# Evaluation queries invoke skills too: only the invocation rule applies there.
json_targets = []
for dirpath, _dirs, files in os.walk(os.path.join(root, 'skills')):
    if os.path.basename(dirpath) == 'evaluations':
        json_targets += [os.path.join(dirpath, n) for n in files if n.endswith('.json')]
for path in json_targets:
    with open(path, encoding='utf-8', newline='') as fh:
        text = fh.read()
    new = '\n'.join(INVOKE.sub(lambda m, ln=ln: invoke(m, ln), ln) for ln in text.split('\n'))
    if new != text:
        json.loads(new)
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(new)
for path in targets:
    if not os.path.isfile(path):
        continue
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
python3 - "$S" "$CLAUDE_DIR" "$OVERWRITE_LOCAL" "$STAGE/renames.json" <<'PYEOF'
import hashlib, json, os, re, shutil, sys
stage, dest, overwrite_local = sys.argv[1], sys.argv[2], sys.argv[3] == 'true'
with open(sys.argv[4]) as fh:
    RENAMES = json.load(fh)
manifest_path = os.path.join(dest, 'sdd', '.harness-manifest')
upstream_dir = os.path.join(dest, 'sdd', 'upstream')

def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()

old = None
if os.path.exists(manifest_path):
    with open(manifest_path) as fh:
        old = json.load(fh).get('files', {})
NAME_LINE = re.compile(r'\A(---\r?\n(?:(?!---).*\r?\n)*?)name:[ \t]*[^\r\n]*')

def prune(path, stop):
    parent = os.path.dirname(path)
    while parent != stop and parent.startswith(stop) and os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
        parent = os.path.dirname(parent)

def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)

# Migrate an unprefixed install: skills/<skill>/<rest> -> skills/<flat>/<rest>.
# A legacy dir that is a symlink is never moved or followed.
def legacy(skill):
    return not os.path.islink(os.path.join(dest, 'skills', skill))

skills_dir = os.path.join(dest, 'skills')
if old is not None and RENAMES:
    renamed = []
    for key in sorted(old):
        parts = key.split('/')
        if len(parts) < 3 or parts[0] != 'skills' or parts[1] not in RENAMES or not legacy(parts[1]):
            continue
        skill, flat = parts[1], RENAMES[parts[1]]
        newkey = '/'.join(['skills', flat] + parts[2:])
        src, dst = os.path.join(dest, key), os.path.join(dest, newkey)
        if os.path.isfile(src) and not os.path.lexists(dst):
            edited = sha(src) != old[key]
            move(src, dst)
            old[newkey] = old.pop(key)
            if edited and len(parts) == 3 and parts[2] == 'SKILL.md':
                with open(dst, encoding='utf-8', newline='') as fh:
                    text = fh.read()
                text = NAME_LINE.sub(lambda m: m.group(1) + 'name: ' + flat, text, count=1)
                with open(dst, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(text)
            prune(src, skills_dir)
            if skill not in renamed:
                renamed.append(skill)
        elif not os.path.lexists(src) and os.path.isfile(dst) and newkey not in old:
            old[newkey] = old.pop(key)
    for skill in RENAMES:
        up = os.path.join(upstream_dir, 'skills', skill)
        if os.path.islink(up) or not os.path.isdir(up):
            continue
        for dirpath, _dirs, files in os.walk(up):
            for name in files:
                src = os.path.join(dirpath, name)
                dst = os.path.join(upstream_dir, 'skills', RENAMES[skill], os.path.relpath(src, up))
                if not os.path.lexists(dst):
                    move(src, dst)
        for dirpath, _dirs, _files in os.walk(up, topdown=False):
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
    for skill in renamed:
        print(f'  Renamed skills/{skill}/ -> skills/{RENAMES[skill]}/')

# Preserve unresolved incoming copies across reruns. The manifest advances to
# the incoming baseline, so deleting this directory can lose the only conflict copy.

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
        incoming = os.path.join(upstream_dir, rel)
        if os.path.isfile(incoming):
            os.remove(incoming)

for rel, digest in (old or {}).items():
    dst = os.path.join(dest, rel)
    if rel in new or not os.path.exists(dst):
        continue
    if rel.startswith('skills/') and not legacy(rel.split('/')[1]):
        continue  # a symlinked skill dir is never followed
    if sha(dst) != digest and not overwrite_local:
        new[rel] = digest  # Retain retired edits for a later explicit overwrite.
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
for skill in sorted(RENAMES):
    if os.path.lexists(os.path.join(dest, 'skills', skill)):
        reason = 'no .harness-manifest' if old is None else 'holds files the installer did not move'
        print(f'Warning: legacy skill directory .claude/skills/{skill}/ left in place ({reason})', file=sys.stderr)
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
def is_sdd_plugin_enabled(candidate):
    enabled_plugins = candidate.get('enabledPlugins')
    return isinstance(enabled_plugins, dict) and any(
        name.startswith('sdd@') and enabled for name, enabled in enabled_plugins.items())
# --local writes settings.local.json; the plugin may still be enabled in the shared file.
other = os.path.join(os.path.dirname(path), 'settings.json')
other_settings = {}
if other != path and os.path.exists(other):
    with open(other) as fh:
        other_settings = json.load(fh)
if is_sdd_plugin_enabled(settings) or is_sdd_plugin_enabled(other_settings):
    print('Warning: the sdd plugin is still enabled. After reviewing the flat snapshot, disable that pipeline plugin registration to avoid loading duplicate skills. Settings were preserved.', file=sys.stderr)
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
before = open(path).read() if os.path.exists(path) else None
after = json.dumps(settings, indent=2) + '\n'
if before != after:
    with open(path, 'w') as fh:
        fh.write(after)
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
    echo "  Warning: foreign .agents/skills symlink left untouched; expose installed skills there manually." >&2
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

# 4b. Codex uses the canonical Markdown roles; no copied agent definitions.
# MCP configuration is the only generated Codex block.
if [ "$WANT_CODEX" = true ]; then
  python3 "$CLAUDE_DIR/sdd/sync_mcp.py" --target "$TARGET"
  if [ -d "$TARGET/.codex/agents" ] && grep -rl 'Generated by agent-framework scripts/codex_adapt.py' "$TARGET/.codex/agents" >/dev/null 2>&1; then
    echo "Warning: legacy generated Codex agents remain untouched. Review and retire them manually; pipeline dispatchers now read the canonical Markdown roles." >&2
  fi
fi

# Existing project rules stay authoritative. Seed routing only for a fresh project,
# and never for a --local trial, which must leave nothing to commit.
if [ "$LOCAL" = false ] && [ ! -e "$TARGET/AGENTS.md" ] && [ ! -L "$TARGET/AGENTS.md" ]; then
  cp "$CLAUDE_DIR/templates/agent-routing.md" "$TARGET/AGENTS.md"
fi

# 4c. --local: keep every installed path out of git. info/exclude lives in the
#     common git dir, so linked worktrees share it. Re-runs add no duplicates.
if [ "$LOCAL" = true ]; then
  python3 - "$EXCLUDE_FILE" "${LOCAL_PATHS[@]}" <<'PYEOF'
import os, sys
path, wanted = sys.argv[1], ['/' + p for p in sys.argv[2:]]
header = '# sdd harness --local install (personal trial, never committed)'
lines = open(path).read().splitlines() if os.path.exists(path) else []
missing = [p for p in wanted if p not in lines]
if missing:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a') as fh:
        if lines and lines[-1].strip():
            fh.write('\n')
        if header not in lines:
            fh.write(header + '\n')
        fh.write('\n'.join(missing) + '\n')
print(f'  Excluded the installed paths from git in {path}')
PYEOF
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
if [ "$LOCAL" = true ]; then
  echo "  Nothing to commit: this --local install is excluded from git."
  echo "  To share it with a linked worktree that has no .claude of its own:"
  echo "    ln -s \"$(realpath "$TARGET")/.claude\" <worktree>/.claude"
else
  echo "  cd \"$(realpath "$TARGET")\""
  echo "  git add AGENTS.md .claude/ $([ "$WANT_AGY" = true ] && echo .agents/) $([ "$WANT_CODEX" = true ] && echo .codex/)"
  echo "  git commit -m 'chore: install sdd harness (flat) v${HARNESS_VERSION}'"
fi
echo ""
if [ "$WANT_CODEX" = true ]; then
  echo "Commit .codex/ and .agents/ too. Codex loads project .codex/ config only for a trusted project."
  echo "After changing .mcp.json: python3 .claude/sdd/sync_mcp.py (or --check for drift). Requires Python 3.11+ or tomli; servers Codex cannot express are skipped with a warning."
  echo "Then open Claude Code or Codex and run /sdd-init (Codex: \$sdd-init)."
else
  echo "Then open Claude Code and run /sdd-init."
fi
echo "To update later, re-run this script from an updated harness checkout."
