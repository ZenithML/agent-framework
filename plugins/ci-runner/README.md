# ci-runner

Run a repository's GitHub Actions jobs on your own Linux or macOS machine, and switch between
that machine and GitHub-hosted runners with one command. Generalised from ZenithML/zenith's
`self-hosted-runner/` scripts.

```
ci-runner on      # jobs use your machine when it is online, else GitHub-hosted
ci-runner off     # back to GitHub-hosted runners
ci-runner status  # what is on, what is online, what is missing
ci-runner check   # what the repo's workflows still need before they can run on your machine
ci-runner scale 4 --cpu 75 --memory 75   # 4 jobs at once, together using at most 3/4 of the machine
```

## Quick start

You need: the [GitHub CLI](https://cli.github.com) signed in with admin rights on the repo
(`gh auth login`), `curl`, `tar`, and bash 3.2 or later (the macOS default is fine).

```bash
# 1. Get the command (once per machine)
git clone https://github.com/zenithml/agent-framework.git
./agent-framework/plugins/ci-runner/install.sh        # links ci-runner into ~/.local/bin

# 2. Register this machine as the repo's runner (once per repo)
ci-runner install --repo OWNER/NAME --create-user     # Linux: runs jobs as a new 'ci-runner' account
ci-runner install --repo OWNER/NAME --yes             # or: run jobs as your own account

# 3. Wire the repo's workflows to it (once per repo), fix what check reports, then commit
cd your-repo && ci-runner workflow && ci-runner check
#    in each workflow, add the select-runner job and point jobs at its output:
#      jobs:
#        select-runner:
#          uses: ./.github/workflows/select-runner.yml
#          secrets: inherit
#        build:
#          needs: select-runner
#          runs-on: ${{ needs.select-runner.outputs.target }}

# 4. Turn it on
ci-runner on --repo OWNER/NAME
```

Until step 4, nothing changes: jobs keep running on GitHub-hosted runners. `install` ends by
printing these next steps, with the instance count and caps it left in place.

Turning ci-runner on is half the job: the repository's workflows must be ready too (step 3).
`ci-runner check` tells you what is missing; [Making jobs runner-safe](#making-jobs-runner-safe)
explains each finding.

## Turning it on and off

The switch is a few repository variables, so flipping it needs no commit and takes effect on the
next run. Jobs already running finish where they started.

| Command | What happens | Jobs while your machine is off |
|---|---|---|
| `ci-runner on` | Your machine when it is online, else GitHub-hosted (**fallback**) | Run on GitHub-hosted |
| `ci-runner on --no-fallback` | Always your machine | Wait in the queue |
| `ci-runner off` | Always GitHub-hosted | Run on GitHub-hosted |

`ci-runner status` tells you which one you are in, whether a runner is online, and anything
missing (the workflow file, the fallback token).

### The fallback token

To know whether your machine is online, the workflow asks GitHub to list the repo's runners, and
GitHub's built-in `GITHUB_TOKEN` is not allowed to do that. So the fallback needs one token that
you create once:

1. Create a [fine-grained token](https://github.com/settings/personal-access-tokens/new) with
   repository access to **only this repo** and the permission **Administration: Read-only**.
2. Give it to `ci-runner on`, which stores it as the `RUNNER_STATUS_PAT` secret:
   - run `ci-runner on` and paste it when asked (input is hidden), or
   - `RUNNER_STATUS_PAT=<token> ci-runner on` (never put a token in the command line itself).

No token? In a terminal you can press Enter to skip: `ci-runner on` then works in the
`--no-fallback` mode and says so. Run it again with a token later to add the fallback. Without a
terminal (a script) it refuses instead, so the fallback is never dropped silently: pass
`RUNNER_STATUS_PAT=<token>`, or `--no-fallback`. For a runner registered on an organization
(`install --org`), use `on --org-runner` and the organization permission
**Self-hosted runners: Read-only**.

### What it changes

| Variable (repo) | Set by | Meaning |
|---|---|---|
| `CI_RUNNER_AUTO=true` | `on` | Check for an online runner on every run, else use `hosted` |
| `CI_RUNNER_LABEL` | `on --no-fallback`, `on --label` | The runner label jobs target (default `self-hosted`) |
| `CI_RUNNER_SCOPE=org` | `on --org-runner` | Look the runner up on the organization |
| `RUNNER_STATUS_PAT` (secret) | `on` | The fallback token |

`off` deletes the three variables and leaves the secret (`gh secret delete RUNNER_STATUS_PAT
--repo OWNER/NAME` removes it). The GitHub-hosted runner used for fallback is `ubuntu-latest`;
a workflow can choose another with `with: { hosted: ubuntu-24.04 }` on the `select-runner` job.

## Running more jobs at once: `scale`

Each runner instance runs one job at a time. To run more jobs in parallel, run more instances:

```bash
ci-runner scale 4 --repo OWNER/NAME     # exactly 4 instances on this machine for that repo
ci-runner scale 2 --repo OWNER/NAME     # back down to 2
ci-runner scale 3 --org ORG             # the same for an organization-level runner
```

- **Up:** adds whichever of instances 1..N are missing, the same way `install` does. New instances
  get the label and account of the existing ones, unless you pass `--label` or `--run-as`.
- **Down:** removes the highest-numbered instances first. Each one has its service stopped and
  removed, is deregistered from GitHub, and has its directory deleted, exactly as `uninstall` does.
- **Busy instances are left alone.** If GitHub reports an instance busy with a job, `scale` keeps it,
  says so and exits 1. Run it again once the job is done, or pass `--force` to remove it anyway (the
  job fails). If the runner list cannot be read, `scale` warns and goes ahead.
- `scale N` with N already installed changes nothing. `scale 0` is refused: use `uninstall`.
- There is no autoscaler: you pick the maximum, and resource caps keep it from overwhelming the
  machine. Idle instances cost almost nothing (they only poll GitHub).
- `ci-runner status` shows how many instances are installed; `--dry-run` shows what `scale` would do.

## Keeping the machine usable: resource caps (Linux)

More instances means more jobs at once, and a few heavy builds at the same time can make the machine
unusable. A cap limits how much of the machine **all ci-runner instances together** may use,
however many there are and whichever repos they serve:

```bash
ci-runner install --repo OWNER/NAME --count 4 --cpu 50 --memory 60   # set while installing
ci-runner scale 6 --cpu 75                                            # or while scaling
ci-runner limits --cpu 40 --memory 50                                 # or any time later
ci-runner limits                                                      # show the current caps
ci-runner limits --cpu none                                           # remove the CPU cap
```

- `--cpu PCT`: at most PCT% of the machine's CPU time, shared. On 8 cores, `--cpu 50` means 4 cores'
  worth for all jobs together. Jobs slow down at the cap; they are not killed.
- `--memory PCT`: at most PCT% of the machine's memory, shared. A job that pushes the total over it is
  killed by the kernel's out-of-memory handling inside the slice (the rest of the machine is not
  touched), so leave room for your biggest job.
- Values are whole percentages from 1 to 100, or `none`. Passing one flag keeps the other cap.
- **How:** every runner service runs in one systemd slice, `ci-runner.slice`
  (`/etc/systemd/system/ci-runner.slice`, `CPUQuota=` PCT x cores, `MemoryMax=` PCT%). Each service
  joins it with a drop-in, `actions.runner.<...>.service.d/ci-runner-slice.conf`, written before it
  first starts. Changing a cap applies to running jobs immediately, without a restart. Writing these
  files needs sudo, like installing the service does.
- Runners installed by ci-runner 0.2.0 are moved into the slice the first time you set a cap, which
  restarts them: a job running on one at that moment is interrupted. The command names each one.
- `uninstall` and `scale` remove an instance's drop-in; the slice file stays (without members it does
  nothing). `ci-runner status` shows the caps, and `install`, `scale` and `limits` print them when
  they finish.
- **macOS:** launchd has no shared equivalent, so `--cpu`, `--memory` and `limits` print a notice and
  the rest of the command goes ahead.

## Is the repo ready? `ci-runner check`

```bash
cd your-repo && ci-runner check          # or: ci-runner check path/to/repo
```

It reads `.github/workflows/*.yml` and `*.yaml` and prints one line per finding, such as:

```
.github/workflows/ci.yml:12: warning: job 'test' runs on GitHub-hosted 'ubuntu-latest'; ...
.github/workflows/ci.yml:31: warning: sudo: the runner has no passwordless sudo; ...
.github/workflows/ci.yml:40: info: job 'mac' runs on 'macos-14', which stays GitHub-hosted (fine if intended)
```

- **Exit code:** 1 when there is any warning, 0 when there are none (info lines only, or nothing at
  all), 2 when there are no workflow files to check. It can run as a CI step.
- **Warnings** are what the checklist below describes. **Info** marks jobs on hardcoded `macos-*` or
  `windows-*` labels: they stay GitHub-hosted, which is usually intended.
- **It is a heuristic.** It reads lines and indentation rather than parsing YAML, so it can miss
  unusual layouts or report something harmless. To silence a false positive, end that line with
  `# ci-runner: ignore`. Comment lines and `select-runner.yml` itself are never reported.
- It does not follow reusable workflows or composite actions, and it cannot see Docker-based actions
  referenced by name (only `container:`, `services:` and `uses: docker://`).
- It needs nothing but the repo checkout: no `gh`, no network, and it changes nothing.

## Choosing the account

Every job runs as one account on your machine and can read whatever that account can: SSH keys,
`.env` files, other checkouts, `gh` and cloud credentials. Jobs that start tmux sessions, install
services or put mock CLIs on `PATH` also run next to your own work.

| Option | When |
|---|---|
| `install --create-user` (Linux, **recommended**) | Creates the account `ci-runner` and runs the service as it. `--run-as USER` picks another name. |
| `install --yes` | Your own account. Fine for a private repo on a machine you trust. |
| macOS | There is no `--run-as`: create a standard user, sign in as it, and run `ci-runner` there. |

With neither flag in a terminal, `install` shows this choice and asks (the dedicated account is
the default answer). Without a terminal it refuses to guess. It never runs jobs as root.

A dedicated account starts with an empty home, so tools installed under your account (cargo, nvm)
are not on its `PATH`. Install them system-wide, or for that account, and put their directory in
the runner's `.path` file (`~ci-runner/actions-runner/<repo>/.path`), then restart the service.

## Making jobs runner-safe

The repo-side checklist. A GitHub-hosted runner is a fresh, disposable VM with passwordless sudo;
your machine is none of those things. `ci-runner check` reports every item marked with a check
column entry.

| What | Why it breaks on your machine | Fix | `check` |
|---|---|---|---|
| `select-runner.yml` | Without it, jobs cannot switch between your runner and GitHub-hosted | `ci-runner workflow`, then commit it | warning |
| Hardcoded `runs-on: ubuntu-*` | The job always runs GitHub-hosted, whatever `ci-runner on` says | `needs: select-runner` and `runs-on: ${{ needs.select-runner.outputs.target }}` | warning |
| Hardcoded `macos-*` / `windows-*` | Stays GitHub-hosted (usually intended; ci-runner registers Linux and macOS machines) | Nothing, or point it at select-runner if your machine is a Mac and should take it | info |
| `sudo` | The runner account has no passwordless sudo, so the step hangs or fails | Preinstall what jobs would `apt-get`/`brew install`, and guard the step with `command -v tool \|\| ...`. Put mocks in `$RUNNER_TEMP` and add that to `$GITHUB_PATH`, never in `/usr/local/bin` | warning |
| `actions/cache`, or `cache:` on `actions/setup-*` | Downloads are slow or stall on home connections, and the disk already persists between jobs | Add `if: needs.select-runner.outputs.self-hosted != 'true'` to the step or the job | warning |
| `container:`, `services:`, `uses: docker://` | Needs Docker on your machine | Install Docker for the runner account, or keep the job GitHub-hosted | warning |
| `git config --global`, writes to `~/` or `$HOME/` | The runner account's home persists between jobs and is shared by every instance | Repo-local `git config`, `GIT_CONFIG_GLOBAL=$RUNNER_TEMP/gitconfig`, or write to `$RUNNER_TEMP` | warning |
| Fixed `/tmp/...` paths | Survive a failed run, and collide when instances run jobs at the same time | `$RUNNER_TEMP`, or `mktemp` | warning |
| `curl ... \| sh` installers | Run on every job, often need root, and change the machine for later jobs | Preinstall the tool on the machine (and on the runner account's `PATH`) | warning |

Two more that `check` cannot see:

- **Parallel jobs share the machine.** With `scale N`, N jobs run at once and share CPU, memory and
  disk; use [resource caps](#keeping-the-machine-usable-resource-caps-linux) to keep the machine
  usable. Checkout still removes ignored files in each instance's own workspace.
- **macOS.** A Mac with Homebrew's GNU tools on `PATH` hides BSD-only bugs. Keep the runner
  account's `PATH` close to stock if the job exists to catch those.

## Troubleshooting

Start with `ci-runner status`. Then open the run on GitHub: the **Decide runner** job's log says
which runner was picked and why.

| You see | Likely cause and fix |
|---|---|
| Jobs stay *Queued* | The mode is always-your-machine and no runner is online. Start the service (Linux: `systemctl status 'actions.runner.*'`; macOS: `./svc.sh status` in the runner directory), or `ci-runner on` for the fallback, or `ci-runner off`. |
| `on` is set but jobs run on GitHub-hosted | Decide runner warns that `RUNNER_STATUS_PAT` is missing, or lists no online runner. Run `ci-runner on` with a token; check that the token is scoped to this repo (or the org, with `--org-runner`). |
| No *Decide runner* job in the run | The workflow does not call `select-runner.yml`. Run `ci-runner workflow` and add the job (Quick start, step 3). |
| *Could not list runners* | The token lacks **Administration: Read-only** on this repo, or the runner is on the org and `--org-runner` was not used. |
| `command not found` for cargo, node, ... | The job account's `PATH` lacks it. Edit the runner's `.path` file and restart the service (see Choosing the account). |
| `sudo: a password is required` | A step uses sudo. Preinstall the package and guard the step. |
| macOS runner stops at night | The launchd agent runs while its user is signed in. Keep that user logged in, or use a dedicated always-on Mac. |
| The machine is sluggish while jobs run | Cap them: `ci-runner limits --cpu 50 --memory 60` (Linux), or `ci-runner scale` down. |
| A job is killed with no error of its own | The memory cap was reached by all jobs together (`journalctl -u 'actions.runner.*'` shows the out-of-memory kill). Raise it with `ci-runner limits --memory PCT` or run fewer instances. |
| `scale` exits 1 saying an instance is busy | It kept an instance that was running a job. Run it again later, or add `--force`. |
| `check` reports something harmless | It is line-based. End that line with `# ci-runner: ignore`. |
| Checksum warning during install | The release notes had no checksum for this platform, or there is no `shasum`/`sha256sum`. The download is otherwise unverified. |

## Rolling back and removing

- **Stop using it for now:** `ci-runner off`. The next run is GitHub-hosted. The runner keeps
  idling, which is harmless.
- **Fewer instances:** `ci-runner scale N`. **No caps:** `ci-runner limits --cpu none --memory none`.
- **Remove it from this machine:** `ci-runner uninstall --repo OWNER/NAME` stops the service,
  deregisters the runner and deletes its directory. Run `ci-runner off` first, or the jobs will
  queue for a runner that no longer exists.
- **Remove the workflow wiring:** point `runs-on` back at `ubuntu-latest` and delete
  `select-runner.yml`.

## How it works

- **Outbound only.** The runner long-polls GitHub over HTTPS. No static IP, port forwarding or
  inbound firewall rule.
- **Service.** Linux: a systemd service (needs `sudo` once), started on boot. macOS: a launchd
  agent that runs while that user is signed in.
- **Layout.** `~/actions-runner/<repo>` (then `<repo>-2`, ...), in the job account's home. Running
  `install` again only adds what is missing; `scale N` adds or removes to leave exactly 1..N.
- **Caps.** Linux: every instance's systemd service runs in `ci-runner.slice`, which carries the
  shared `CPUQuota` and `MemoryMax`.
- **Download check.** The `actions/runner` package's SHA-256 is compared with the checksum in its
  release notes.
- **Repo or org.** `--repo` registers the runner for one repository, and only that repository's
  jobs reach it. `--org` registers it on the organization's Default runner group, which by default
  serves the org's private repositories. The `on`/`off` variables are always per repository.
- **`ci-runner --help`** lists every option. All write commands take `--dry-run`, which also prints
  the systemd files it would write.

## Security

- **Private repositories only.** A self-hosted runner runs whatever a triggered workflow says,
  including a pull request's branch. On a public repository, or one that allows forks, that is
  anyone's code on your machine. GitHub's guidance is not to use self-hosted runners with public
  repositories. If a repo might go public, run `ci-runner off` and `ci-runner uninstall` first.
- **Use a dedicated account** when the machine holds anything you care about (see above).
- **The fallback token** can read the repo's runner list and nothing else. Keep it scoped to one
  repo, and rotate it like any token. `ci-runner` hands it to `gh secret set` on standard input,
  so it never appears in a process list or shell history.
- **Turning it off** only changes where jobs go. The service keeps polling until `uninstall`.
