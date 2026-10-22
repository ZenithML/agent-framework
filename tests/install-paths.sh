#!/usr/bin/env bash
#
# install-paths.sh — verify every route a consumer can use to install the
# framework. CI runs this on every pull request; it also runs locally and never
# touches your ~/.claude (marketplace checks use a throwaway CLAUDE_CONFIG_DIR).
#
#   flat         scripts/install-skills.sh into an empty project: skills, agents,
#                hook, version stamp; a re-run is idempotent and keeps local
#                edits; --with-render adds render; --dry-run writes nothing; a project's own skills survive
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
    test "$(grep -cx '.claude/skills/\*/SKILL.md' "$p/.claude/skills/lint-harness/SKILL.md")" -eq 1
  check "manifest written"          test -s "$p/.claude/sdd/.harness-manifest"

  git -C "$p" add -A && git -C "$p" -c user.name=t -c user.email=t@t commit -qm installed
  "$install" "$p" >/dev/null 2>&1
  check "re-run is idempotent" test -z "$(git -C "$p" status --porcelain)"

  # Local edits survive a re-run; the manifest is what tells them from upstream changes.
  local ship="$p/.claude/skills/ship/SKILL.md" m="$p/.claude/sdd/.harness-manifest"
  echo "local edit" >> "$ship"
  "$install" "$p" >/dev/null 2>&1
  check "re-run keeps a local edit" grep -qx "local edit" "$ship"
  check "no upstream copy when upstream is unchanged" test ! -e "$p/.claude/sdd/upstream"
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d['files']['skills/ship/SKILL.md']='0'*64; json.dump(d,open(sys.argv[1],'w'))" "$m"
  "$install" "$p" >/dev/null 2>&1
  check "edited + upstream-changed: local kept" grep -qx "local edit" "$ship"
  check "edited + upstream-changed: upstream copy saved" test -f "$p/.claude/sdd/upstream/skills/ship/SKILL.md"
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

  local r; r="$(new_project render)"
  "$install" --with-render "$r" >/dev/null 2>&1
  check "--with-render adds render skills" test -f "$r/.claude/skills/frames/SKILL.md"

  local d; d="$(new_project dry)"
  "$install" --dry-run --harness codex "$d" >/dev/null 2>&1
  check "--dry-run writes nothing" bash -c "test ! -e '$d/.claude' && test ! -e '$d/.codex'"

  # Codex: skills via .agents/skills, agents as TOML, .mcp.json mirrored into config.toml.
  local c; c="$(new_project codex)"
  printf '%s\n' '{"mcpServers":{"gh":{"type":"http","url":"https://x.test/mcp","headers":{"Authorization":"Bearer ${GH_TOKEN}"}},"pw":{"command":"npx","args":["pw"],"env":{"A":"b"}}}}' > "$c/.mcp.json"
  printf '[features]\nfoo = true\n' > "$c/.codex-seed"; mkdir -p "$c/.codex"; mv "$c/.codex-seed" "$c/.codex/config.toml"
  "$install" --harness claude,codex "$c" >/dev/null 2>&1
  check "codex: $SDD_AGENTS agent TOMLs" test "$(ls "$c/.codex/agents" | wc -l)" -eq "$SDD_AGENTS"
  check "codex: agent TOML parses and names the agent" \
    python3 -c "import tomllib,sys; d=tomllib.load(open('$c/.codex/agents/critic.toml','rb')); sys.exit(d['name']!='critic' or d['sandbox_mode']!='read-only' or not d['developer_instructions'])"
  check "codex: .agents/skills reaches the skills" test -f "$c/.agents/skills/ship/SKILL.md"
  check "codex: config.toml parses, keeps existing keys, mirrors .mcp.json" \
    python3 -c "import tomllib,sys; d=tomllib.load(open('$c/.codex/config.toml','rb')); m=d['mcp_servers']; sys.exit(not(d['features']['foo'] and m['gh']['bearer_token_env_var']=='GH_TOKEN' and m['pw']['command']=='npx'))"
  git -C "$c" add -A && git -C "$c" -c user.name=t -c user.email=t@t commit -qm installed
  "$install" --harness claude,codex "$c" >/dev/null 2>&1
  check "codex: re-run is idempotent" test -z "$(git -C "$c" status --porcelain)"
  rm "$c/.mcp.json"; "$install" --harness codex "$c" >/dev/null 2>&1
  check "codex: dropping .mcp.json removes the generated block" bash -c "! grep -q mcp_servers '$c/.codex/config.toml' && grep -q foo '$c/.codex/config.toml'"
  # Servers Codex cannot take as-is must not abort the install: serverUrl is read as url,
  # headersHelper and shapeless entries only warn.
  local u; u="$(new_project codex-odd)"
  printf '%s\n' '{"mcpServers":{"hosted":{"serverUrl":"https://s.test/mcp"},"dyn":{"type":"http","url":"https://d.test/mcp","headersHelper":"echo {}"},"broken":{"type":"stdio"}}}' > "$u/.mcp.json"
  check "codex: odd .mcp.json entries do not abort the install" "$install" --harness claude,codex "$u"
  check "codex: serverUrl becomes url, shapeless entry skipped" \
    python3 -c "import tomllib,sys; m=tomllib.load(open('$u/.codex/config.toml','rb'))['mcp_servers']; sys.exit(not(m['hosted']['url']=='https://s.test/mcp' and m['dyn']['url']=='https://d.test/mcp' and 'broken' not in m))"
  local n; n="$(new_project no-codex)"; "$install" "$n" >/dev/null 2>&1
  check "default install writes no .codex/" test ! -e "$n/.codex"
  check "unknown harness is rejected" bash -c "! '$install' --harness bogus '$n'"

  local o; o="$(new_project own)"
  mkdir -p "$o/.claude/skills/my-own-skill" && echo "own" > "$o/.claude/skills/my-own-skill/SKILL.md"
  "$install" "$o" >/dev/null 2>&1
  check "refuses a foreign .claude/ without --force" test ! -f "$o/.claude/skills/ship/SKILL.md"
  "$install" --force "$o" >/dev/null 2>&1
  check "--force installs alongside the project's own skills" \
    bash -c "test -f '$o/.claude/skills/ship/SKILL.md' && grep -qx own '$o/.claude/skills/my-own-skill/SKILL.md'"
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
