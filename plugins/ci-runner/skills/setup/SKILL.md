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
rights on the repository. Always run `ci-runner` commands as the regular user (never prefix with
`sudo`); it invokes `sudo` internally only when writing systemd files.

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

If the user wants several jobs at once, `ci-runner scale N --repo OWNER/NAME` (or `--org ORG`) sets
the instance count.

### Determining optimal runner count and caps

Inspect the machine before suggesting an instance count:
- **Linux:** `lscpu | grep -E "Model name|CPU\(s\):|Thread\(s\) per core"`, `free -h`
- **macOS:** `sysctl -n hw.ncpu`, `sysctl -n hw.memsize`

**Sizing formula:**
1. **Instances:** 0.5× to 1× the physical CPU cores (or up to 0.5× logical threads). Beyond 1× physical cores, concurrent compilation/tests cause CPU context-switching thrashing and slow down all jobs.
2. **RAM:** Ensure at least 4–8 GB RAM per runner instance, plus 4–8 GB reserved for OS and desktop usage.
3. **Reference sizing:**
   - 4 cores / 8 threads, 16 GB RAM: 2–3 runners, caps: `--cpu 75 --memory 75`
   - 6 cores / 12 threads, 32–64 GB RAM: 4–6 runners, caps: `--cpu 85 --memory 80`
   - 8 cores / 16 threads, 32–64 GB RAM: 6–8 runners, caps: `--cpu 85 --memory 80`
4. **Capping on Linux:** Always cap instances together so background CI cannot freeze the machine:
   e.g. `--cpu 85 --memory 80` during `install` or `scale`, or via `ci-runner limits --cpu 85 --memory 80`.

## Step 4: Turn it on or off

- `ci-runner on --repo OWNER/NAME`: the user's machine when online, else GitHub-hosted. It asks for
  the fallback token (a fine-grained token with Administration: Read-only on that repo, hidden
  input); the user can skip it, and `on` then always targets the machine, which it says. Note: auto
  mode consumes at least 1 GitHub-hosted minute per run in private repos for the decision check.
- `ci-runner on --no-fallback`: always the machine; jobs wait in the queue while it is off. This is
  Static Mode ($0 GitHub Actions charges; no token required). For org runners, pass `--org-runner`.
  To set an organization default, set `CI_RUNNER_LABEL=self-hosted` in GitHub Org Variables.
- `ci-runner off`: back to GitHub-hosted from the next run.

Confirm with `ci-runner status` and by reading the next run's **Decide runner** job log. For
anything not working, use the README's troubleshooting table. Note that on GitHub Free organizations,
`RUNNER_STATUS_PAT` must be set per private repo if using auto-fallback.
