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
  "variable get CI_RUNNER_AUTO"*) [ -n "${FAKE_AUTO:-}" ] && echo "$FAKE_AUTO" || exit 1 ;;
  "variable get CI_RUNNER_LABEL"*) [ -n "${FAKE_LABEL:-}" ] && echo "$FAKE_LABEL" || exit 1 ;;
  "variable get"*) exit 1 ;;
  "secret list"*) [ -n "${FAKE_NO_SECRET:-}" ] || printf 'RUNNER_STATUS_PAT\t2026-01-01\n' ;;
  "secret set"*) cat > "$GH_LOG.secret" ;;
  *"| length"*) echo "${FAKE_ONLINE:-1}" ;;
  "api repos/"*"/actions/runners"*) printf '  host-widget\tonline\tself-hosted,Linux\n' ;;
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
# shellcheck disable=SC2317,SC2329  # called through check
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
check "a missing --run-as user is refused without --create-user" sh -c "! '$BASH_BIN' '$CLI' install --dry-run --repo acme/widget --run-as ghost"
check "--run-as with shell metacharacters is refused" sh -c "! '$BASH_BIN' '$CLI' install --dry-run --repo acme/widget --run-as 'x;touch $WORK/pwned' --create-user && [ ! -e '$WORK/pwned' ]"
out="$("$BASH_BIN" "$CLI" install --dry-run --repo acme/widget --run-as ghost --create-user 2>&1)"
check "--create-user creates the missing account" sh -c "echo \"\$0\" | grep -q 'useradd --create-home --shell /bin/bash ghost'" "$out"
check "...and installs under its home" sh -c "echo \"\$0\" | grep -q '/home/ghost/actions-runner'" "$out"
out="$("$BASH_BIN" "$CLI" install --dry-run --repo acme/widget --create-user 2>&1)"
check "--create-user alone means the 'ci-runner' account" sh -c "echo \"\$0\" | grep -q 'svc.sh install' && echo \"\$0\" | grep -q ci-runner" "$out"
check "without a terminal, own account needs --yes" sh -c "! '$BASH_BIN' '$CLI' install --repo acme/widget </dev/null"

echo "== on / off"
ci on --repo acme/widget >/dev/null
check "on (token present) turns the fallback on" logged "variable set CI_RUNNER_AUTO --repo acme/widget --body true"
check "on leaves the default label unset" logged "variable delete CI_RUNNER_LABEL --repo acme/widget"
check "on stores no new secret when one exists" sh -c "! grep -q 'secret set' '$GH_LOG'"
ci on --label gpu --repo acme/widget >/dev/null
check "on --label sets the label" logged "variable set CI_RUNNER_LABEL --repo acme/widget --body gpu"
ci on --no-fallback --repo acme/widget >/dev/null
check "--no-fallback sets the label" logged "variable set CI_RUNNER_LABEL --repo acme/widget --body self-hosted"
check "--no-fallback clears the fallback" logged "variable delete CI_RUNNER_AUTO --repo acme/widget"
ci on --org-runner --repo acme/widget >/dev/null
check "--org-runner records the scope" logged "variable set CI_RUNNER_SCOPE --repo acme/widget --body org"
ci auto --repo acme/widget >/dev/null
check "auto still works as an alias of on" logged "variable set CI_RUNNER_AUTO --repo acme/widget --body true"

out="$(FAKE_NO_SECRET=1 RUNNER_STATUS_PAT=tok-123 ci on --repo acme/widget 2>&1)"
check "a token from the environment is stored as the secret" logged "secret set RUNNER_STATUS_PAT --repo acme/widget"
check "the stored token is exactly the one given" sh -c "[ \"\$(cat '$GH_LOG.secret')\" = tok-123 ]"
check "the token never appears on a command line" sh -c "! grep -q 'tok-123' '$GH_LOG'"
check "fallback is on once the token is stored" logged "variable set CI_RUNNER_AUTO --repo acme/widget --body true"
check "no secret set when it already exists" sh -c "! FAKE_NO_SECRET= RUNNER_STATUS_PAT=x '$BASH_BIN' '$CLI' on --repo acme/widget </dev/null | grep -q Stored"
out="$(FAKE_NO_SECRET=1 ci on --repo acme/widget </dev/null 2>&1)"
check "without a token, on falls back to always-self-hosted" sh -c "echo \"\$0\" | grep -q \"On, always 'self-hosted'\"" "$out"
check "...and says how to add the fallback" sh -c "echo \"\$0\" | grep -q 'RUNNER_STATUS_PAT=<token> ci-runner on'" "$out"
check "...and links where to create the token" sh -c "echo \"\$0\" | grep -q 'personal-access-tokens/new'" "$out"
out="$(FAKE_NO_SECRET=1 RUNNER_STATUS_PAT=tok-123 ci on --dry-run --repo acme/widget 2>&1)"
check "--dry-run stores no secret" sh -c "! grep -q 'secret set' '$GH_LOG'"

ci off >/dev/null
check "off uses the current repo" logged "repo view"
check "off deletes the label, fallback and scope" sh -c "grep -qF 'variable delete CI_RUNNER_LABEL --repo acme/widget' '$GH_LOG' && grep -qF 'variable delete CI_RUNNER_AUTO --repo acme/widget' '$GH_LOG' && grep -qF 'variable delete CI_RUNNER_SCOPE --repo acme/widget' '$GH_LOG'"

echo "== status / uninstall"
mkdir -p "$HOME/actions-runner/widget" "$HOME/actions-runner/widget-2" "$HOME/actions-runner/widget-tools"
touch "$HOME/actions-runner/widget/config.sh" "$HOME/actions-runner/widget-2/config.sh" "$HOME/actions-runner/widget-tools/config.sh"
chmod +x "$HOME"/actions-runner/*/config.sh
out="$(ci status --repo acme/widget 2>&1)"
check "status lists numbered instances only" sh -c "echo \"\$0\" | grep -q 'widget-2' && ! echo \"\$0\" | grep -q 'widget-tools'" "$out"
check "status says OFF when no variable is set" sh -c "echo \"\$0\" | grep -q 'Switch:  OFF'" "$out"
out="$(FAKE_AUTO=true ci status --repo acme/widget 2>&1)"
check "status says ON with fallback" sh -c "echo \"\$0\" | grep -q 'ON, with fallback'" "$out"
out="$(FAKE_AUTO=true FAKE_NO_SECRET=1 ci status --repo acme/widget 2>&1)"
check "status flags a missing fallback token" sh -c "echo \"\$0\" | grep -q 'RUNNER_STATUS_PAT secret is missing'" "$out"
out="$(FAKE_LABEL=self-hosted ci status --repo acme/widget 2>&1)"
check "status says ON, always self-hosted" sh -c "echo \"\$0\" | grep -q 'ON, always'" "$out"
out="$(FAKE_LABEL=self-hosted FAKE_ONLINE=0 ci status --repo acme/widget 2>&1)"
check "status warns when no runner is online" sh -c "echo \"\$0\" | grep -q 'none online'" "$out"
check "status shows the online runner" sh -c "echo \"\$0\" | grep -q 'host-widget'" "$(ci status --repo acme/widget 2>&1)"
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
