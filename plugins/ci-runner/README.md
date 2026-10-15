# ci-runner

Run a repository's GitHub Actions jobs on your own Linux or macOS machine, and switch between
that machine and GitHub-hosted runners with one command. Generalised from ZenithML/zenith's
`self-hosted-runner/` scripts.

```
ci-runner on      # jobs use your machine when it is online, else GitHub-hosted
ci-runner off     # back to GitHub-hosted runners
ci-runner status  # what is on, what is online, what is missing
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

# 3. Wire the repo's workflows to it (once per repo), then commit
cd your-repo && ci-runner workflow
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

Until step 4, nothing changes: jobs keep running on GitHub-hosted runners.

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

No token? `ci-runner on` still works, in the `--no-fallback` mode, and tells you so. Run it again
with a token later to add the fallback. For a runner registered on an organization
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

- **No passwordless sudo.** Preinstall what jobs would `apt-get` or `brew install`, and guard those
  steps with `command -v tool || ...`. Never write to `/usr/local/bin` from a job; put mocks in
  `$RUNNER_TEMP` and add that to `$GITHUB_PATH`.
- **Skip `actions/cache` on the runner.** Its downloads are slow or stall on home connections, and
  the runner's disk already persists between jobs:
  `if: needs.select-runner.outputs.self-hosted != 'true'`.
- **The machine is not wiped.** Fixed paths such as `/tmp/test-x` survive a failed run; clean them
  up first or use `$RUNNER_TEMP`. Checkout still removes ignored files in the workspace.
- **Docker actions** need Docker on the machine; keep those jobs GitHub-hosted if it is not there.
- **One job at a time per runner.** `install --count N` adds instances if jobs need to run in
  parallel, but jobs then share the machine's CPU, and jobs with fixed paths can collide.
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
| Checksum warning during install | The release notes had no checksum for this platform, or there is no `shasum`/`sha256sum`. The download is otherwise unverified. |

## Rolling back and removing

- **Stop using it for now:** `ci-runner off`. The next run is GitHub-hosted. The runner keeps
  idling, which is harmless.
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
  `install` again only adds what is missing.
- **Download check.** The `actions/runner` package's SHA-256 is compared with the checksum in its
  release notes.
- **Repo or org.** `--repo` registers the runner for one repository, and only that repository's
  jobs reach it. `--org` registers it on the organization's Default runner group, which by default
  serves the org's private repositories. The `on`/`off` variables are always per repository.
- **`ci-runner --help`** lists every option. All write commands take `--dry-run`.

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
