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
  "secret list"*) [ -z "${FAKE_SECRET_FAIL:-}" ] || exit 1; [ -n "${FAKE_NO_SECRET:-}" ] || printf 'RUNNER_STATUS_PAT\t2026-01-01\n' ;;
  "secret set"*) cat > "$GH_LOG.secret" ;;
  *"| length"*) echo "${FAKE_ONLINE:-1}" ;;
  *'=\(.busy)='*) [ -z "${FAKE_RUNNERS_FAIL:-}" ] || exit 1; [ -z "${FAKE_RUNNERS:-}" ] || printf '%s\n' $FAKE_RUNNERS ;;
  "api -X POST"*remove-token*) echo "tok-remove" ;;
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
# sudo runs the command as us (dropping -u USER -H); systemctl only records; fixed cores and OS.
cat > "$WORK/bin/sudo" <<'SUDO'
#!/bin/sh
echo "sudo $*" >> "$SUDO_LOG"
while [ $# -gt 0 ]; do case "$1" in -u) shift 2 ;; -H) shift ;; *) break ;; esac; done
exec "$@"
SUDO
cat > "$WORK/bin/systemctl" <<'SYSTEMCTL'
#!/bin/sh
echo "systemctl $*" >> "$SYSTEMCTL_LOG"
SYSTEMCTL
cat > "$WORK/bin/nproc" <<'NPROC'
#!/bin/sh
echo "${FAKE_CORES:-8}"
NPROC
REAL_UNAME="$(command -v uname)"
cat > "$WORK/bin/uname" <<UNAME
#!/bin/sh
case "\$1" in
  -s) echo "\${FAKE_OS:-Linux}" ;;
  -m) echo x86_64 ;;
  *) exec "$REAL_UNAME" "\$@" ;;
esac
UNAME
chmod +x "$WORK/bin/sudo" "$WORK/bin/systemctl" "$WORK/bin/nproc" "$WORK/bin/uname"
SYSD="$WORK/systemd"
mkdir -p "$SYSD"
export PATH="$WORK/bin:$PATH" HOME="$WORK/home" GH_LOG="$WORK/gh.log" SUDO_LOG="$WORK/sudo.log" \
  SYSTEMCTL_LOG="$WORK/systemctl.log" CI_RUNNER_SYSTEMD_DIR="$SYSD"
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
out="$(FAKE_NO_SECRET=1 ci on --repo acme/widget </dev/null 2>&1)" && rc=0 || rc=$?
check "without a token and no terminal, on refuses" sh -c "[ $rc -ne 0 ]"
check "...and names the two ways out" sh -c "echo \"\$0\" | grep -q -- '--no-fallback'" "$out"
: > "$GH_LOG"
FAKE_SECRET_FAIL=1 ci on --repo acme/widget </dev/null >/dev/null 2>&1
check "when secrets cannot be listed, the fallback stays on" logged "variable set CI_RUNNER_AUTO --repo acme/widget --body true"
check "...and no secret is overwritten" sh -c "! grep -q 'secret set' '$GH_LOG'"
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

echo "== caps / limits"
SLICE="$SYSD/ci-runner.slice"
for bad in 0 101 abc -5 50%; do
  check "--cpu $bad is refused" sh -c "! '$BASH_BIN' '$CLI' limits --cpu '$bad' --dry-run"
done
check "--memory 0 is refused" sh -c "! '$BASH_BIN' '$CLI' limits --memory 0 --dry-run"
check "--cpu 100 and --memory none are accepted" "$BASH_BIN" "$CLI" limits --cpu 100 --memory none --dry-run
out="$(ci limits --cpu 50 --memory 60 --dry-run 2>&1)"
check "limits --dry-run prints the slice" sh -c "echo \"\$0\" | grep -q 'CPUQuota=400%' && echo \"\$0\" | grep -q 'MemoryMax=60%'" "$out"
check "limits --dry-run writes no slice" test ! -e "$SLICE"
: > "$SYSTEMCTL_LOG"
out="$(ci limits --cpu 50 --memory 60 2>&1)"
check "limits writes CPUQuota as PCT x cores" grep -qx 'CPUQuota=400%' "$SLICE"
check "limits writes MemoryMax as a percentage" grep -qx 'MemoryMax=60%' "$SLICE"
check "limits reloads systemd" grep -q 'systemctl daemon-reload' "$SYSTEMCTL_LOG"
check "limits applies the caps live" grep -q 'set-property --runtime ci-runner.slice CPUQuota=400% MemoryMax=60%' "$SYSTEMCTL_LOG"
ci limits --cpu 75 >/dev/null 2>&1
check "limits --cpu keeps the memory cap" sh -c "grep -qx 'CPUQuota=600%' '$SLICE' && grep -qx 'MemoryMax=60%' '$SLICE'"
out="$(ci limits 2>&1)"
check "limits alone shows the caps" sh -c "echo \"\$0\" | grep -q 'CPU 75% (6 of 8 cores), memory 60%'" "$out"
ci limits --cpu none >/dev/null 2>&1
check "limits --cpu none drops the CPU cap" sh -c "! grep -q CPUQuota '$SLICE' && grep -qx 'MemoryMax=60%' '$SLICE'"
: > "$SYSTEMCTL_LOG"
ci limits --memory none >/dev/null 2>&1
check "removing both leaves an uncapped slice" sh -c "test -e '$SLICE' && ! grep -q 'CPUQuota=[0-9]' '$SLICE' && ! grep -q 'MemoryMax=' '$SLICE'"
check "...and resets the live caps" grep -q 'CPUQuota= MemoryMax=infinity' "$SYSTEMCTL_LOG"
out="$(FAKE_OS=Darwin ci limits --cpu 50 2>&1)" && rc=0 || rc=$?
check "macOS: limits prints a notice and succeeds" sh -c "[ $rc -eq 0 ] && echo \"\$0\" | grep -q 'not supported on macOS'" "$out"
rm -f "$SLICE"

echo "== slice membership"
out="$(ci install --dry-run --repo acme/widget --yes --dir "$WORK/capinst" --cpu 50 2>&1)"
check "install --cpu prints the capped slice" sh -c "echo \"\$0\" | grep -q 'CPUQuota=400%'" "$out"
check "install adds the drop-in" sh -c "echo \"\$0\" | grep -q 'Slice=ci-runner.slice'" "$out"
check "...after svc.sh install and before svc.sh start" sh -c "echo \"\$0\" | awk '/svc.sh install/ { i = NR } /Slice=ci-runner.slice/ { d = NR } /svc.sh start/ { s = NR } END { exit !(i && d && s && i < d && d < s) }'" "$out"
check "install --dry-run writes no slice" test ! -e "$SLICE"
out="$(ci install --dry-run --repo acme/widget --yes --dir "$WORK/capinst" 2>&1)"
check "install without caps still joins an (uncapped) slice" sh -c "echo \"\$0\" | grep -q 'Slice=ci-runner.slice' && ! echo \"\$0\" | grep -q 'CPUQuota=[0-9]'" "$out"
out="$(FAKE_OS=Darwin ci install --dry-run --repo acme/widget --yes --dir "$WORK/capinst" --cpu 50 2>&1)" && rc=0 || rc=$?
check "macOS: install --cpu prints the notice and still installs" sh -c "[ $rc -eq 0 ] && echo \"\$0\" | grep -q 'not supported on macOS' && echo \"\$0\" | grep -q 'svc.sh install' && ! echo \"\$0\" | grep -q 'Slice='" "$out"
UNIT="actions.runner.acme-widget.host-a.service"
mkdir -p "$WORK/joinbase/widget"
echo "$UNIT" > "$WORK/joinbase/widget/.service"
: > "$SYSTEMCTL_LOG"
out="$(ci limits --cpu 50 --dir "$WORK/joinbase" 2>&1)"
check "limits gives an existing instance the drop-in" grep -qx 'Slice=ci-runner.slice' "$SYSD/$UNIT.d/ci-runner-slice.conf"
check "...restarts it so it joins" grep -q "systemctl restart $UNIT" "$SYSTEMCTL_LOG"
check "...and warns that a running job is interrupted" sh -c "echo \"\$0\" | grep -q 'interrupted'" "$out"
: > "$SYSTEMCTL_LOG"
ci limits --cpu 60 --dir "$WORK/joinbase" >/dev/null 2>&1
check "an instance already in the slice is not restarted" sh -c "! grep -q restart '$SYSTEMCTL_LOG'"
mkdir -p "$WORK/joinbase/evil"
echo "sshd.service" > "$WORK/joinbase/evil/.service"
: > "$SYSTEMCTL_LOG"
ci limits --cpu 60 --dir "$WORK/joinbase" >/dev/null 2>&1
check "a .service naming a non-runner unit is ignored" sh -c "[ ! -e '$SYSD/sshd.service.d' ] && ! grep -q 'restart sshd' '$SYSTEMCTL_LOG'"
rm -rf "$WORK/joinbase/evil"
mkdir -p "$WORK/uninst/widget"
printf '#!/bin/sh\nexit 0\n' > "$WORK/uninst/widget/config.sh"
chmod +x "$WORK/uninst/widget/config.sh"
echo "$UNIT" > "$WORK/uninst/widget/.service"
ci uninstall --repo acme/widget --dir "$WORK/uninst" >/dev/null 2>&1
check "uninstall deletes the runner directory" test ! -e "$WORK/uninst/widget"
check "uninstall removes the instance's drop-in" test ! -e "$SYSD/$UNIT.d"
check "...and keeps the slice" test -e "$SLICE"
rm -f "$SLICE"

echo "== scale"
SC="$WORK/sc"
HOST="$(hostname -s 2>/dev/null || hostname)"
# Own the instance directories, so the tests do not depend on who runs them.
# shellcheck disable=SC2012  # the same owner lookup ci-runner does
FAKE_USER="$(ls -ld "$WORK" | awk '{print $3}')"
export FAKE_USER
mkinst() {
  local d="$SC/widget"
  [ "$1" -eq 1 ] || d="$SC/widget-$1"
  mkdir -p "$d"
  printf '#!/bin/sh\nexit 0\n' > "$d/config.sh"
  chmod +x "$d/config.sh"
  touch "$d/.runner"
}
sc() { ci scale "$@" --repo acme/widget --dir "$SC"; }
check "scale without N is refused" sh -c "! '$BASH_BIN' '$CLI' scale --repo acme/widget --dry-run"
out="$("$BASH_BIN" "$CLI" scale 0 --repo acme/widget --dry-run 2>&1)" && rc=0 || rc=$?
check "scale 0 is refused and points at uninstall" sh -c "[ $rc -ne 0 ] && echo \"\$0\" | grep -q 'ci-runner uninstall'" "$out"
check "scale abc is refused" sh -c "! '$BASH_BIN' '$CLI' scale abc --repo acme/widget --dry-run"
check "scale takes one number only" sh -c "! '$BASH_BIN' '$CLI' scale 2 3 --repo acme/widget --dry-run"
for i in 1 2 3 4; do mkinst "$i"; done
mkdir -p "$SC/widget-tools" && cp "$SC/widget/config.sh" "$SC/widget-tools/"
out="$(sc 2 --dry-run 2>&1)"
check "scale down removes the highest first" sh -c "echo \"\$0\" | awk '/Removing the runner at .*widget-4\$/ { a = NR } /Removing the runner at .*widget-3\$/ { b = NR } END { exit !(a && b && a < b) }'" "$out"
check "...and keeps 1 and 2" sh -c "! echo \"\$0\" | grep -q 'Removing the runner at .*/widget\$' && ! echo \"\$0\" | grep -q 'Removing the runner at .*widget-2\$'" "$out"
check "scale --dry-run deletes nothing" test -d "$SC/widget-4"
check "scale --dry-run asks for no remove token" sh -c "! grep -q remove-token '$GH_LOG'"
sc 2 >/dev/null 2>&1 && rc=0 || rc=$?
check "scale down succeeds" test "$rc" -eq 0
check "scale down deletes 3 and 4" sh -c "[ ! -e '$SC/widget-3' ] && [ ! -e '$SC/widget-4' ]"
check "...keeps 1 and 2" sh -c "[ -d '$SC/widget' ] && [ -d '$SC/widget-2' ]"
check "...deregisters with a remove token" logged "remove-token"
check "scale leaves another repo's runner alone" test -d "$SC/widget-tools"
out="$(sc 2 2>&1)"
check "scale to the current count changes nothing" sh -c "echo \"\$0\" | grep -q 'nothing to change'" "$out"
rm -rf "$SC/widget-2"; mkinst 3
out="$(sc 2 --dry-run 2>&1)"
check "with 1 and 3, scale 2 removes 3" sh -c "echo \"\$0\" | grep -q 'Removing the runner at .*widget-3\$'" "$out"
check "...and adds 2" sh -c "echo \"\$0\" | grep -q 'into $SC/widget-2\$'" "$out"
out="$(sc 3 --dry-run 2>&1)"
check "with 1 and 3, scale 3 adds only 2" sh -c "echo \"\$0\" | grep -q 'into $SC/widget-2\$' && ! echo \"\$0\" | grep -q 'Removing' && ! echo \"\$0\" | grep -q 'into $SC/widget-3\$'" "$out"
rm -rf "$SC/widget-3"; mkinst 2
out="$(FAKE_RUNNERS="$HOST-widget=false=gpu" sc 4 --dry-run 2>&1)"
check "scale up adds 3 and 4 only" sh -c "echo \"\$0\" | grep -q 'into $SC/widget-3\$' && echo \"\$0\" | grep -q 'into $SC/widget-4\$' && ! echo \"\$0\" | grep -q 'into $SC/widget\$'" "$out"
check "...with the existing instances' label" sh -c "echo \"\$0\" | grep -q 'label: gpu'" "$out"
out="$(FAKE_RUNNERS="$HOST-widget=false=gpu" sc 3 --label cpu --dry-run 2>&1)"
check "--label overrides the existing label" sh -c "echo \"\$0\" | grep -q 'label: cpu'" "$out"
out="$(sc 3 --dry-run --cpu 40 2>&1)"
check "scale --cpu sets the cap too" sh -c "echo \"\$0\" | grep -q 'CPUQuota=320%'" "$out"
mkinst 3
out="$(FAKE_RUNNERS="$HOST-widget-3=true=" sc 2 2>&1)" && rc=0 || rc=$?
check "a busy instance is kept" test -d "$SC/widget-3"
check "...says so and exits non-zero" sh -c "[ $rc -ne 0 ] && echo \"\$0\" | grep -q 'busy'" "$out"
FAKE_RUNNERS="$HOST-widget-3=true=" sc 2 --force >/dev/null 2>&1
check "--force removes a busy instance" test ! -e "$SC/widget-3"
mkinst 3
out="$(FAKE_RUNNERS_FAIL=1 sc 2 2>&1)"
check "an unreadable runner list warns and proceeds" sh -c "[ ! -e '$SC/widget-3' ] && echo \"\$0\" | grep -q 'could not check'" "$out"
mkdir -p "$SC/widget-3"
out="$(sc 2 2>&1)"
check "scale removes a partial directory above N" sh -c "[ ! -e '$SC/widget-3' ] && echo \"\$0\" | grep -q 'Removing the partial runner directory'" "$out"
mkdir -p "$WORK/sc-partial/widget-2"
out="$(ci status --repo acme/widget --dir "$WORK/sc-partial" 2>&1)"
check "status marks a partial directory" sh -c "echo \"\$0\" | grep -q 'widget-2 .*partial'" "$out"
out="$(ci scale 2 --repo acme/widget --dir "$WORK/sc-empty" --yes --dry-run 2>&1)"
check "scale with no instances installs like install" sh -c "echo \"\$0\" | grep -q 'into $WORK/sc-empty/widget\$' && echo \"\$0\" | grep -q 'into $WORK/sc-empty/widget-2\$'" "$out"
unset FAKE_USER

echo "== next steps / status"
out="$(ci install --dry-run --repo acme/widget --yes --dir "$WORK/ns" --count 2 --cpu 50 2>&1)"
check "install ends with next steps" sh -c "echo \"\$0\" | grep -q '^Next steps'" "$out"
check "...with the count and caps it leaves" sh -c "echo \"\$0\" | grep -q '2 runner instance(s) for acme/widget' && echo \"\$0\" | grep -q 'CPU 50% (4 of 8 cores)'" "$out"
check "...how to scale and cap later" sh -c "echo \"\$0\" | grep -q 'ci-runner scale N --repo acme/widget' && echo \"\$0\" | grep -q 'ci-runner limits --cpu PCT --memory PCT'" "$out"
check "...how to turn it on and check the workflows" sh -c "echo \"\$0\" | grep -q 'ci-runner on --repo acme/widget' && echo \"\$0\" | grep -q 'ci-runner check'" "$out"
out="$(ci install --dry-run --org acme --yes --dir "$WORK/ns" 2>&1)"
check "org install: on names --org-runner" sh -c "echo \"\$0\" | grep -q 'ci-runner on --org-runner --repo acme/<repo>' && echo \"\$0\" | grep -q 'ci-runner scale N --org acme'" "$out"
out="$(ci scale 3 --dry-run --repo acme/widget --yes --dir "$WORK/ns" 2>&1)"
check "scale ends with next steps and the new count" sh -c "echo \"\$0\" | grep -q '^Next steps' && echo \"\$0\" | grep -q '3 runner instance(s)'" "$out"
out="$(ci limits --memory 70 --dry-run 2>&1)"
check "limits ends with next steps and the caps" sh -c "echo \"\$0\" | grep -q '^Next steps' && echo \"\$0\" | grep -q 'memory 70%' && echo \"\$0\" | grep -q 'ci-runner check'" "$out"
out="$(ci status --repo acme/widget 2>&1)"
check "status shows the instance count" sh -c "echo \"\$0\" | grep -q 'Instances on this machine: 2'" "$out"
check "status shows the caps" sh -c "echo \"\$0\" | grep -q 'Resource caps (all ci-runner instances on this machine): none'" "$out"
out="$(FAKE_OS=Darwin ci status --repo acme/widget 2>&1)"
check "status on macOS says caps are unsupported" sh -c "echo \"\$0\" | grep -q 'not supported on macOS'" "$out"

echo "== check"
FX="$ROOT/tests/ci-runner-fixtures/check"
BAD_CI="$FX/bad/.github/workflows/ci.yml"
# The line number of the first fixture line containing $1 (so tests survive fixture edits).
line_of() { grep -nF -- "$1" "${2:-$BAD_CI}" | head -1 | cut -d: -f1; }
out="$("$BASH_BIN" "$CLI" check "$FX/bad" 2>&1)" && rc=0 || rc=$?
# shellcheck disable=SC2317,SC2329  # called through check
has() { printf '%s\n' "$out" | grep -qF -- "$1"; }
check "check exits 1 on warnings" test "$rc" -eq 1
check "R1 missing select-runner.yml" has ".github/workflows/select-runner.yml: warning:"
check "R2 hardcoded ubuntu-latest" has ".github/workflows/ci.yml:$(line_of 'runs-on: ubuntu-latest'): warning: job 'build'"
check "R2 in a flow list" has ".github/workflows/ci.yml:$(line_of 'runs-on: [ubuntu-22.04]'): warning:"
check "R2 in a block list" has ".github/workflows/ci.yml:$(line_of '      - ubuntu-latest'): warning: job 'block'"
check "R2 in a same-indent block list" has ".github/workflows/ci.yml:$(line_of '    - ubuntu-24.04'): warning: job 'compact'"
check "R4 in same-indent steps" has ".github/workflows/ci.yml:$(line_of 'sudo systemctl restart compact-service'): warning:"
check "R5 in same-indent steps" has ".github/workflows/ci.yml:$(grep -nF -- '    - uses: actions/cache@v4' "$BAD_CI" | grep -v '      - ' | tail -1 | cut -d: -f1): warning:"
check "R3 macos is info" has ".github/workflows/ci.yml:$(line_of 'runs-on: macos-14'): info:"
check "R4 sudo" has ".github/workflows/ci.yml:$(line_of 'run: sudo apt-get'): warning:"
check "R5 unguarded actions/cache" has ".github/workflows/ci.yml:$(line_of 'uses: actions/cache@v4'): warning:"
check "R5 setup-node with cache:" has ".github/workflows/ci.yml:$(line_of 'uses: actions/setup-node@v4'): warning:"
check "R6 container:" has ".github/workflows/ci.yml:$(line_of 'container: node:20'): warning:"
check "R6 services:" has ".github/workflows/ci.yml:$(line_of 'services:'): warning:"
check "R6 docker://" has ".github/workflows/ci.yml:$(line_of 'docker://alpine'): warning:"
check "R7 git config --global" has ".github/workflows/ci.yml:$(line_of 'git config --global'): warning:"
check "R7 redirect into ~/" has ".github/workflows/ci.yml:$(line_of 'echo hi > ~/'): warning:"
check "R7 mkdir under \$HOME" has ".github/workflows/ci.yml:$(line_of 'mkdir -p'): warning:"
check "R8 fixed /tmp path" has ".github/workflows/ci.yml:$(line_of 'cp build.log /tmp/'): warning:"
check "R8 in a .yaml file's env" has ".github/workflows/release.yaml:$(line_of 'OUT: /tmp' "$FX/bad/.github/workflows/release.yaml"): warning:"
check "R9 curl | bash" has ".github/workflows/ci.yml:$(line_of 'curl -fsSL'): warning:"
check "R9 wget | sh" has ".github/workflows/ci.yml:$(line_of 'wget -qO-'): warning:"
check "a step name mentioning sudo is not reported" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(line_of 'name: Install jq'):'" "$out"
check "comment lines are not reported" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(line_of 'in-a-comment'):'" "$out"
check "'# ci-runner: ignore' silences a line" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(line_of 'ci-runner: ignore'):'" "$out"
check "reading from ~/ is not a home write" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(line_of 'cp ~/.config'):'" "$out"
check "mktemp under /tmp is fine" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(line_of 'mktemp'):'" "$out"
check "a cache step guarded by its if: is fine" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(($(line_of "if: needs.select-runner.outputs.self-hosted != 'true'") - 1)):'" "$out"
check "a cache step in a guarded job is fine" sh -c "! printf '%s\n' \"\$0\" | grep -q 'ci.yml:$(grep -nF -- '      - uses: actions/cache@v4' "$BAD_CI" | sed -n 3p | cut -d: -f1):'" "$out"
check "an expression runs-on is not judged" sh -c "! printf '%s\n' \"\$0\" | grep -q \"job 'matrix'\"" "$out"
check "findings are sorted by file and line" sh -c "printf '%s\n' \"\$0\" | grep '^\.github/workflows/ci\.yml:' | cut -d: -f2 | sort -nc" "$out"
check "the summary points at the README" has "Making jobs runner-safe"
out="$("$BASH_BIN" "$CLI" check "$FX/clean" 2>&1)" && rc=0 || rc=$?
check "a clean repo exits 0" test "$rc" -eq 0
check "...says so, and skips select-runner.yml itself" sh -c "printf '%s\n' \"\$0\" | grep -q 'No problems found' && ! printf '%s\n' \"\$0\" | grep -q 'select-runner.yml:'" "$out"
out="$("$BASH_BIN" "$CLI" check "$FX/info-only" 2>&1)" && rc=0 || rc=$?
check "info-only findings exit 0" sh -c "[ $rc -eq 0 ] && [ \$(printf '%s\n' \"\$0\" | grep -c ': info: ') -eq 2 ]" "$out"
mkdir -p "$WORK/noflows"
"$BASH_BIN" "$CLI" check "$WORK/noflows" >/dev/null 2>&1; rc=$?
check "no .github/workflows exits 2" test "$rc" -eq 2
mkdir -p "$WORK/noflows/.github/workflows"
"$BASH_BIN" "$CLI" check "$WORK/noflows" >/dev/null 2>&1; rc=$?
check "no workflow files exits 2" test "$rc" -eq 2
check "check uses the current directory by default" sh -c "cd '$FX/clean' && '$BASH_BIN' '$CLI' check"

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
