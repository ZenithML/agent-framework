# ci-runner: scale, resource caps and workflow readiness — Requirements

**Status:** Approved
**Last Updated:** 2026-10-16

Scope: `plugins/ci-runner` 0.3.0. The 0.2.0 behaviour (install, uninstall, on, off, status,
workflow) is described in [`plugins/ci-runner/README.md`](../../../plugins/ci-runner/README.md);
this spec covers only what 0.3.0 adds or changes.

## Problem Statement

A user who runs a self-hosted runner with `ci-runner` wants the machine kept busy with CI jobs
without CI starving everything else on it, and has found that turning ci-runner on for a
repository is not enough, because the repository's workflows have to be prepared too.

Today:

- **Instance count is grow-only.** `install --count N` adds missing instances, but nothing removes
  some of them. The only way down is `uninstall` (all of them) followed by a fresh `install`.
- **No resource limits.** Each instance runs one job, so N instances run N jobs at once with
  nothing capping their combined CPU or memory. More instances means more throughput but also a
  machine that stops responding during a heavy build.
- **No readiness check.** The README lists what makes a workflow safe on a self-hosted runner
  (no sudo, no actions/cache, no fixed /tmp paths, ...), but the user has to read every workflow
  by hand. A repo switched `on` without a `select-runner` job keeps running on GitHub-hosted
  runners and the user may not notice. A job that uses sudo fails on the runner.

## Goals

- **G1 Scale.** `ci-runner scale N [--repo OWNER/NAME | --org ORG]` leaves exactly instances
  1..N installed on this machine for that target: it removes every instance numbered above N
  (stop service, deregister, delete directory) and installs any of 1..N that is missing.
- **G2 Collective caps (Linux).** `install`, `scale` and a new `limits` command take
  `--cpu PCT` and `--memory PCT` (percent of the machine). All ci-runner instances on the machine
  run in one systemd slice, `ci-runner.slice`, whose `CPUQuota` is PCT x cores and whose
  `MemoryMax` is PCT%, so the cap holds for all instances together, across every repo and org.
- **G3 Adjust and remove caps.** `ci-runner limits --cpu PCT --memory PCT` changes the caps
  later, `--cpu none` / `--memory none` removes one, and `ci-runner limits` with no flags prints
  the current caps.
- **G4 macOS.** On macOS, `--cpu` / `--memory` and `limits` print a notice that resource caps are
  not supported there and carry on with the rest of the command, exiting 0.
- **G5 Status.** `ci-runner status` shows how many instances are installed on this machine for
  the target and the current caps (or "none", or "not supported on macOS").
- **G6 Readiness check.** `ci-runner check [DIR]` scans `DIR/.github/workflows` (default: the
  current directory) and prints one finding per problem as `file:line: level: message`, for each
  rule in the Rules table below. It exits 1 when any warning is found and 0 when there is none.
- **G7 Dry run.** Every command that writes (scale, limits, install with caps) honours
  `--dry-run`: it prints every command and every file it would write, including the slice and
  drop-in contents, and changes nothing on the machine or on GitHub.
- **G8 Docs, usage and tests.** `ci-runner --help`, `plugins/ci-runner/README.md`,
  `docs/plugins.md` and the `/ci-runner:setup` skill describe the new commands; `tests/ci-runner.sh`
  covers scale and caps with dry-run and stubbed commands, and `check` with fixture workflows.
- **G9 Release.** The plugin version is 0.3.0 in `bin/ci-runner`, `.claude-plugin/plugin.json`
  and its `marketplace.json` entry.
- **G10 Clear manual.** `plugins/ci-runner/README.md` has a section for each new command
  (`scale`, `limits` and the caps flags, `check`) that says what it does, when to use it, and gives
  an example, and its repo-side checklist ("Making jobs runner-safe") lists every rule `check`
  reports, with the fix for each.
- **G11 Next steps.** When `install`, `scale` or `limits` finishes, it prints short next steps:
  the current instance count and caps, how to change them later (`ci-runner scale N`,
  `ci-runner limits --cpu/--memory`), `ci-runner on` for the repo, and `ci-runner check` to see
  what the repo's workflows still need.

### Readiness check rules

| ID | Finding | Level |
|---|---|---|
| R1 | `.github/workflows/select-runner.yml` is missing | warning |
| R2 | A job's `runs-on` is a hardcoded GitHub-hosted label (`ubuntu-*`, scalar or in a list) instead of `needs.select-runner.outputs.target` or `vars.CI_RUNNER_LABEL` | warning |
| R3 | A job's `runs-on` is a hardcoded `macos-*` or `windows-*` label (it stays GitHub-hosted on purpose, or cannot run on a Linux runner) | info |
| R4 | `sudo` in a step | warning |
| R5 | `uses: actions/cache@...` (or a `actions/setup-*` step with a `cache:` input) without an `if:` on the step or job that mentions `self-hosted` | warning |
| R6 | Job-level `container:` or `services:`, or a step `uses: docker://...` (needs Docker on the machine) | warning |
| R7 | `git config --global`, or a write to `~/`, `$HOME/` or `${HOME}/` (redirect, `tee`, `cp`, `mv`, `mkdir`, `touch`, `ln`) | warning |
| R8 | A fixed `/tmp/...` path (persists between jobs and collides between instances; use `$RUNNER_TEMP`) | warning |
| R9 | `curl ... \| bash`/`sh` or `wget ... \| bash`/`sh` installers | warning |

## Out of Scope

- Autoscaling. There is no autoscaler: a maximum instance count (`scale`) plus collective caps
  is the model; nothing adds or removes instances based on queue length or load.
- Per-instance or per-repo caps. The cap is one budget for every ci-runner instance on the
  machine.
- Caps on macOS (launchd has no collective equivalent of a systemd slice). Notice only.
- cgroup controls beyond CPU and memory (IO weight, tasks max, swap).
- Removing runners registered on GitHub whose directory is already gone (stale registrations).
- Draining: `scale` does not wait for a busy instance to finish its job (see Story 3).
- A YAML parser. `check` is line-based (grep/awk) and can miss or misreport unusual layouts; it
  does not detect Docker-based actions referenced by name (only `docker://`, `container:` and
  `services:`), does not follow reusable workflows or composite actions, and does not check whether
  `select-runner.yml` is up to date with the template.
- Rewriting workflows. `check` reports; it never edits.
- Changing `install`'s grow-only behaviour: `install --count N` still never removes instances.

## User Stories & Acceptance Criteria

### Story 1: Scale up

**Given** instances 1 and 2 are installed for `acme/widget`
**When** I run `ci-runner scale 4 --repo acme/widget`
**Then** instances 3 and 4 are downloaded, registered and started exactly as `install` would add
them, instances 1 and 2 are left alone, and the command reports 4 instances.

**Given** instances 1 and 3 are installed (2 was removed by hand)
**When** I run `ci-runner scale 3`
**Then** instance 2 is installed and 1 and 3 are left alone.

**Given** existing instances were installed with `--label gpu` and as account `ci-runner`
**When** I run `ci-runner scale 3` without `--label` or `--run-as`
**Then** the new instances get label `gpu` and run as `ci-runner`, the same as the existing ones,
and the command says which label and account it used. `--label` / `--run-as` override this.

**Given** no instance is installed for the target
**When** I run `ci-runner scale 2`
**Then** it behaves as `ci-runner install --count 2` (including the account prompt or `--yes`
requirement).

### Story 2: Scale down

**Given** instances 1 to 4 are installed for `acme/widget`
**When** I run `ci-runner scale 2 --repo acme/widget`
**Then** instances 4 and 3, in that order, each have their service stopped and uninstalled, are
deregistered from GitHub with a remove token, and have their directory deleted, by the same
per-directory steps `uninstall` uses (including acting as the directory's owning account);
instances 1 and 2 keep running; the command reports 2 instances.

**Given** instances 1 and 3 are installed
**When** I run `ci-runner scale 2`
**Then** instance 3 is removed and instance 2 is installed, leaving exactly 1 and 2.

**Given** instances 1 and 2 are installed
**When** I run `ci-runner scale 2`
**Then** nothing is changed and it says so.

**Given** any state
**When** I run `ci-runner scale 0`, `scale -1`, `scale abc` or `scale` with no number
**Then** it exits non-zero with a message; for 0 the message points at `ci-runner uninstall`.

**Given** a repo-level instance set for `acme/widget` and another for `acme/widget-tools`
**When** I scale `acme/widget`
**Then** no directory of `widget-tools` is touched (same matching rule as `uninstall`).

### Story 3: Do not kill a running job when scaling down

**Given** instance 3 is busy running a job according to the GitHub API
**When** I run `ci-runner scale 2`
**Then** instance 3 is not removed, the command says it is busy and to retry or pass `--force`,
and it exits non-zero after doing the rest of the work.

**Given** the same
**When** I run `ci-runner scale 2 --force`
**Then** instance 3 is removed anyway.

**Given** the runner list cannot be read (no admin rights, network error)
**When** I scale down
**Then** it warns that it could not check for busy runners and proceeds.

### Story 4: Set a collective cap (Linux)

**Given** a Linux machine with 8 cores
**When** I run `ci-runner install --repo acme/widget --count 4 --cpu 50 --memory 60`
**Then** `/etc/systemd/system/ci-runner.slice` contains `CPUQuota=400%` and `MemoryMax=60%`,
each instance's service has a drop-in setting `Slice=ci-runner.slice` before it is first started,
systemd is reloaded, and all four instances together can use at most 4 cores and 60% of memory.

**Given** instances for two repos on the same machine, both in the slice
**When** I set `--cpu 50`
**Then** the 50% is shared by both repos' instances, not granted to each.

**Given** `--cpu` or `--memory` with a value that is not an integer from 1 to 100 or `none`
**When** I run any command that takes them
**Then** it exits non-zero with a message before changing anything.

**Given** only `--cpu 50` is passed and a memory cap is already set
**When** the command runs
**Then** the memory cap is kept; only the flag given changes.

### Story 5: Adjust or remove the cap later

**Given** caps CPU 50% and memory 60% are set
**When** I run `ci-runner limits --cpu 75`
**Then** the slice's `CPUQuota` becomes 75% x cores, the memory cap stays, and the new quota
applies to running instances without restarting them.

**Given** the same
**When** I run `ci-runner limits --cpu none`
**Then** the CPU cap is removed and the memory cap stays; `limits --cpu none --memory none`
leaves the slice with no caps.

**Given** caps are set
**When** I run `ci-runner limits` with no flags
**Then** it prints the current caps (as percent of the machine and as cores / `MemoryMax`) and
changes nothing.

**Given** ci-runner instances under the runner directory that are not yet in the slice (for
example installed by 0.2.0)
**When** I run `ci-runner limits --cpu 50`
**Then** each gets the drop-in and is restarted so that it joins the slice, and the command names
each one it restarts and warns that a restart interrupts a job that is running on it.

**Given** `ci-runner scale 3 --cpu 40`
**When** it runs
**Then** it scales to 3 and sets the CPU cap, as if `scale 3` and `limits --cpu 40` were run.

### Story 6: macOS

**Given** a Mac
**When** I run `ci-runner install --count 2 --cpu 50 --yes`, `ci-runner scale 2 --memory 50` or
`ci-runner limits --cpu 50`
**Then** it prints that resource caps are not supported on macOS, does everything else the command
does, and exits 0.

### Story 7: Status shows count and caps

**Given** 3 instances installed for `acme/widget` and caps CPU 50% / memory 60% on an 8-core machine
**When** I run `ci-runner status --repo acme/widget`
**Then** it shows the instance count (3) and the caps (`CPU 50% (4 of 8 cores), memory 60%`).

**Given** no caps, or a Mac
**When** I run `ci-runner status`
**Then** the caps line says `none`, or that caps are not supported on macOS.

### Story 8: Uninstall leaves no stray drop-in

**Given** an instance in the slice
**When** it is removed by `uninstall` or `scale`
**Then** its drop-in directory is removed too. The slice unit stays (it is inert without members).

### Story 9: Check a repository's workflows

**Given** a repo whose workflows trigger every rule R1 to R9
**When** I run `ci-runner check` in it
**Then** it prints one finding per occurrence as `<path>:<line>: <warning|info>: <message>`, paths
relative to DIR (R1, a missing file, has no line: `.github/workflows/select-runner.yml: warning: ...`), sorted by file then line, followed by a summary count and a pointer to the
README's "Making jobs runner-safe" section, and exits 1.

**Given** a repo whose workflows have `select-runner.yml`, every job on
`needs.select-runner.outputs.target`, cache steps guarded with
`if: needs.select-runner.outputs.self-hosted != 'true'`, and none of R4 and R6 to R9
**When** I run `ci-runner check DIR`
**Then** it prints that no problems were found and exits 0.

**Given** the only findings are info (R3)
**When** I run `ci-runner check`
**Then** it prints them and exits 0.

**Given** a line ending in the comment `# ci-runner: ignore`
**When** a rule matches that line
**Then** no finding is reported for it.

**Given** a match inside a YAML comment line (first non-blank character `#`)
**When** I run `ci-runner check`
**Then** it is not reported.

**Given** `select-runner.yml` itself
**When** I run `ci-runner check`
**Then** its own `runs-on` and steps are not reported.

**Given** DIR has no `.github/workflows` directory, or it has no `*.yml` / `*.yaml` files
**When** I run `ci-runner check DIR`
**Then** it says so and exits 2.

**Given** `ci-runner check` runs anywhere
**When** it runs
**Then** it needs no `gh`, network, `yq` or other non-POSIX tool, and writes nothing.

### Story 10: Next steps after install, scale and limits

**Given** `ci-runner install --repo acme/widget --count 2 --cpu 50` (or `scale`, or `limits`) has finished
**When** it prints its closing lines
**Then** they show the instance count for the target (not for `limits`, which has no target) and the
caps, the commands to change them (`ci-runner scale N --repo acme/widget`,
`ci-runner limits --cpu PCT --memory PCT`), `ci-runner on --repo acme/widget` (for an org runner:
`ci-runner on --org-runner --repo ORG/<repo>`), and `ci-runner check` to run in a checkout of the
repo. With `--dry-run` the count and caps are the ones the run would produce.

### Story 11: Dry run

**Given** any of `scale`, `limits`, or `install` with `--cpu`/`--memory`
**When** I add `--dry-run`
**Then** it prints each command it would run and the full contents of the slice and drop-in files
it would write, requests no registration or remove token, calls no write API, writes no file,
and starts or stops no service.

## Constraints

- **Portability.** `bin/ci-runner` stays bash 3.2 and BSD/GNU userland safe as its header states:
  no associative arrays, `mapfile`, `${var,,}`, `sed -i`, `readlink -f`, empty-array expansions
  under `set -u`, GNU-only `grep -P`/`awk` extensions or `nproc`-only core counts (fall back to
  `getconf _NPROCESSORS_ONLN`).
- **No new dependencies.** `check` uses grep/awk/sed only, no `yq` or `jq`. Caps use `systemctl`
  and `sudo`, which the Linux service install already needs.
- **Reuse.** Scale-down uses the same per-directory removal code as `uninstall` (refactored into
  a shared function, not copied); scale-up uses `install_one`.
- **Privilege.** Writing the slice and drop-ins needs sudo, like `svc.sh install` today. Jobs still
  never run as root.
- **Shellcheck clean.** `shellcheck plugins/ci-runner/bin/ci-runner tests/ci-runner.sh` passes,
  as CI runs it.
- **Tests offline.** `tests/ci-runner.sh` stays runnable without GitHub, systemd or sudo, using
  stubs on `PATH`, and under `/bin/bash` 3.2 on macOS.
- **Gates.** `./scripts/check-all.sh` and `./tests/ci-runner.sh` pass. Version bump per
  [`docs/standards/release/design.md`](../../standards/release/design.md): new commands are a
  MINOR change, 0.2.0 to 0.3.0.
- No UI; accessibility requirements do not apply.

## References

- [`plugins/ci-runner/README.md`](../../../plugins/ci-runner/README.md) — current behaviour and the
  "Making jobs runner-safe" guidance that `check` automates
- [`plugins/ci-runner/bin/ci-runner`](../../../plugins/ci-runner/bin/ci-runner) — `install_one`,
  `cmd_uninstall`, `instance_dirs`
- [`tests/ci-runner.sh`](../../../tests/ci-runner.sh)
- [`docs/standards/release/design.md`](../../standards/release/design.md)
- systemd.resource-control(5): `CPUQuota=`, `MemoryMax=` (percentages), `Slice=`
- Requested by Spencer (GitHub spencerimp), who runs a self-hosted runner
