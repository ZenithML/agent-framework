# ci-runner

Run a repository's GitHub Actions jobs on your own Linux or macOS machine, and switch
between that machine and GitHub-hosted runners without editing workflows.
Generalised from ZenithML/zenith's `self-hosted-runner/` scripts.

## Install the command

```bash
git clone https://github.com/zenithml/agent-framework.git
./agent-framework/plugins/ci-runner/install.sh     # links ci-runner into ~/.local/bin
```

As a Claude Code plugin, `/plugin install ci-runner@sdd-harness` adds the
`/ci-runner:setup` skill, which runs the same command. Requirements: `gh` signed in
with admin rights on the repository, `curl`, `tar`, and bash 3.2 or later.

## Use it

```bash
# 1. On the machine that will run jobs (as a dedicated account, see Security)
ci-runner install --repo OWNER/NAME --run-as ci-runner

# 2. In the repository: add the reusable workflow, then point jobs at it
ci-runner workflow
#   jobs:
#     select-runner:
#       uses: ./.github/workflows/select-runner.yml
#       secrets: inherit
#     test:
#       needs: select-runner
#       runs-on: ${{ needs.select-runner.outputs.target }}

# 3. Switch (repository variables; takes effect on the next run)
ci-runner auto --repo OWNER/NAME   # self-hosted when online, else GitHub-hosted
ci-runner on   --repo OWNER/NAME   # always self-hosted; jobs wait if the machine is off
ci-runner off  --repo OWNER/NAME   # back to GitHub-hosted

ci-runner status --repo OWNER/NAME
ci-runner uninstall --repo OWNER/NAME
```

Every command takes `--dry-run`. `ci-runner --help` lists all options.

| Variable | Set by | Effect |
|---|---|---|
| `CI_RUNNER_LABEL` | `on` (or `auto --label`) | Runner label jobs target |
| `CI_RUNNER_AUTO=true` | `auto` | Live check per run, falls back to `hosted` (default `ubuntu-latest`) |
| `CI_RUNNER_SCOPE=org` | you | With `auto`: look the runner up on the organization |
| `RUNNER_STATUS_PAT` (secret) | you | Token that can list runners; `auto` needs it because `GITHUB_TOKEN` cannot. Fine-grained, this repo, **Administration: Read-only** |

## How it works

- **Outbound only.** The runner long-polls GitHub over HTTPS. No static IP, port
  forwarding or inbound firewall rule.
- **Service.** Linux: a systemd service (`svc.sh`, needs sudo once), started on boot.
  macOS: a launchd agent that runs while that user is signed in.
- **Layout.** `~/actions-runner/<repo>` (then `<repo>-2`, ...) in the runner account's
  home. `--count N` adds instances; each runs one job at a time. Re-running `install`
  only adds what is missing.
- **Download check.** The `actions/runner` package's SHA-256 is checked against the
  checksum in its release notes.
- **Repo or org.** `--repo` registers the runner on one repository, and only that
  repository's jobs reach it. `--org` registers it on the organization's Default
  runner group, which by default serves the org's private repositories. The switch
  variables stay per repository either way.

## Making jobs runner-safe

- **No passwordless sudo.** Preinstall what jobs `apt-get`/`brew install`, and guard
  those steps with `command -v tool || ...`. Never write to `/usr/local/bin` from a job;
  put mocks in `$HOME/<dir>` and add it to `$GITHUB_PATH`.
- **Skip `actions/cache` on the runner.** Its downloads are slow or stall on home
  connections, and the runner's disk already persists between jobs:
  `if: needs.select-runner.outputs.self-hosted != 'true'`.
- **The machine is not wiped.** Fixed paths such as `/tmp/test-x` survive a failed
  run; clean them up first or use `$RUNNER_TEMP`.
- **Docker actions** need Docker on the machine; keep those jobs GitHub-hosted if it
  isn't installed.
- **macOS.** A Mac with Homebrew GNU tools on `PATH` hides BSD-only bugs. Keep the
  runner account's `PATH` close to stock if the job exists to catch them.

## Security

- **Private repositories only.** A self-hosted runner runs whatever a triggered
  workflow says, including a pull request's branch. On a public repository, or one
  that allows forks, that is anyone's code on your machine. GitHub's guidance is not
  to use self-hosted runners with public repositories.
- **Use a dedicated account.** Jobs can read everything the runner's account can:
  SSH keys, `.env` files, other checkouts, `gh` and cloud credentials. Tests that start
  tmux sessions, install services or put mock CLIs on `PATH` would also run alongside
  your own work. `install` asks before using your own account (`--yes` skips the
  question); `--run-as USER` on Linux installs and runs the service as `USER`.
- **Turning it off** (`ci-runner off`) only changes where jobs go. The service keeps
  polling until you run `ci-runner uninstall`.
