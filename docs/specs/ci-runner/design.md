# ci-runner: scale, resource caps and workflow readiness — Design

**Status:** Approved
**Last Updated:** 2026-10-16

Source: [requirements.md](requirements.md). Everything lives in the one script
`plugins/ci-runner/bin/ci-runner`; no new files ship except test fixtures.

## Architecture

### Component Design

New and changed functions in `bin/ci-runner`:

| Function | Role |
|---|---|
| `parse_opts` | Adds `--cpu PCT`, `--memory PCT` (integer 1..100 or `none`, validated before anything runs), records `LABEL_GIVEN`, and accepts one positional argument only when the dispatcher set `ALLOW_POS=true` (used by `scale N`). |
| `as_root` | Runs a command directly when uid is 0, else through `sudo`. |
| `write_root_file PATH CONTENT` | Dry run: prints `[dry-run] write PATH:` and the content, each line prefixed `      | `. Otherwise `printf … \| as_root tee PATH >/dev/null`. |
| `cpu_cores` | `nproc`, else `getconf _NPROCESSORS_ONLN`, else 1. |
| `read_caps` | Sets `CUR_CPU` / `CUR_MEM` from the `# ci-runner: cpu=X memory=Y` line of the slice file (`none` when absent). |
| `effective_caps` | `EFF_CPU=${CPU_CAP:-$CUR_CPU}`, same for memory: what the run will leave in place (also used by dry runs). |
| `caps_summary` | `CPU 50% (4 of 8 cores), memory 60%`, `none`, or `not supported on macOS`. |
| `apply_caps` | Writes the slice with the effective caps, `systemctl daemon-reload`, then `systemctl set-property --runtime ci-runner.slice CPUQuota=… MemoryMax=…` so running instances get the new quota without a restart (`CPUQuota=` and `MemoryMax=infinity` for `none`). A failing `set-property` warns; the file still applies at the next start. |
| `ensure_slice` | Writes an uncapped slice when none exists, so every Linux instance can join it from the start. |
| `join_slice DIR` | Writes the drop-in for the unit named in `DIR/.service` (dry run: a placeholder name) and reloads systemd. |
| `join_existing` | For every `*/.service` under the runner base(s) whose unit has no drop-in: write it, reload once, `systemctl restart` it, and say so with a warning that a restart interrupts a running job. |
| `remove_instance DIR` | The body of the old `cmd_uninstall` loop, moved verbatim, plus drop-in removal (unit name read from `.service` before `svc.sh uninstall` deletes it). Used by `uninstall` and `scale`. |
| `find_base` | `--dir`/`--run-as` given: as before. Otherwise the first of `~/actions-runner` and `~ci-runner/actions-runner` that holds instances for the target, else `~/actions-runner`. Used by `scale`, `status`, `limits`. |
| `instance_index DIR` | 1 for the bare slug, N for `slug-N`. |
| `install_one` | Linux: `svc.sh install`, then `join_slice`, then `svc.sh start` (the drop-in exists before the first start). |
| `cmd_install` | After `confirm_account`: Linux with caps flags runs `apply_caps`, else `ensure_slice`; macOS with caps flags prints the notice. After the loop, `join_existing` when caps flags were given. Ends with `next_steps`. |
| `cmd_scale` | See Data Flow. |
| `cmd_limits` | macOS: notice, exit 0. No flags: prints `caps_summary` and the slice path. Otherwise `apply_caps`, `join_existing`, `next_steps`. |
| `cmd_status` | Adds `Instances on this machine: N` and `Resource caps (all ci-runner instances): …`. |
| `next_steps COUNT` | The closing block (Story 10). |
| `cmd_check [DIR]` | Lists `DIR/.github/workflows/*.yml|*.yaml`, prints R1 when `select-runner.yml`/`.yaml` is missing, runs one awk program per other file, sorts the findings by file and line, prints a summary, exits 0/1/2. |

Test hook: `CI_RUNNER_SYSTEMD_DIR` (default `/etc/systemd/system`) so tests can write real unit
files into a temp dir. Not documented for users.

### Data Model

Machine state, all under `$SYSTEMD_DIR`:

```
ci-runner.slice
  # Written by ci-runner (agent-framework, plugins/ci-runner). Change with: ci-runner limits
  # ci-runner: cpu=50 memory=60
  [Unit]
  Description=ci-runner: self-hosted GitHub Actions runners (shared resource cap)
  [Slice]
  CPUAccounting=yes
  MemoryAccounting=yes
  CPUQuota=400%        # only when cpu != none; PCT x cores
  MemoryMax=60%        # only when memory != none

<unit>.service.d/ci-runner-slice.conf    # <unit> from the runner dir's .service file
  # Written by ci-runner: run this runner in the shared, capped ci-runner.slice
  [Service]
  Slice=ci-runner.slice
```

The comment line is the source of truth for the percentages (the core count can change; the
percentage is what the user chose). Nothing is stored per repo.

### Data Flow

**scale N**

1. Validate N (positive integer; 0 points to `uninstall`). `need_gh`, `resolve_repo`, `platform`.
2. `base=find_base`. `existing` = instance dirs with `config.sh`; the lowest-numbered is the
   reference instance.
3. Account: when no `--run-as`/`--create-user`/`--yes` and instances exist, `RUN_AS` = owner of the
   reference dir (if it is not us); no prompt. With no instances, `confirm_account` as in install.
4. Remove: for each instance dir with index > N, highest first: skip it when the runner list says
   it is busy and `--force` is not given (remembered for the exit code); else `remove_instance`.
   The runner list is one `gh api …/actions/runners` read; a failure warns and treats all as idle.
5. Add: when any of 1..N lacks `config.sh`+`.runner`: label = `--label`, else the first `custom`
   label of the reference runner in the same list, else `self-hosted`; look up the runner version;
   `ensure_slice` (or `apply_caps` with caps flags) on Linux; `install_one` for each missing index.
6. Caps flags without anything to add still run `apply_caps` + `join_existing`.
7. Nothing removed or added: `… already has instances 1..N; nothing to change.`
8. `next_steps`; exit 1 when a busy instance was kept.

**check**: per file, one awk pass with this state: inside `jobs:`; the job key indent (first key
under `jobs:`); current job name and its key indent; inside `steps:`; current step indent, its
`uses:`, `if:` and `cache:`; inside a `run:` block scalar (lines deeper than the `run:` key).
Rules on `runs-on:`/`container:`/`services:`/`if:` look at job keys; R5 is decided at job end
(a job-level `if:` may follow the steps); R4/R7/R9 look at script lines (inline `run:` values and
block lines); R8 looks at every non-comment line except `mktemp` lines.

## Decisions

| # | Question | Options Considered | Decision | Rationale |
|---|----------|--------------------|----------|-----------|
| 1 | Do instances join the slice only when caps are set? | Only with caps; always on Linux | Always on Linux: `install`/`scale` create an uncapped slice if missing and add the drop-in | Later `limits` then applies live with no restart; an uncapped slice costs nothing |
| 2 | How do caps change on a running system? | Rewrite file + daemon-reload; `set-property --runtime`; both | Both | The file persists across reboots; `set-property --runtime` applies the change to the running slice now. A failing runtime call only warns |
| 3 | Where are the chosen percentages kept? | Parse `CPUQuota` back; comment line | `# ci-runner: cpu=X memory=Y` in the slice | CPUQuota depends on the core count; the comment keeps the user's choice exactly |
| 4 | How is a unit's name found? | Recompute svc.sh's naming; `.service` file | `DIR/.service`, which `svc.sh install` writes | No duplication of svc.sh's escaping rules |
| 5 | Which instances does `limits` join? | systemd's `actions.runner.*`; runner dirs | Runner dirs under `find_base` candidates (all repos and orgs) | Only touches runners ci-runner manages |
| 6 | How does scale learn the label? | Marker file; GitHub API; always `self-hosted` | API (`custom` labels of the reference runner), `--label` overrides, else `self-hosted`, printed | Works for 0.2.0 installs; no new state |
| 7 | How does scale learn the account? | Ask again; owner of an existing dir | Owner of the reference dir | The choice was made at install; the same rule `uninstall` already uses |
| 8 | Busy detection when the API is unreadable | Refuse; proceed | Warn and proceed | Matches Story 3; the user can retry |
| 9 | Exit codes for check | 1 on any finding; 1 on warnings | 1 on warnings, 0 on info only or clean, 2 when there is nothing to check | Info marks deliberate GitHub-hosted jobs, which are not problems |
| 10 | Suppressing a false positive | None; config file; inline marker | `# ci-runner: ignore` at the end of the line | Heuristics need an escape hatch to be usable as a CI gate |
| 11 | Where do the next steps print in a dry run? | Skip; print planned values | Print, with the counts and caps the run would produce | The user sees the result before committing to it |
| 12 | `scale` needs `--force` for busy runners; `workflow` already has `--force` | New flag; reuse | Reuse `FORCE` | One meaning: "do it anyway" |

## Test Scenarios

### Unit Tests

Behaviour checked through the command, with stubs on `PATH` (`gh`, `id`, `sudo`, `systemctl`,
`nproc`, `uname`) and `CI_RUNNER_SYSTEMD_DIR` in a temp dir.

- `--cpu`/`--memory` reject 0, 101, `abc`, `-5`; accept 1, 100, `none`.
- `scale` rejects a missing N, 0 (message names `uninstall`), `abc`.
- `limits --cpu 50 --memory 60` on 8 cores writes `CPUQuota=400%` and `MemoryMax=60%`, reloads, sets runtime properties.
- `limits --cpu 75` afterwards keeps `MemoryMax=60%`; `limits --cpu none` drops `CPUQuota`.
- `limits` with no flags prints the caps and writes nothing.
- `limits --dry-run` prints the file content and writes no file.
- macOS (`uname -s` = Darwin): `limits --cpu 50` prints the notice and exits 0; `install --dry-run --cpu 50 --yes` does the same and still installs.
- `install --dry-run --cpu 50` prints `Slice=ci-runner.slice`, `CPUQuota=400%`, and `svc.sh start` after the drop-in.
- `limits` joins an existing instance with no drop-in: drop-in written, unit restarted, the restart named.
- `uninstall` removes an instance's drop-in.
- `scale 2` with 1..4: dry run removes 4 then 3, keeps 1 and 2, writes nothing, asks for no token; a real run (stubs) deletes 3 and 4 and asks for a remove token.
- `scale 2` with {1,3}: removes 3, adds 2. `scale 2` with {1,2}: says nothing to change.
- `scale 4` with {1,2}: adds 3 and 4 only, with the label from the API (`gpu`).
- A busy instance is kept and the exit code is 1; `--force` removes it.
- `scale` for `widget` leaves `widget-tools` alone.
- `status` shows the instance count and the caps line.
- Next steps after `install`, `scale`, `limits` name `ci-runner scale`, `ci-runner limits`, `ci-runner on`, `ci-runner check`.
- `check` on the `bad` fixture reports each of R1..R9 with the right file:line and exits 1; on `clean` exits 0 with no findings; on `info-only` prints info and exits 0; on a dir without workflows exits 2; comment lines, `# ci-runner: ignore` lines and `select-runner.yml` are not reported.

### BDD Scenarios

- **S1:** Given 1..2, When `scale 4`, Then 3 and 4 are added, 1 and 2 untouched. (Story 1)
- **S2:** Given {1,3}, When `scale 3`, Then 2 is added. (Story 1)
- **S3:** Given instances labelled `gpu`, When `scale 3` without `--label`, Then new ones get `gpu`. (Story 1)
- **S4:** Given 1..4, When `scale 2`, Then 4 then 3 are stopped, deregistered and deleted. (Story 2)
- **S5:** Given {1,3}, When `scale 2`, Then 3 removed and 2 added. (Story 2)
- **S6:** Given 1..2, When `scale 2`, Then nothing changes. (Story 2)
- **S7:** When `scale 0`/`abc`/no N, Then non-zero with message. (Story 2)
- **S8:** Given `widget` and `widget-tools`, When scaling `widget`, Then `widget-tools` untouched. (Story 2)
- **S9:** Given busy 3, When `scale 2`, Then 3 kept, exit 1; with `--force` removed. (Story 3)
- **S10:** Given 8 cores, When `install --cpu 50 --memory 60`, Then slice has 400% / 60% and drop-ins precede start. (Story 4)
- **S11:** When `--cpu 0`, Then refused before any change. (Story 4)
- **S12:** Given memory cap, When `limits --cpu 75`, Then memory kept, CPU changed live. (Stories 4, 5)
- **S13:** When `limits --cpu none`, Then CPU cap removed. (Story 5)
- **S14:** When `limits` alone, Then caps printed, nothing changed. (Story 5)
- **S15:** Given an instance outside the slice, When `limits --cpu 50`, Then it gets the drop-in and is restarted with a warning. (Story 5)
- **S16:** Given macOS, When caps flags are used, Then a notice and exit 0. (Story 6)
- **S17:** When `status`, Then count and caps shown. (Story 7)
- **S18:** When an instance is removed, Then its drop-in is removed. (Story 8)
- **S19:** Given the bad fixture, When `check`, Then R1..R9 reported, exit 1. (Story 9)
- **S20:** Given the clean fixture, When `check`, Then exit 0. (Story 9)
- **S21:** Given info-only findings, When `check`, Then exit 0. (Story 9)
- **S22:** Given comments, ignore markers and select-runner.yml, When `check`, Then not reported. (Story 9)
- **S23:** Given no workflows, When `check`, Then exit 2. (Story 9)
- **S24:** When install/scale/limits finish, Then next steps print. (Story 10)
- **S25:** With `--dry-run`, Then files printed, nothing written, no token. (Story 11)

### BDD Traceability

| BDD Scenario | Component(s) / Module(s) | Notes |
|---|---|---|
| S1–S9 | `cmd_scale`, `remove_instance`, `install_one`, `find_base` | Story 1–3 |
| S10–S16 | `parse_opts`, `apply_caps`, `ensure_slice`, `join_slice`, `join_existing`, `cmd_limits`, `cmd_install` | Story 4–6 |
| S17 | `cmd_status`, `caps_summary` | Story 7 |
| S18 | `remove_instance` | Story 8 |
| S19–S23 | `cmd_check` | Story 9 |
| S24 | `next_steps` | Story 10 |
| S25 | `run`, `write_root_file` | Story 11 |

### QA Scenarios

- `ci-runner --help` lists `scale`, `limits`, `check`, `--cpu`, `--memory` and `--force`.
- `ci-runner scale 3 --repo acme/widget --dry-run` with no instances installed prints three downloads and a next-steps block.
- `ci-runner limits --cpu 50 --memory 60 --dry-run` prints a slice file with `CPUQuota=` equal to 50 x the machine's cores and `MemoryMax=60%`, and leaves `/etc/systemd/system/ci-runner.slice` untouched.
- `ci-runner limits --cpu 150` exits non-zero with a message.
- `ci-runner check` in a repo with an `ubuntu-latest` job and `sudo apt-get` prints both with file:line and exits 1; after fixing both and adding select-runner.yml it exits 0.
- `ci-runner check /nonexistent` exits 2.
- The README has sections for scale, caps/limits and check, and its runner-safe checklist names every check rule.

## Edge Cases & Error Handling

- Caps value validation runs in `parse_opts`, before `need_gh`, so a bad value changes nothing.
- `.service` missing in a runner dir (service never installed): `join_slice`/`join_existing` skip it with a note.
- `systemctl set-property` failing (slice not loaded yet, old systemd): warning; the unit file applies at the next start.
- Core count unknown: 1, so `CPUQuota` is never 0%.
- A stale partial instance dir above N without `config.sh`: removed with `rm -rf` only.
- `check` on files with CRLF line endings: `\r` is stripped first.
- `check` block-list `runs-on:` (`- ubuntu-latest` lines below it) is handled; flow lists `[a, b]` too; expressions other than select-runner/CI_RUNNER_LABEL are not reported (cannot be judged).
- `cp`/`mv`/`ln` count as home writes only when a home path is the last argument.
- `.service` sits in a directory the runner account (and so any job) can write. Drop-ins are written,
  restarted and removed only for names matching `actions.runner.*.service`, so a job cannot get
  another service moved or restarted by a later `limits` run as root.
- `check` also reads lists written at the same indent as their key (`steps:` then `- run:` directly
  below, or `runs-on:` then `- label`).
