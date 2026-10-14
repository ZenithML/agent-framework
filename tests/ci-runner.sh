#!/usr/bin/env bash
#
# ci-runner.sh — tests for plugins/ci-runner without touching GitHub or the machine.
#
# A fake `gh` on PATH records every call and answers the few queries ci-runner
# makes, so these run anywhere, including CI. Pass a bash binary to run the
# command under it (e.g. /bin/bash on macOS for bash 3.2):
#   tests/ci-runner.sh [bash]

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASH_BIN="${1:-bash}"
CLI="$ROOT/plugins/ci-runner/bin/ci-runner"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILS=0

pass() { echo "  ok    $1"; }
fail() { echo "  FAIL  $1"; FAILS=$((FAILS + 1)); }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$name"; else fail "$name"; fi; }

mkdir -p "$WORK/bin" "$WORK/home"
cat > "$WORK/bin/gh" <<'GH'
#!/bin/sh
echo "gh $*" >> "$GH_LOG"
case "$*" in
  "auth status") exit 0 ;;
  "repo view"*) echo "acme/widget" ;;
  "api repos/actions/runner/releases/latest"*) echo "v2.999.0" ;;
  "variable list"*) printf 'CI_RUNNER_AUTO\ttrue\t2026-01-01\n' ;;
  "secret list"*) printf 'RUNNER_STATUS_PAT\t2026-01-01\n' ;;
esac
exit 0
GH
chmod +x "$WORK/bin/gh"
# A fake `id` so the result does not depend on who runs the tests (CI is not root, containers often are).
cat > "$WORK/bin/id" <<'ID'
#!/bin/sh
case "$1" in
  -u) echo "${FAKE_UID:-1000}" ;;
  -un) echo "${FAKE_USER:-tester}" ;;
  *) [ "$1" = "${FAKE_USER:-tester}" ] || [ "$1" = ci-runner ] ;;
esac
ID
chmod +x "$WORK/bin/id"
export PATH="$WORK/bin:$PATH" HOME="$WORK/home" GH_LOG="$WORK/gh.log"
ci() { : > "$GH_LOG"; "$BASH_BIN" "$CLI" "$@"; }
# shellcheck disable=SC2329  # called through check
logged() { grep -qF -- "$1" "$GH_LOG"; }

echo "== syntax"
check "parses under $BASH_BIN" "$BASH_BIN" -n "$CLI"
check "install.sh parses under $BASH_BIN" "$BASH_BIN" -n "$ROOT/plugins/ci-runner/install.sh"
check "version" sh -c "'$BASH_BIN' '$CLI' version | grep -q '^ci-runner '"

echo "== options"
check "unknown command fails" sh -c "! '$BASH_BIN' '$CLI' bogus"
check "--count 0 is refused" sh -c "! '$BASH_BIN' '$CLI' install --count 0 --dry-run"
check "a label with spaces is refused" sh -c "! '$BASH_BIN' '$CLI' on --label 'a b'"
check "--repo and --org together are refused" sh -c "! '$BASH_BIN' '$CLI' status --repo a/b --org a"
check "--repo without a slash is refused" sh -c "! '$BASH_BIN' '$CLI' on --repo widget"
check "on refuses --org" sh -c "! '$BASH_BIN' '$CLI' on --org acme"

echo "== install --dry-run"
out="$(ci install --dry-run --repo acme/widget --count 2 2>&1)"
check "names both instances" sh -c "echo \"\$0\" | grep -q 'widget-2' && echo \"\$0\" | grep -q '/actions-runner/widget '" "$out"
check "registers against the repo URL" sh -c "echo \"\$0\" | grep -q 'https://github.com/acme/widget'" "$out"
check "warns about the current account" sh -c "echo \"\$0\" | grep -q 'dedicated account'" "$out"
check "writes nothing" test ! -e "$HOME/actions-runner"
check "asks for no registration token" sh -c "! grep -q registration-token '$GH_LOG'"
out="$(ci install --dry-run --org acme 2>&1)"
check "--org registers on the org URL" sh -c "echo \"\$0\" | grep -q 'https://github.com/acme ' && echo \"\$0\" | grep -q 'acme-org'" "$out"
check "refuses to run jobs as root" sh -c "! FAKE_UID=0 FAKE_USER=root '$BASH_BIN' '$CLI' install --dry-run --repo acme/widget --yes"
check "--run-as is accepted as root" sh -c "FAKE_UID=0 FAKE_USER=root '$BASH_BIN' '$CLI' install --dry-run --repo acme/widget --run-as ci-runner --dir '$WORK/runas' | grep -q 'svc.sh install'"
check "without a terminal, own account needs --yes" sh -c "! '$BASH_BIN' '$CLI' install --repo acme/widget </dev/null"

echo "== switch"
ci on --repo acme/widget >/dev/null
check "on sets CI_RUNNER_LABEL" logged "variable set CI_RUNNER_LABEL --repo acme/widget --body self-hosted"
check "on clears CI_RUNNER_AUTO" logged "variable delete CI_RUNNER_AUTO --repo acme/widget"
ci auto --label gpu --repo acme/widget >/dev/null
check "auto sets CI_RUNNER_AUTO" logged "variable set CI_RUNNER_AUTO --repo acme/widget --body true"
check "auto with --label sets the label" logged "variable set CI_RUNNER_LABEL --repo acme/widget --body gpu"
ci off >/dev/null
check "off uses the current repo" logged "repo view"
check "off deletes both variables" sh -c "grep -qF 'variable delete CI_RUNNER_LABEL --repo acme/widget' '$GH_LOG' && grep -qF 'variable delete CI_RUNNER_AUTO --repo acme/widget' '$GH_LOG'"

echo "== status / uninstall"
mkdir -p "$HOME/actions-runner/widget" "$HOME/actions-runner/widget-2" "$HOME/actions-runner/widget-tools"
touch "$HOME/actions-runner/widget/config.sh" "$HOME/actions-runner/widget-2/config.sh" "$HOME/actions-runner/widget-tools/config.sh"
chmod +x "$HOME"/actions-runner/*/config.sh
out="$(ci status --repo acme/widget 2>&1)"
check "status lists numbered instances only" sh -c "echo \"\$0\" | grep -q 'widget-2' && ! echo \"\$0\" | grep -q 'widget-tools'" "$out"
check "status shows the switch" sh -c "echo \"\$0\" | grep -q CI_RUNNER_AUTO" "$out"
out="$(ci uninstall --dry-run --repo acme/widget 2>&1)"
check "uninstall --dry-run keeps the directories" test -d "$HOME/actions-runner/widget-2"
check "uninstall leaves another repo's runner alone" sh -c "! echo \"\$0\" | grep -q 'widget-tools'" "$out"

echo "== workflow"
mkdir -p "$WORK/repo" && cd "$WORK/repo" || exit 1
check "writes select-runner.yml" sh -c "'$BASH_BIN' '$CLI' workflow && cmp -s '$ROOT/plugins/ci-runner/templates/select-runner.yml' .github/workflows/select-runner.yml"
check "re-running is a no-op" "$BASH_BIN" "$CLI" workflow
echo "# local" >> .github/workflows/select-runner.yml
check "refuses to overwrite local edits" sh -c "! '$BASH_BIN' '$CLI' workflow"
check "--force overwrites" "$BASH_BIN" "$CLI" workflow --force

echo "== install.sh"
check "links the command" sh -c "'$BASH_BIN' '$ROOT/plugins/ci-runner/install.sh' --bin-dir '$WORK/linkbin' && test -L '$WORK/linkbin/ci-runner' && '$WORK/linkbin/ci-runner' version"
check "--uninstall removes the link" sh -c "'$BASH_BIN' '$ROOT/plugins/ci-runner/install.sh' --bin-dir '$WORK/linkbin' --uninstall && test ! -e '$WORK/linkbin/ci-runner'"

echo
if [ "$FAILS" -eq 0 ]; then echo "All ci-runner checks passed."; else echo "$FAILS check(s) failed."; fi
exit $((FAILS > 0))
