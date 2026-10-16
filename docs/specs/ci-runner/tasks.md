# ci-runner: scale, resource caps and workflow readiness — Tasks

**Source:** [requirements.md](requirements.md) | [design.md](design.md)
**Last Updated:** 2026-10-16

Per-task issues are not used for this domain; the PR links the spec.

## Tasks

- [ ] 1. Caps core: `--cpu`/`--memory` parsing and validation, slice file write/read, `ci-runner limits` (show, set, `none`, live apply), macOS notice, dry-run file printing; tests with stubbed `sudo`/`systemctl`/`nproc`/`uname` (S11–S14, S16, S25)
- [ ] 2. Slice membership: `install_one` writes the drop-in between `svc.sh install` and `start`, `install --cpu/--memory`, `join_existing` for instances outside the slice, drop-in removal in the shared `remove_instance` (extracted from `cmd_uninstall`); tests (S10, S15, S18)
- [ ] 3. `ci-runner scale N`: positional N, `find_base`, account and label inference, busy check with `--force`, remove highest first via `remove_instance`, add via `install_one`, caps flags; tests (S1–S9)
- [ ] 4. Closing next steps for install, scale and limits; status shows instance count and caps; tests (S17, S24)
- [ ] 5. `ci-runner check [DIR]`: rules R1–R9, ignore marker, comment and select-runner.yml skipping, sorted file:line output, exit 0/1/2; fixture workflows and tests (S19–S23)
- [ ] 6. Docs and release: usage text, README sections for scale, caps/limits and check plus the runner-safe checklist, `docs/plugins.md`, `/ci-runner:setup` skill, version 0.3.0 in the script, plugin.json and marketplace.json
