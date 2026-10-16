---
name: setup
description: Move a repository's GitHub Actions jobs onto a self-hosted runner on this machine, or back to GitHub-hosted runners, with the ci-runner command, including how many runner instances run, their shared CPU and memory caps, and whether the repo's workflows are ready for it. Does not trigger for writing or debugging ordinary workflow steps, and does not trigger for GitHub-hosted runner sizing or billing questions.
---

**Usage:** `/ci-runner:setup [on | off | status | check | scale | uninstall]`

Everything is done by the `ci-runner` command; this skill is the order to run it in and the
checks to make between steps. Reference: the plugin's [README](../../README.md).

## Step 1: Make sure the command exists

Run `command -v ci-runner`. If it is missing, run the installer from the plugin's own directory,
which is the parent of this skill's `skills/` folder:

```bash
<plugin-dir>/install.sh            # links bin/ci-runner into ~/.local/bin
```

Without the plugin on disk: `git clone https://github.com/zenithml/agent-framework` and run
`agent-framework/plugins/ci-runner/install.sh`. `ci-runner` needs `gh` signed in with admin
rights on the repository.

## Step 2: Check the repository is a fit

- **Public repository, or forks allowed:** stop. A pull request from a fork would run its code on
  this machine. Self-hosted runners are for private repositories.
- Ask which account runs the jobs only if the user has not said. Recommend a dedicated one
  (`--create-user` on Linux; on macOS a separate standard user). Their own account is acceptable
  for a private repository on a machine they trust (`--yes`), but never pass `--yes` on your own.

## Step 3: Install and wire the workflows

```bash
ci-runner install --repo OWNER/NAME --create-user      # or --yes for the user's own account
ci-runner workflow                                     # writes .github/workflows/select-runner.yml
```

Then edit each workflow: add the `select-runner` job and set the other jobs' `runs-on` to
`${{ needs.select-runner.outputs.target }}` (the command prints the snippet). In jobs that can land
on the runner:

- gate `actions/cache` and `cache:` inputs on `needs.select-runner.outputs.self-hosted != 'true'`;
- remove anything that needs passwordless `sudo` (`apt-get install`, writing to `/usr/local/bin`);
  preinstall those tools on the machine and guard the step with `command -v`;
- avoid fixed paths outside the workspace, since the machine persists between jobs.

Then run `ci-runner check` in the checkout and fix each warning it prints (file:line; the README's
"Making jobs runner-safe" table has the fix for each). Info lines (hardcoded `macos-*` or
`windows-*` jobs) can stay. Repeat until it exits 0. Land the workflow change through a pull
request before turning it on.

If the user wants several jobs at once, `ci-runner scale N --repo OWNER/NAME` sets the instance
count. On Linux, cap them together so the machine stays usable, e.g. `--cpu 50 --memory 60` on
`install` or `scale`, or `ci-runner limits` later; ask for the percentages rather than picking them.

## Step 4: Turn it on or off

- `ci-runner on --repo OWNER/NAME`: the user's machine when online, else GitHub-hosted. It asks for
  the fallback token (a fine-grained token with Administration: Read-only on that repo, hidden
  input); the user can skip it, and `on` then always targets the machine, which it says.
- `ci-runner on --no-fallback`: always the machine; jobs wait in the queue while it is off.
- `ci-runner off`: back to GitHub-hosted from the next run.

Confirm with `ci-runner status` and by reading the next run's **Decide runner** job log. For
anything not working, use the README's troubleshooting table.
