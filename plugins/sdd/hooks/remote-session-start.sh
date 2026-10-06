#!/bin/bash
set -euo pipefail

# SDD plugin SessionStart hook.
# Only runs in remote (Claude Code on the web) environments; a no-op locally.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "SDD SessionStart hook: setting up environment..."

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$PROJECT_DIR"

CONFIG="$PROJECT_DIR/.claude/sdd/config.json"

# Resolve install + test commands. Order of precedence:
#   1. .claude/sdd/config.json (commands.install / commands.test)
#   2. auto-detect from manifest (package.json → npm, pyproject.toml → python)
#   3. skip with a warning
read_cfg() {
  # $1 = dotted key e.g. commands.install
  node -e "try{const c=require('$CONFIG');const v='$1'.split('.').reduce((o,k)=>o&&o[k],c);if(v)console.log(v)}catch(e){}" 2>/dev/null || true
}

INSTALL_CMD=""
TEST_CMD=""
if [ -f "$CONFIG" ]; then
  INSTALL_CMD="$(read_cfg commands.install)"
  TEST_CMD="$(read_cfg commands.test)"
fi

if [ -z "$INSTALL_CMD" ] || [ -z "$TEST_CMD" ]; then
  if [ -f "$PROJECT_DIR/package.json" ]; then
    INSTALL_CMD="${INSTALL_CMD:-npm install}"
    TEST_CMD="${TEST_CMD:-npm test}"
  elif [ -f "$PROJECT_DIR/pyproject.toml" ] || [ -f "$PROJECT_DIR/setup.py" ]; then
    INSTALL_CMD="${INSTALL_CMD:-pip install -e .}"
    TEST_CMD="${TEST_CMD:-pytest}"
  fi
fi

if [ -n "$INSTALL_CMD" ]; then
  echo "SDD: installing dependencies → $INSTALL_CMD"
  eval "$INSTALL_CMD" || echo "Warning: install step failed — continuing." >&2
else
  echo "SDD: no install command resolved (no .claude/sdd/config.json and no recognised manifest) — skipping." >&2
fi

if [ -n "$TEST_CMD" ]; then
  echo "SDD: verifying test suite → $TEST_CMD"
  eval "$TEST_CMD" || echo "Warning: tests did not pass at session start — continuing." >&2
fi

# Install gh CLI if not present
if ! command -v gh &> /dev/null; then
  echo "Installing gh CLI from GitHub Releases..."
  if GH_VERSION=$(curl -sf https://api.github.com/repos/cli/cli/releases/latest \
      | node -e "const d=[];process.stdin.on('data',c=>d.push(c));process.stdin.on('end',()=>console.log(JSON.parse(Buffer.concat(d).toString()).tag_name.slice(1)))"); then
    TARBALL="gh_${GH_VERSION}_linux_amd64.tar.gz"
    GH_INSTALL_DIR="${HOME}/.local/bin"
    mkdir -p "$GH_INSTALL_DIR"
    if curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/${TARBALL}" \
        -o "/tmp/${TARBALL}"; then
      tar -xzf "/tmp/${TARBALL}" -C /tmp
      mv "/tmp/gh_${GH_VERSION}_linux_amd64/bin/gh" "$GH_INSTALL_DIR/gh"
      rm -rf "/tmp/${TARBALL}" "/tmp/gh_${GH_VERSION}_linux_amd64"
      export PATH="$GH_INSTALL_DIR:$PATH"
      echo "gh $(gh --version | head -1) installed to $GH_INSTALL_DIR."
    else
      echo "Warning: failed to download gh tarball — continuing without gh CLI." >&2
    fi
  else
    echo "Warning: failed to resolve gh version — continuing without gh CLI." >&2
  fi
fi

# Wire up GitHub token and repo for gh CLI.
# GH_REPO is needed because the git remote may point to a local proxy, not github.com.
if [ -n "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ] && [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  REPO=$(git -C "$PROJECT_DIR" remote get-url origin \
    | sed -e 's|^git@github\.com:||' -e 's|^https://github\.com/||' -e 's|\.git$||' -e 's|.*/git/||')
  # Remove any existing entries first to stay idempotent across restarts
  sed -i -e '/^export GH_TOKEN=/d' -e '/^export GH_REPO=/d' "$CLAUDE_ENV_FILE"
  printf 'export GH_TOKEN=%q\n' "$GITHUB_PERSONAL_ACCESS_TOKEN" >> "$CLAUDE_ENV_FILE"
  printf 'export GH_REPO=%q\n' "$REPO" >> "$CLAUDE_ENV_FILE"
fi

echo "SDD SessionStart hook: done."
