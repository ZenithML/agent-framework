#!/usr/bin/env bash
#
# install-paths.sh — verify every route a consumer can use to install the
# framework. CI runs this on every pull request; it also runs locally and never
# touches your ~/.claude (marketplace checks use a throwaway CLAUDE_CONFIG_DIR).
#
#   flat         scripts/install-skills.sh into an empty project: skills, agents,
#                hook, version stamp; a re-run is idempotent and keeps local
#                edits; --with-render adds render; --dry-run writes nothing; a project's own skills survive;
#                --local leaves nothing to commit, even from a worktree symlinked to it
#   vendor       scripts/vendor.sh: the vendored marketplace installs sdd@<key>
#                at this repo's version; --dry-run writes nothing
#   marketplace  install every plugin from this repo's marketplace into an empty
#                project and check its version
#
# Usage: tests/install-paths.sh [flat|vendor|marketplace ...]   (default: all)
# Needs git and python3; "vendor" and "marketplace" also need the claude CLI.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKETPLACE="$ROOT/.claude-plugin/marketplace.json"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

FAILS=0
pass() { echo "  ok    $*"; }
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$msg"; else fail "$msg"; fi; }

mp() { python3 -c "import json,sys; m=json.load(open('$MARKETPLACE')); $1"; }
MP_NAME="$(mp 'print(m["name"])')"
SDD_VERSION="$(python3 -c "import json;print(json.load(open('$ROOT/plugins/sdd/.claude-plugin/plugin.json'))['version'])")"
SDD_SKILLS="$(find "$ROOT/plugins/sdd/skills" -name SKILL.md | wc -l)"
SDD_AGENTS="$(ls "$ROOT/plugins/sdd/agents" | wc -l)"

new_project() { local d="$WORK/$1"; mkdir -p "$d"; git -C "$d" init -q; echo "$d"; }

isolated_claude() {
  command -v claude >/dev/null 2>&1 || { fail "claude CLI on PATH"; return 1; }
  export CLAUDE_CONFIG_DIR="$WORK/claude-config-$1"; mkdir -p "$CLAUDE_CONFIG_DIR"
}


# Simulate a pre-0.20 (unprefixed) install: rename each flat skill dir back to its
# source name, restore its SKILL.md name:, and rename the manifest keys (rehashing
# SKILL.md so it counts as unedited). Robust in CI: needs no old tag.
downgrade() {
  python3 - "$1/.claude" "$ROOT/plugins" <<'PY'
import hashlib, json, os, re, sys
claude, plugins = sys.argv[1:3]
mf = os.path.join(claude, 'sdd', '.harness-manifest')
data = json.load(open(mf))
back = {}
for plug in ('sdd', 'render'):
    for s in os.listdir(os.path.join(plugins, plug, 'skills')):
        flat = s if s.startswith(plug + '-') else plug + '-' + s
        if flat != s:
            back[flat] = s
files = {}
for key, h in data['files'].items():
    parts = key.split('/')
    if parts[0] == 'skills' and parts[1] in back:
        old = back[parts[1]]
        newkey = '/'.join(['skills', old] + parts[2:])
        src, dst = os.path.join(claude, key), os.path.join(claude, newkey)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
            if len(parts) == 3 and parts[2] == 'SKILL.md':
                t = open(dst, newline='').read()
                t = re.sub(r'(?m)^name: .*$', 'name: ' + old, t, count=1)
                open(dst, 'w', newline='').write(t)
                h = hashlib.sha256(t.encode()).hexdigest()
        key = newkey
    files[key] = h
for flat in back:
    d = os.path.join(claude, 'skills', flat)
    if os.path.isdir(d):
        os.rmdir(d) if not os.listdir(d) else None
data['files'] = files
json.dump(data, open(mf, 'w'), indent=2)
PY
  find "$1/.claude/skills" -mindepth 1 -type d -empty -delete 2>/dev/null
}

# ── flat ─────────────────────────────────────────────────────────────────────
test_flat() {
  echo "== flat"
  local install="$ROOT/scripts/install-skills.sh" p
  p="$(new_project flat)"
  if ! "$install" "$p" >"$WORK/flat.log" 2>&1; then
    fail "install-skills.sh exits 0"; sed 's/^/        /' "$WORK/flat.log"; return
  fi
  pass "install-skills.sh exits 0"
  check "$SDD_SKILLS sdd skills"    test "$(find "$p/.claude/skills" -name SKILL.md | wc -l)" -eq "$SDD_SKILLS"
  check "$SDD_AGENTS agents"        test "$(ls "$p/.claude/agents" | wc -l)" -eq "$SDD_AGENTS"
  check "hook script copied"        test -f "$p/.claude/hooks/remote-session-start.sh"
  check "hook declared once"        test "$(grep -c remote-session-start "$p/.claude/settings.json")" -eq 1
  check ".harness-version = $SDD_VERSION" grep -qx "$SDD_VERSION" "$p/.claude/sdd/.harness-version"
  check "no plugin-root paths left" bash -c "! grep -rq 'CLAUDE_PLUGIN_ROOT' '$p/.claude/skills' '$p/.claude/agents'"
  check "no /sdd: skill names left" bash -c "! grep -rE '/sdd:[a-z<]' '$p/.claude' | grep -v 'when installed as a plugin'"
  check "plugin-root rewrite adds no duplicate lines" \
    test "$(grep -cx '.claude/skills/\*/SKILL.md' "$p/.claude/skills/sdd-lint-harness/SKILL.md")" -eq 1
  check "manifest written"          test -s "$p/.claude/sdd/.harness-manifest"

  # Flat names: every skill carries its plugin prefix, and text follows.
  local sk="$p/.claude/skills"
  check "sdd-ship installed with name: sdd-ship" grep -qx 'name: sdd-ship' "$sk/sdd-ship/SKILL.md"
  check "no unprefixed ship/ dir" test ! -e "$sk/ship"
  check "every skill dir starts sdd-" bash -c "! ls '$sk' | grep -v '^sdd-'"
  check "no double prefix: sdd-init keeps its name" \
    bash -c "grep -qx 'name: sdd-init' '$sk/sdd-init/SKILL.md' && ! ls '$sk' | grep -q '^sdd-sdd-'"
  check "no source-form skill invocations left in installed markdown" python3 - "$ROOT/plugins/sdd/skills" "$p/.claude" <<'PY'
import os, re, sys
src, root = sys.argv[1:3]
names = sorted((n for d in (src, os.path.join(os.path.dirname(os.path.dirname(src)), 'render', 'skills')) for n in os.listdir(d)
                if not n.startswith(('sdd-', 'render-'))), key=len, reverse=True)
rx = re.compile(r"(?<![^\s`(\['\"])([/$])(?:(?:sdd|render):)?(" + '|'.join(map(re.escape, names)) + r")(?![\w/-]|\.\w)")
bad = []
for base in ('skills', 'agents', 'standards', 'templates/agent-routing.md'):
    path = os.path.join(root, base)
    files = [path] if path.endswith('.md') else [os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs if f.endswith('.md')]
    for f in files:
        text = open(f, encoding='utf-8').read()
        for m in rx.finditer(text):
            if text[m.end():].startswith('` when installed as a plugin'):
                continue
            bad.append((f, m.group(0)))
for b in bad[:10]:
    print(b)
sys.exit(1 if bad else 0)
PY
  check "longest-first: /sdd-qa-explore and /sdd-review-diff intact, no mangling" \
    bash -c "grep -rqF '/sdd-qa-explore' '$p/.claude' && grep -rqF '/sdd-review-diff' '$p/.claude' && ! grep -rqE 'sdd-sdd-|/sdd-qa-explore-explore|/sdd-qa -explore|/sdd-review-pr-diff' '$p/.claude'"
  # The plugin-note exception: a renamed skill followed by the note stays verbatim.
  local h="$WORK/harness-note" hp; hp="$(new_project note)"
  mkdir -p "$h" && cp -r "$ROOT/scripts" "$ROOT/plugins" "$h/"
  printf '\nSee `/sdd:ship` when installed as a plugin; otherwise /sdd:ship.\n' >> "$h/plugins/sdd/skills/plan/SKILL.md"
  "$h/scripts/install-skills.sh" "$hp" >/dev/null 2>&1
  check "plugin note kept verbatim for a renamed skill, plain use rewritten" \
    grep -qxF 'See `/sdd:ship` when installed as a plugin; otherwise /sdd-ship.' "$hp/.claude/skills/sdd-plan/SKILL.md"
  check "triage-pr script path prefixed" \
    bash -c "grep -q '.claude/skills/sdd-triage-pr/scripts' '$sk/sdd-triage-pr/SKILL.md' && ! grep -rq '.claude/skills/triage-pr/' '$p/.claude'"
  check "non-invocations untouched (docs/specs/<domain>/tasks.md)" grep -q 'docs/specs/<domain>/tasks.md' "$p/.claude/agents/planner.md"
  check "plugin note survives" grep -rq 'when installed as a plugin' "$sk/sdd-init/SKILL.md"
  check "seeded AGENTS.md names /sdd-ship and \$sdd-ship" \
    bash -c "grep -q '/sdd-ship' '$p/AGENTS.md' && grep -qF '\$sdd-ship' '$p/AGENTS.md' && ! grep -q '\`/ship\`' '$p/AGENTS.md'"
  check "closing hint says /sdd-init" grep -q 'run /sdd-init' "$WORK/flat.log"
  check "sdd-init names both flat-install markers" \
    bash -c "grep -q 'skills/sdd-ship/SKILL.md' '$sk/sdd-init/SKILL.md' && grep -q 'skills/ship/SKILL.md' '$sk/sdd-init/SKILL.md'"
  check "docs give /sdd-ship for flat installs" \
    bash -c "grep -q '/sdd-ship' '$ROOT/docs/installation.md' && grep -q '/sdd-ship' '$ROOT/docs/plugins.md'"
  check "plugin source keeps name: ship" bash -c "head -3 '$ROOT/plugins/sdd/skills/ship/SKILL.md' | grep -qx 'name: ship'"
  check "sdd manifests say 0.20.0" \
    bash -c "grep -q '\"version\": \"0.20.0\"' '$ROOT/plugins/sdd/.claude-plugin/plugin.json' && python3 -c \"import json,sys; m=json.load(open('$MARKETPLACE')); sys.exit(not(m['version']=='0.20.0' and {x['name']:x['version'] for x in m['plugins']}['sdd']=='0.20.0'))\""
  check "render manifests say 0.3.0" \
    bash -c "grep -q '\"version\": \"0.3.0\"' '$ROOT/plugins/render/.claude-plugin/plugin.json' && python3 -c \"import json,sys; m=json.load(open('$MARKETPLACE')); sys.exit({x['name']:x['version'] for x in m['plugins']}['render']!='0.3.0')\""

  git -C "$p" add -A && git -C "$p" -c user.name=t -c user.email=t@t commit -qm installed
  "$install" "$p" >/dev/null 2>&1
  check "re-run is idempotent" test -z "$(git -C "$p" status --porcelain)"

  # Local edits survive a re-run; the manifest is what tells them from upstream changes.
  local ship="$p/.claude/skills/sdd-ship/SKILL.md" m="$p/.claude/sdd/.harness-manifest"
  echo "local edit" >> "$ship"
  "$install" "$p" >/dev/null 2>&1
  check "re-run keeps a local edit" grep -qx "local edit" "$ship"
  check "no upstream copy when upstream is unchanged" test ! -e "$p/.claude/sdd/upstream"
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d['files']['skills/sdd-ship/SKILL.md']='0'*64; json.dump(d,open(sys.argv[1],'w'))" "$m"
  "$install" "$p" >/dev/null 2>&1
  check "edited + upstream-changed: local kept" grep -qx "local edit" "$ship"
  check "edited + upstream-changed: upstream copy saved" test -f "$p/.claude/sdd/upstream/skills/sdd-ship/SKILL.md"
  "$install" --overwrite-local "$p" >/dev/null 2>&1
  check "--overwrite-local replaces the edit" bash -c "! grep -qx 'local edit' '$ship'"

  # A file the release stops shipping is removed, unless it was edited.
  mkdir -p "$p/.claude/skills/retired" && echo "old" > "$p/.claude/skills/retired/SKILL.md"
  echo "old2" > "$p/.claude/agents/retired-agent.md"
  python3 - "$m" "$p/.claude" <<'PY'
import hashlib, json, sys
d = json.load(open(sys.argv[1]))
d['files']['skills/retired/SKILL.md'] = hashlib.sha256(b'old\n').hexdigest()
d['files']['agents/retired-agent.md'] = hashlib.sha256(b'edited-since\n').hexdigest()
json.dump(d, open(sys.argv[1], 'w'))
PY
  "$install" "$p" >/dev/null 2>&1
  check "unedited retired file removed" test ! -e "$p/.claude/skills/retired"
  check "edited retired file kept" test -f "$p/.claude/agents/retired-agent.md"

  check "gate scripts installed" test -x "$p/.claude/scripts/gate-design.py"
  check "gate-review installed" test -x "$p/.claude/scripts/gate-review.py"

  local r; r="$(new_project render)"
  "$install" --with-render "$r" >/dev/null 2>&1
  check "--with-render adds render skills" test -f "$r/.claude/skills/render-frames/SKILL.md"
  check "--with-render adds dcg skill" test -f "$r/.claude/skills/render-dcg/SKILL.md"
  check "--with-render names: render-frames, render-init, no double prefix" \
    bash -c "grep -qx 'name: render-frames' '$r/.claude/skills/render-frames/SKILL.md' && test -f '$r/.claude/skills/render-init/SKILL.md' && test ! -e '$r/.claude/skills/render-render-init' && test ! -e '$r/.claude/skills/frames'"
  check "--with-render: no source-form render invocations or paths" \
    bash -c "! grep -rnE '[/$](render:)?(frames|tune|trap|dcg)([^[:alnum:]/._-]|\$)|\.claude/skills/(frames|tune|trap|dcg)/' '$r/.claude' | grep -v 'when installed as a plugin'"
  check "--with-render: /render-frames and /render-tune referenced" \
    bash -c "grep -rqF '/render-frames' '$r/.claude/skills' && grep -rqF '/render-tune' '$r/.claude/skills'"
  check "--with-render adds dcg standard" test -f "$r/.claude/standards/digital-content-generation.md"

  local d; d="$(new_project dry)"
  "$install" --dry-run --harness codex "$d" >/dev/null 2>&1
  check "--dry-run writes nothing" bash -c "test ! -e '$d/.claude' && test ! -e '$d/.codex'"

  # Codex: shared Markdown roles, discovery link, and managed MCP configuration.
  local c; c="$(new_project codex)"
  printf '%s\n' '{"mcpServers":{"gh":{"type":"http","url":"https://x.test/mcp","headers":{"Authorization":"Bearer ${GH_TOKEN}"}},"pw":{"command":"npx","args":["pw"],"env":{"A":"b"}}}}' > "$c/.mcp.json"
  printf '[features]\nfoo = true\n' > "$c/.codex-seed"; mkdir -p "$c/.codex"; mv "$c/.codex-seed" "$c/.codex/config.toml"
  "$install" --harness claude,codex "$c" >/dev/null 2>&1
  check "codex: no generated role files" test ! -e "$c/.codex/agents"
  check "codex: .agents/skills lists sdd-ship" bash -c "ls '$c/.agents/skills/' | grep -qx sdd-ship"
  check "codex: closing hint says \$sdd-init" bash -c "'$install' --harness claude,codex '$c' 2>&1 | grep -qF '\$sdd-init'"
  check "codex: canonical critic role available" test -f "$c/.claude/agents/critic.md"
  check "codex: .agents/skills reaches the skills" test -f "$c/.agents/skills/sdd-ship/SKILL.md"
  check "codex: config.toml parses, keeps existing keys, mirrors .mcp.json" \
    python3 -c "import tomllib,sys; d=tomllib.load(open('$c/.codex/config.toml','rb')); m=d['mcp_servers']; sys.exit(not(d['features']['foo'] and m['gh']['bearer_token_env_var']=='GH_TOKEN' and m['pw']['command']=='npx'))"
  git -C "$c" add -A && git -C "$c" -c user.name=t -c user.email=t@t commit -qm installed
  "$install" --harness claude,codex "$c" >/dev/null 2>&1
  check "codex: re-run is idempotent" test -z "$(git -C "$c" status --porcelain)"
  rm "$c/.mcp.json"; "$install" --harness codex "$c" >/dev/null 2>&1
  check "codex: dropping .mcp.json removes the generated block" bash -c "! grep -q mcp_servers '$c/.codex/config.toml' && grep -q foo '$c/.codex/config.toml'"
  # Malformed MCP input fails before writing any consumer snapshot.
  local u; u="$(new_project codex-odd)"
  printf '%s\n' '{"mcpServers":{"broken":{"args":["no command"]}}}' > "$u/.mcp.json"
  check "codex: malformed MCP input fails without mutation" bash -c '
    ! "$1" --harness codex "$2" >/dev/null 2>&1 && test ! -e "$2/.claude" && test ! -e "$2/.codex"
  ' _ "$install" "$u"
  # A server Codex cannot express is skipped with a warning; the install still succeeds.
  local w; w="$(new_project codex-skip)"
  printf '%s\n' '{"mcpServers":{"dyn":{"url":"https://d.test/mcp","headersHelper":"echo {}"},"ok":{"url":"https://o.test/mcp"}}}' > "$w/.mcp.json"
  check "codex: unsupported MCP server is skipped with a warning" bash -c '
    out="$("$1" --harness codex "$2" 2>&1)" && printf "%s" "$out" | grep -q "skipped server dyn" &&
    python3 -c "import tomllib,sys; m=tomllib.load(open(sys.argv[1],\"rb\"))[\"mcp_servers\"]; sys.exit(set(m)!={\"ok\"})" "$2/.codex/config.toml"
  ' _ "$install" "$w"
  printf '%s\n' '{"mcpServers":{"hosted":{"serverUrl":"https://s.test/mcp"}}}' > "$u/.mcp.json"
  "$install" --harness codex "$u" >/dev/null 2>&1
  check "codex: installed standalone sync helper detects no drift" python3 "$u/.claude/sdd/sync_mcp.py" --target "$u" --check
  printf '%s\n' '{"mcpServers":{}}' > "$u/.mcp.json"
  python3 "$u/.claude/sdd/sync_mcp.py" --target "$u" >/dev/null 2>&1
  check "codex: standalone sync removes retired entries" test ! -e "$u/.codex/config.toml"
  local n; n="$(new_project no-codex)"; "$install" "$n" >/dev/null 2>&1
  check "default install writes no .codex/" test ! -e "$n/.codex"
  check "unknown harness is rejected" bash -c "! '$install' --harness bogus '$n'"

  # --local: a personal trial that leaves nothing to commit, shared with worktrees by a symlink.
  local l; l="$(new_project local)"
  echo "app" > "$l/README.md"
  git -C "$l" add -A && git -C "$l" -c user.name=t -c user.email=t@t commit -qm base
  local exclude="$l/.git/info/exclude"
  cp "$exclude" "$WORK/exclude.before" 2>/dev/null || : > "$WORK/exclude.before"
  "$install" --dry-run --local "$l" >/dev/null 2>&1
  check "--local --dry-run writes nothing" \
    bash -c "test ! -e '$l/.claude' && cmp -s '$exclude' '$WORK/exclude.before'"
  if "$install" --local "$l" >"$WORK/local.log" 2>&1; then pass "--local exits 0"
  else fail "--local exits 0"; sed 's/^/        /' "$WORK/local.log"; fi
  check "--local installs the skills" test -f "$l/.claude/skills/sdd-ship/SKILL.md"
  check "--local leaves a clean git status" test -z "$(git -C "$l" status --porcelain)"
  check "--local declares the hook in settings.local.json" \
    test "$(grep -c remote-session-start "$l/.claude/settings.local.json")" -eq 1
  check "--local writes no settings.json" test ! -e "$l/.claude/settings.json"
  check "--local seeds no AGENTS.md" test ! -e "$l/AGENTS.md"
  "$install" --local "$l" >/dev/null 2>&1
  check "--local re-run adds no duplicate excludes" test "$(grep -cx '/.claude/skills' "$exclude")" -eq 1
  local wt="$WORK/local-wt"
  git -C "$l" worktree add -q "$wt" -b trial
  ln -s "$l/.claude" "$wt/.claude"
  check "--local: a worktree symlinked to the install stays clean" test -z "$(git -C "$wt" status --porcelain)"
  local t; t="$(new_project local-tracked)"
  mkdir -p "$t/.claude/skills/team" && echo "team" > "$t/.claude/skills/team/SKILL.md"
  git -C "$t" add -A && git -C "$t" -c user.name=t -c user.email=t@t commit -qm base
  check "--local refuses when it would change tracked files" bash -c "! '$install' --local --force '$t'"
  check "--local refusal writes nothing" test ! -e "$t/.claude/skills/sdd-ship"

  local o; o="$(new_project own)"
  mkdir -p "$o/.claude/skills/my-own-skill" && echo "own" > "$o/.claude/skills/my-own-skill/SKILL.md"
  "$install" "$o" >/dev/null 2>&1
  check "refuses a foreign .claude/ without --force" test ! -f "$o/.claude/skills/sdd-ship/SKILL.md"
  "$install" --force "$o" >/dev/null 2>&1
  check "--force installs alongside the project's own skills" \
    bash -c "test -f '$o/.claude/skills/sdd-ship/SKILL.md' && grep -qx own '$o/.claude/skills/my-own-skill/SKILL.md'"

  # ── upgrade from an unprefixed install ──
  local u1 u1c u1e
  u1="$(new_project up-clean)"; "$install" "$u1" >/dev/null 2>&1; downgrade "$u1"
  check "simulated old install has ship/ and no sdd-ship/" bash -c "test -f '$u1/.claude/skills/ship/SKILL.md' && test ! -e '$u1/.claude/skills/sdd-ship'"
  "$install" "$u1" >"$WORK/up1.out" 2>"$WORK/up1.err"; u1c=$?
  check "story 4: upgrade exits 0" test "$u1c" -eq 0
  check "story 4: sdd-ship moved, name flat" grep -qx 'name: sdd-ship' "$u1/.claude/skills/sdd-ship/SKILL.md"
  check "story 4: no unprefixed skill dirs left" bash -c "! ls '$u1/.claude/skills' | grep -v '^sdd-'"
  check "story 4: manifest has no skills/ship/ keys" bash -c "! grep -q '\"skills/ship/' '$u1/.claude/sdd/.harness-manifest'"
  check "story 4: Renamed line printed" grep -qxF '  Renamed skills/ship/ -> skills/sdd-ship/' "$WORK/up1.out"
  check "story 4: no legacy warning" bash -c "! grep -q 'legacy skill directory' '$WORK/up1.err'"
  check "story 4: closing says /sdd-init" grep -q 'run /sdd-init' "$WORK/up1.out"
  git -C "$u1" add -A && git -C "$u1" -c user.name=t -c user.email=t@t commit -qm up
  "$install" "$u1" >"$WORK/up1b.out" 2>"$WORK/up1b.err"
  check "story 8: re-run is quiet (no Renamed, no warning, no changes)" \
    bash -c "! grep -q Renamed '$WORK/up1b.out' && ! test -s '$WORK/up1b.err' && test -z \"\$(git -C '$u1' status --porcelain)\""

  # Story 5: edited SKILL.md keeps the edit under the flat dir with the flat name.
  local u2 u2m; u2="$(new_project up-edit)"; "$install" "$u2" >/dev/null 2>&1; downgrade "$u2"
  echo "my edit" >> "$u2/.claude/skills/ship/SKILL.md"
  "$install" "$u2" >"$WORK/up2.out" 2>"$WORK/up2.err"
  check "story 5: edit kept under sdd-ship with flat name" \
    bash -c "grep -qx 'my edit' '$u2/.claude/skills/sdd-ship/SKILL.md' && grep -qx 'name: sdd-ship' '$u2/.claude/skills/sdd-ship/SKILL.md' && test ! -e '$u2/.claude/skills/ship'"
  check "story 5: upstream copy saved" test -f "$u2/.claude/sdd/upstream/skills/sdd-ship/SKILL.md"
  check "story 5: conflict block lists skills/sdd-ship/SKILL.md" grep -q 'skills/sdd-ship/SKILL.md' "$WORK/up2.err"

  # Story 5b: a pending upstream copy under the old path moves.
  local u3; u3="$(new_project up-pending)"; "$install" "$u3" >/dev/null 2>&1; downgrade "$u3"
  mkdir -p "$u3/.claude/sdd/upstream/skills/ship" && echo pending > "$u3/.claude/sdd/upstream/skills/ship/pending.md"
  "$install" "$u3" >/dev/null 2>&1
  check "story 5b: pending upstream copy moves" \
    bash -c "grep -qx pending '$u3/.claude/sdd/upstream/skills/sdd-ship/pending.md' && test ! -e '$u3/.claude/sdd/upstream/skills/ship'"

  # Existing destination: unedited old file deleted; edited one kept and warned.
  local u4; u4="$(new_project up-both)"; "$install" "$u4" >/dev/null 2>&1; downgrade "$u4"
  mkdir -p "$u4/.claude/skills/sdd-ship" && echo dest > "$u4/.claude/skills/sdd-ship/SKILL.md"
  mkdir -p "$u4/.claude/skills/sdd-plan" && echo dest > "$u4/.claude/skills/sdd-plan/SKILL.md"
  echo "edited" >> "$u4/.claude/skills/ship/SKILL.md"
  "$install" "$u4" >/dev/null 2>"$WORK/up4.err"
  check "both present: unedited old file deleted" test ! -e "$u4/.claude/skills/plan"
  check "both present: edited old file kept and dir warned" \
    bash -c "grep -qx edited '$u4/.claude/skills/ship/SKILL.md' && grep -qF 'Warning: legacy skill directory .claude/skills/ship/ left in place (holds files the installer did not move)' '$WORK/up4.err'"

  # Story 6: a user file in the old dir survives and is named.
  local u5 u5c; u5="$(new_project up-userfile)"; "$install" "$u5" >/dev/null 2>&1; downgrade "$u5"
  echo mine > "$u5/.claude/skills/ship/notes.md"
  "$install" "$u5" >/dev/null 2>"$WORK/up5.err"; u5c=$?
  check "story 6: exit 0, file survives, warning names dir" \
    bash -c "test $u5c -eq 0 && grep -qx mine '$u5/.claude/skills/ship/notes.md' && grep -qxF 'Warning: legacy skill directory .claude/skills/ship/ left in place (holds files the installer did not move)' '$WORK/up5.err' && test -f '$u5/.claude/skills/sdd-ship/SKILL.md' && test ! -e '$u5/.claude/skills/ship/SKILL.md'"

  # Story 7: no manifest -> warning, nothing moved or deleted.
  local u6 u6c; u6="$(new_project up-nomanifest)"; "$install" "$u6" >/dev/null 2>&1; downgrade "$u6"
  rm "$u6/.claude/sdd/.harness-manifest"
  "$install" "$u6" >/dev/null 2>"$WORK/up6.err"; u6c=$?
  check "story 7: no manifest exits 0 with the no-manifest warning" \
    bash -c "test $u6c -eq 0 && grep -qxF 'Warning: legacy skill directory .claude/skills/ship/ left in place (no .harness-manifest)' '$WORK/up6.err' && test -f '$u6/.claude/skills/ship/SKILL.md'"

  # Symlinked legacy dir: warned, never followed or moved.
  local u7; u7="$(new_project up-symlink)"; "$install" "$u7" >/dev/null 2>&1; downgrade "$u7"
  mv "$u7/.claude/skills/ship" "$WORK/ship-target"; ln -s "$WORK/ship-target" "$u7/.claude/skills/ship"
  "$install" "$u7" >/dev/null 2>"$WORK/up7.err"
  check "symlinked legacy dir: still a symlink, target intact, warned" \
    bash -c "test -L '$u7/.claude/skills/ship' && test -f '$WORK/ship-target/SKILL.md' && grep -qF 'legacy skill directory .claude/skills/ship/' '$WORK/up7.err'"

  # Edited SKILL.md without a name line moves byte-identical; CRLF name line keeps CRLF.
  local u8 u9; u8="$(new_project up-noname)"; "$install" "$u8" >/dev/null 2>&1; downgrade "$u8"
  printf 'no frontmatter here\nedited\n' > "$u8/.claude/skills/ship/SKILL.md"
  cp "$u8/.claude/skills/ship/SKILL.md" "$WORK/noname.expected"
  "$install" "$u8" >/dev/null 2>&1
  check "edited SKILL.md without a name line moves byte-identical" cmp -s "$WORK/noname.expected" "$u8/.claude/skills/sdd-ship/SKILL.md"
  u9="$(new_project up-crlf)"; "$install" "$u9" >/dev/null 2>&1; downgrade "$u9"
  printf -- '---\r\nname: ship\r\ndescription: x\r\n---\r\nbody\r\n' > "$u9/.claude/skills/ship/SKILL.md"
  "$install" "$u9" >/dev/null 2>&1
  check "CRLF name line replaced keeping CRLF" \
    bash -c "printf -- '---\r\nname: sdd-ship\r\ndescription: x\r\n---\r\nbody\r\n' | cmp -s - '$u9/.claude/skills/sdd-ship/SKILL.md'"

  # Interrupted upgrade: file moved by hand and edited, manifest still old.
  local u10; u10="$(new_project up-interrupted)"; "$install" "$u10" >/dev/null 2>&1; downgrade "$u10"
  mv "$u10/.claude/skills/ship/SKILL.md" "$WORK/hand.md"; rmdir "$u10/.claude/skills/ship" 2>/dev/null
  mkdir -p "$u10/.claude/skills/sdd-ship"; mv "$WORK/hand.md" "$u10/.claude/skills/sdd-ship/SKILL.md"
  echo "hand edit" >> "$u10/.claude/skills/sdd-ship/SKILL.md"
  "$install" "$u10" >/dev/null 2>&1
  check "interrupted upgrade: hand-moved edit kept, key renamed" \
    bash -c "grep -qx 'hand edit' '$u10/.claude/skills/sdd-ship/SKILL.md' && ! grep -q '\"skills/ship/SKILL.md' '$u10/.claude/sdd/.harness-manifest' && grep -q '\"skills/sdd-ship/SKILL.md' '$u10/.claude/sdd/.harness-manifest'"

  # Render upgrade with and without --with-render.
  local r1 r2; r1="$(new_project up-render)"; "$install" --with-render "$r1" >/dev/null 2>&1; downgrade "$r1"
  check "simulated old render install has frames/" test -f "$r1/.claude/skills/frames/SKILL.md"
  "$install" --with-render "$r1" >"$WORK/r1.out" 2>"$WORK/r1.err"
  check "render upgrade: frames/ gone, render-frames/ present, Renamed printed" \
    bash -c "test ! -e '$r1/.claude/skills/frames' && test -f '$r1/.claude/skills/render-frames/SKILL.md' && grep -qxF '  Renamed skills/frames/ -> skills/render-frames/' '$WORK/r1.out'"
  r2="$(new_project up-render-noflag)"; "$install" --with-render "$r2" >/dev/null 2>&1; downgrade "$r2"
  "$install" "$r2" >/dev/null 2>"$WORK/r2.err"
  check "render upgrade without --with-render retires unedited render files" \
    bash -c "test ! -e '$r2/.claude/skills/frames' && test ! -e '$r2/.claude/skills/render-frames' && test ! -e '$r2/.claude/skills/dcg' && test -f '$r2/.claude/skills/sdd-ship/SKILL.md'"
}

# ── vendor ───────────────────────────────────────────────────────────────────
test_vendor() {
  echo "== vendor"
  local p; p="$(new_project demo)"
  if ! "$ROOT/scripts/vendor.sh" "$p" >"$WORK/vendor.log" 2>&1; then
    fail "vendor.sh exits 0"; sed 's/^/        /' "$WORK/vendor.log"; return
  fi
  pass "vendor.sh exits 0"
  check "settings enable sdd@demo" grep -q '"sdd@demo"' "$p/.claude/settings.json"
  check "vendored marketplace is named demo" \
    python3 -c "import json,sys; sys.exit(json.load(open('$p/.claude/vendors/demo/.claude-plugin/marketplace.json'))['name'] != 'demo')"

  local d; d="$(new_project dry-vendor)"
  "$ROOT/scripts/vendor.sh" --dry-run "$d" >/dev/null 2>&1
  check "--dry-run writes nothing" test ! -e "$d/.claude"

  isolated_claude vendor || return
  (cd "$p" && claude plugin marketplace add ./.claude/vendors/demo >/dev/null 2>&1 \
           && claude plugin install sdd@demo --scope project >"$WORK/vendor-install.log" 2>&1) \
    && pass "install sdd@demo from the vendored marketplace" \
    || { fail "install sdd@demo from the vendored marketplace"; sed 's/^/        /' "$WORK/vendor-install.log"; return; }
  got="$(cd "$p" && claude plugin details sdd@demo 2>/dev/null | head -1)"
  [ "$got" = "sdd $SDD_VERSION" ] && pass "sdd@demo resolves to $SDD_VERSION" || fail "sdd@demo resolves to '$got'"
}

# ── marketplace ──────────────────────────────────────────────────────────────
test_marketplace() {
  echo "== marketplace"
  isolated_claude marketplace || return
  check "claude plugin validate --strict" claude plugin validate "$ROOT" --strict
  (cd "$WORK" && claude plugin marketplace add "$ROOT" >"$WORK/mp.log" 2>&1) \
    && pass "marketplace add" || { fail "marketplace add"; sed 's/^/        /' "$WORK/mp.log"; return; }

  while IFS=$'\t' read -r name version; do
    local p; p="$(new_project "mp-$name")"
    if (cd "$p" && claude plugin install "$name@$MP_NAME" --scope project >"$WORK/mp-$name.log" 2>&1); then
      pass "install $name@$MP_NAME"
      got="$(cd "$p" && claude plugin details "$name@$MP_NAME" 2>/dev/null | head -1)"
      [ "$got" = "$name $version" ] && pass "$name resolves to $version" || fail "$name resolves to '$got', expected '$name $version'"
    else
      fail "install $name@$MP_NAME"; sed 's/^/        /' "$WORK/mp-$name.log"
    fi
  done < <(mp 'print("\n".join(p["name"]+"\t"+p["version"] for p in m["plugins"]))')
}

SUITES=("$@"); [ ${#SUITES[@]} -eq 0 ] && SUITES=(flat vendor marketplace)
for s in "${SUITES[@]}"; do "test_$s"; done

echo
if [ "$FAILS" -eq 0 ]; then echo "All install paths verified."; else echo "$FAILS check(s) failed."; fi
exit $((FAILS > 0))
