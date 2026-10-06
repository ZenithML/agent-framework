#!/usr/bin/env bash
#
# install-paths.sh — verify every route a consumer can use to install the
# framework. CI runs this on every pull request; it also runs locally and never
# touches your ~/.claude (marketplace checks use a throwaway CLAUDE_CONFIG_DIR).
#
#   flat         scripts/install-skills.sh into an empty project: skills, agents,
#                hook, version stamp; a re-run is idempotent; --with-render adds
#                render; --dry-run writes nothing; a project's own skills survive
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

  git -C "$p" add -A && git -C "$p" -c user.name=t -c user.email=t@t commit -qm installed
  "$install" "$p" >/dev/null 2>&1
  check "re-run is idempotent" test -z "$(git -C "$p" status --porcelain)"

  local r; r="$(new_project render)"
  "$install" --with-render "$r" >/dev/null 2>&1
  check "--with-render adds render skills" test -f "$r/.claude/skills/frames/SKILL.md"

  local d; d="$(new_project dry)"
  "$install" --dry-run "$d" >/dev/null 2>&1
  check "--dry-run writes nothing" test ! -e "$d/.claude"

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
