---
name: setup
description: Move a repository's GitHub Actions jobs onto a self-hosted runner on this machine, or back to GitHub-hosted runners, with the ci-runner command. Does not trigger for writing or debugging ordinary workflow steps, and does not trigger for GitHub-hosted runner sizing or billing questions.
---

**Usage:** `/ci-runner:setup [on | auto | off | status | uninstall]`

Everything is done by the `ci-runner` command; this skill is the order to run it in
and the checks to make between steps. Full reference: the plugin's
[README](../../README.md).

## Step 1: Make sure the command exists

Run `command -v ci-runner`. If it is missing, install it from the plugin's own
directory, which is the parent of this skill's `skills/` folder:

```bash
<plugin-dir>/install.sh            # links bin/ci-runner into ~/.local/bin
```

Without the plugin on disk: `git clone https://github.com/zenithml/agent-framework`
and run `agent-framework/plugins/ci-runner/install.sh`.

`ci-runner` needs `gh` signed in with admin rights on the repository.

## Step 2: Decide where the runner runs, and say so

Ask the user only what changes the outcome:

- **Which account.** Jobs can read everything the runner's account can. Default to
  a dedicated account: on Linux `ci-runner install --run-as ci-runner` (create it
  with `sudo useradd --create-home --shell /bin/bash ci-runner`); on macOS sign in
  as a separate standard user and run `ci-runner` there. Never pass `--yes` to
  install under the user's own account unless they said so.
- **Public repository or forks allowed:** stop. A pull request from a fork would run
  its code on this machine. Self-hosted runners are for private repositories.

## Step 3: Install and wire the workflows

```bash
ci-runner install --repo OWNER/NAME [--run-as ci-runner]
ci-runner workflow                     # writes .github/workflows/select-runner.yml
```

Then edit each workflow: add the `select-runner` job and set the other jobs'
`runs-on: ${{ needs.select-runner.outputs.target }}` (the command prints the
snippet). In jobs that can land on the runner:

- gate `actions/cache` and `cache:` inputs on
  `needs.select-runner.outputs.self-hosted != 'true'`;
- remove anything that needs passwordless `sudo` (`apt-get install`, writing to
  `/usr/local/bin`); preinstall those tools on the machine and guard the step
  with `command -v`;
- avoid fixed paths outside the workspace, since the machine persists between jobs.

Land the workflow change through a pull request before switching.

## Step 4: Switch

`ci-runner auto --repo OWNER/NAME` (self-hosted when online, else GitHub-hosted;
needs the `RUNNER_STATUS_PAT` secret, and the command prints how to make it) or
`ci-runner on` (always self-hosted). `ci-runner off` goes back. Confirm with
`ci-runner status` and by watching the next run's "Decide runner" job.
