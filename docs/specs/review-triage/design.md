# Review triage — Design

**Status:** Approved
**Last Updated:** 2026-10-20

Source: [requirements.md](requirements.md).

## Decision

**Build risk triage that produces an ordered review path with a focus checklist.** It ships as
one skill, `/sdd:triage-pr`, backed by one deterministic script.

The user describes two failures. The first is that reviewers cannot tell which part of too much
diff matters. The second is that they skip at random and approve anyway. Inline review comments
already exist, so a missing comment tool is not the problem.

Triage fixes the first failure directly. It cuts the diff into three parts: *read this
closely*, *review normally*, and *safe to skip, because …*.

The ordered path and the checklist fix the second failure cheaply. The reviewer starts with the
part that matters. A partial review then has a visible shape, the unticked focus items, instead
of looking the same as a full one.

### Alternatives considered

| Direction | Why not (now) |
|---|---|
| **Track what the reviewer actually looked at** | GitHub's GraphQL API exposes the per-file "Viewed" state only to the viewer who set it (`viewerViewedState`), so a team cannot see what another reviewer looked at. Git records nothing. "Viewed" is also a click, as easy to fake as an approval. Real tracking needs a browser extension or a custom review UI, and a Claude Code plugin cannot ship either. The checklist gives the useful half, declared coverage, without surveillance. |
| **Per-hunk attestation that gates approval** | Gating a human's approval needs a required status check and a bot account in every consuming repo. It also invites the behaviour it targets: ticking boxes without reading. What changes behaviour is making the skip *visible*, so enforcement is left out on purpose. |
| **Split the diff into a guided multi-step walkthrough** | Useful, but it is an interactive session that the agent drives hunk by hunk. That makes a large skill with no deterministic core to test. The ordered path here is the static version of a walkthrough, and a walkthrough mode can be built on the same JSON later. |
| **Backlog triage across many PRs** | Ranking PRs still leaves the overload problem inside every PR in the ranking. Per-PR triage is the building block, and its JSON output is the interface a backlog view would consume. |
| **Let the agent judge risk with no script** | Not repeatable and not testable. An agent under the same overload pressure can also quietly call a risky hunk "fine". The script sets a floor the agent cannot lower: it can promote hunks but never demote them. |
| **Extend `/sdd:review-pr` instead of a new skill** | review-pr's contract is "an agent leaves comments". Triage serves the *human* reviewer and runs before any review. Folding it into review-pr would blur two triggers that the description gate keeps apart, so review-pr gets a one-line pointer instead. |

## Architecture

### Component Design

| Component | Path | Role |
|---|---|---|
| Triage script | `plugins/sdd/skills/triage-pr/scripts/triage.py` | Parses a unified diff, tiers each hunk, and prints markdown or JSON. Standard library only. |
| Skill | `plugins/sdd/skills/triage-pr/SKILL.md` | Gets the diff, runs the script, reads every focus hunk and adds a `check:` line, re-runs with `--promote` when needed, and can post or update the PR comment. |
| Baseline evals | `plugins/sdd/skills/triage-pr/evaluations/baseline-evals.json` | Three scenarios: the happy path; the gate (`--comment` with no PR); and the signature failure, where the agent hand-moves a focus hunk to a lower tier to make the review look smaller. |
| Tests | `tests/triage-pr.sh` runs `tests/triage-pr/test_triage.py`; fixtures are in `tests/triage-pr/fixtures/` | Standard-library `unittest` against fixture diffs. Runs in the `gates` CI job. |

Script functions:

| Function | Role |
|---|---|
| `parse_diff(text)` | Parses the diff into files and hunks (see Parsing). Raises `DiffError` when the input is non-empty but has no `diff --git` header, or when it contains a combined diff (`diff --cc` / `diff --combined`). |
| `load_rules(path)` | Reads the optional JSON rules file. The file must be an object whose only keys are `focus_paths`, `low_paths` and `focus_patterns`, each a list of regex strings that compile. Otherwise raises `RulesError` naming the file, the key and the problem. |
| `path_focus_reasons(f, rules)` | Returns the focus reasons that come from the path (see Rules: path focus). |
| `file_low_reason(f, rules)` | Returns the low reason for a whole file, or `None`. |
| `hunk_focus_reasons(f, hunk, rules)` | Returns the content and test-weakening reasons for one hunk. |
| `is_whitespace_only(f, hunk)` | Applies the whitespace-only rule. |
| `triage(files, rules, promotions)` | Builds the ordered items and the summary. |
| `render_markdown(result, previous=None)` / `render_json(result)` | Produces the output. `previous` is the body of an earlier triage comment, used to carry ticks over. |
| `main(argv)` | Takes `--diff FILE` (default stdin), `--rules FILE`, `--format markdown|json`, `--promote FILE:LINE=REASON` (repeatable) and `--previous FILE`. Exits 0 on success, 2 on a usage error, a bad rules file, a bad promotion, or input that is not a diff. |

### Parsing

- **Sections.** Each file section starts at a `diff --git` line.
- **Paths.** Paths come from the `rename from` / `rename to` lines when present, otherwise from
  `--- a/X` and `+++ b/Y` (`/dev/null` marks an added or deleted file). The `diff --git a/X b/Y`
  header is used only when neither is present, for binary files and mode-only changes, and then
  by splitting on ` b/`. A path in double quotes is unquoted by Python string-literal rules
  (`\t`, `\"`, `\\`, octal escapes).
- **Status.** `added` comes from `new file mode`, `deleted` from `deleted file mode`, and
  `renamed` from `rename from`. Anything else is `modified`.
- **Other flags.** `similarity` is the integer from `similarity index N%`. `binary` is set by a
  `Binary files … differ` line or a `GIT binary patch` line. `mode_changed` is set by an
  `old mode` / `new mode` pair.
- **Hunks.** A hunk starts at `@@ -a[,b] +c[,d] @@`. Its body is the lines that follow, up to
  the next `@@` or `diff --git`. In the body, a line starting with `+` is added and a line
  starting with `-` is removed. Lines starting with a space are context, and lines starting with
  `\` are ignored. `+++` and `---` lines appear only before the first `@@` of a file, so they are
  headers and are never counted.
- **Hunk record.** Each hunk keeps `header` (the full `@@` line), `old_start` (a), `new_start`
  (c), and its added and removed line texts with the first character stripped.

### Data Model

There is one item per focus hunk, one per standard file, and one per low file:

```json
{
  "tier": "focus | standard | low",
  "file": "src/auth/session.ts",
  "old_file": "src/auth/old.ts",
  "line": 42,
  "hunks": 1,
  "added": 12,
  "removed": 3,
  "reasons": ["sensitive path: auth", "adds eval("]
}
```

- **`line`.**
  - For a focus hunk, `line` is the hunk's `new_start`. For a deleted file it is `old_start`.
  - For a no-hunk item, and for every standard or low item, `line` is `null`.
- **`old_file`.** Present only on renames.
- **`hunks`.** For standard and low items, `hunks` counts the hunks in that item, and
  `added`/`removed` sum over them.
- **`reasons`.**
  - Standard items carry `[]`, except a binary file, which carries `["binary"]`. That reason is
    a note: no rule fired.

The result:

```json
{
  "summary": {
    "files": 20, "changed_lines": 1840,
    "focus":    {"items": 4,  "lines": 96},
    "standard": {"items": 6,  "lines": 210},
    "low":      {"items": 10, "lines": 1534}
  },
  "items": [ ...ordered... ]
}
```

- **Totals.**
  - `changed_lines` is added plus removed over every hunk.
  - An item's lines are its added plus removed.
  - The three tier `lines` totals always sum to `changed_lines`.
- **Splitting.**
  - A file can contribute to several tiers. Its focus hunks become focus items. Its
    whitespace-only hunks become at most one low item with the reason `whitespace only`. Its
    remaining hunks become at most one standard item.
  - For that reason the tier item counts can sum to more than `summary.files`.

The repo rules file is `.claude/sdd/review-triage.json`. Every key is optional:

```json
{
  "focus_paths": ["^ledger/", "config\\.schema\\.json$"],
  "low_paths": ["^docs/generated/"],
  "focus_patterns": ["\\bfeature_flag\\("]
}
```

### Rules

- **Case.** Built-in regexes are case-insensitive. Repo regexes are applied exactly as written,
  so they are case-sensitive unless they begin with `(?i)`.
- **Paths.** Path regexes use `search` against the file's path. For a rename they are tested
  against both the old and the new path. For a deletion the path is the old path.
- **Whole-file low and test-file checks.** These use the file's path only: the new path, or the old path for a deletion. On a rename the old path is not consulted.
- **Content.** Content patterns are matched against **added** lines only. The one exception is
  the test-weakening rule `removes assertions`, which also reads removed lines.
- **Reasons.**
  - Each reason appears once per item, however many lines or paths match.
  - Reasons are ordered as the tables list them: path reasons, then content reasons, then
    test-weakening reasons, then repo rules last within each group.

**Path focus** applies to every hunk of the file:

| Reason | Path regex |
|---|---|
| `sensitive path: <word>` | `(auth|login|session|passw|secret|token|credential|crypto|permission|acl|security|sanitiz|payment|billing)`. `<word>` is the lower-cased text of the leftmost match. A path yields at most one such reason; on a rename, the new path is tried first. |
| `migration or schema` | `(^|/)migrations?/`, `\.sql$`, `(^|/)schema\.[a-z]+$` |
| `CI or deploy config` | `(^|/)\.github/workflows/`, `(^|/)Dockerfile`, `\.tf$`, `(^|/)\.gitlab-ci\.yml$`, `(^|/)Jenkinsfile$` |
| `env file` | `(^|/)\.env(\.|$)` |
| `deletes test file` | The status is deleted and the path is a test file. |
| `repo rule: <regex>` | A repo `focus_paths` entry matches. |

A test file is one whose path matches `(^|/)(tests?|__tests__|spec)/`, or whose basename
matches `^test_.*\.py$`, `_test\.(py|go)$` or `\.(test|spec)\.[a-z]+$`.

**Low (whole file).** The first match wins:

| Reason | Condition |
|---|---|
| `lockfile` | The basename is one of `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, `Pipfile.lock`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`, `go.sum`, `bun.lockb`, `flake.lock`. |
| `generated or vendored` | The path matches `(^|/)(dist|build|vendor|node_modules|third_party|__generated__|generated)/`, `\.min\.(js|css)$`, `\.snap$`, `\.pb\.go$`, `_pb2(_grpc)?\.py$` or `\.generated\.` |
| `repo rule: <regex>` | A repo `low_paths` entry matches. |
| `pure rename` | The file is renamed and has no hunks, whatever its similarity and even if its mode also changed. |
| `mode change only` | The mode changed, the file has no hunks, and it is not a rename. |
| `empty file` | The file was added or deleted, has no hunks, and is not binary. |

**Content focus** is per hunk. Inside this table, `|` inside a regex is alternation; a literal
pipe is written out in words.

| Reason | Added-line regex |
|---|---|
| `adds eval(` / `adds exec(` | `\beval\(` / `\bexec\(` |
| `adds shell execution` | `shell\s*=\s*True`, `os\.system\(`, `child_process`, `subprocess\.` |
| `adds rm -rf` | `rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r` |
| `adds sudo` | `\bsudo\b` |
| `adds pipe-to-shell` | `curl` or `wget`, then a literal pipe later on the same line, then optional whitespace, then `sh`, `bash` or `zsh` as a word. |
| `adds destructive SQL` | `\b(DROP|TRUNCATE)\s+(TABLE|DATABASE)\b`, `\bDELETE\s+FROM\b`, `\bALTER\s+TABLE\b` |
| `adds unsafe deserialisation` | `pickle\.loads?\(`, `yaml\.load\((?![^)]*SafeLoader)`, `\bunserialize\(` |
| `adds raw HTML injection` | `innerHTML\s*=`, `dangerouslySetInnerHTML` |
| `disables verification` | `verify\s*=\s*False`, `--no-verify`, `rejectUnauthorized\s*:\s*false`, `InsecureSkipVerify\s*:\s*true` |
| `adds force flag` | `--force\b` |
| `widens CI permissions` | `continue-on-error\s*:\s*true`, `permissions\s*:\s*write-all`, `\bpull_request_target\b` |
| `suppresses a check` | `#\s*noqa`, `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `#\s*type:\s*ignore`, `//\s*nolint`, `pragma:\s*no\s*cover`, `#\s*nosec` |
| `repo rule: <regex>` | A repo `focus_patterns` entry matches. |

**Test weakening** is per hunk and applies to test files only:

| Reason | Condition |
|---|---|
| `removes assertions` | More removed lines than added lines match `\b(assert\w*|expect|should|verify)\b`. |
| `adds skip marker` | An added line matches `\.(skip|only)\(`, `@pytest\.mark\.(skip|xfail)`, `\bxit\(`, `\bxdescribe\(`, `@Disabled\b`, `@Ignore\b`, `\bt\.Skip\(` or `unittest\.skip`. |

**Whitespace-only hunk.** Take the hunk's removed lines and its added lines, each in order, and
drop the blank ones.

- **Normalisation.** In each remaining line, replace every run of whitespace with one space and
  strip both ends. For indentation-significant files (`.py`, `.yaml`, `.yml`, `Makefile`,
  `.mk`), strip only trailing whitespace instead.
- **Test.** The hunk is whitespace-only when it has at least one added or removed line and the
  two normalised sequences are equal in order. A hunk that only adds or removes blank lines is
  whitespace-only. A hunk that reorders lines is not.

### Tiering (deterministic order of checks)

For each file:

1. **Path focus.** Compute the path focus reasons `P`.
2. **Whole-file low.** If `P` is empty and `file_low_reason` is set, the file becomes one low
   item, and its content is never scanned. A low reason never overrides a path focus reason.
   That holds even for repo `low_paths`.
3. **No-hunk files.** If the file has no hunks: when `P` is non-empty it becomes one focus item
   (`line` is `null`); when it is binary it becomes one standard item with the reason `binary`.
   No other case is possible, because every remaining no-hunk file has a low reason.
4. **Hunks.** Otherwise, check each hunk in order:
   - If it is whitespace-only, it goes to the low remainder. Whitespace-only beats both path
     and content focus.
   - Otherwise its reasons are `P` plus `hunk_focus_reasons`. If there are any, the hunk
     becomes a focus item. If not, it goes to the standard remainder.
5. **Promotions.** For each `--promote FILE:LINE=REASON`, find the hunk of `FILE` whose
   `new_start` (or `old_start` for a deleted file) equals `LINE`.
   - If that hunk is in a remainder, move it out into its own focus item with the reason
     `promoted: REASON`.
   - If it is already focus, append `promoted: REASON` to its reasons.
   - If no hunk matches, exit 2, naming the argument.
6. **Remainders.** Each non-empty remainder becomes one item.

Ordering (string comparison is Python's default code-point order on the new path):

- **Focus.** Items are grouped by file. Groups are ordered by the highest reason count among
  their items, descending, then by path. Within a group, items are ordered by `line`, with
  `null` first.
- **Standard.** Ordered by lines, descending, then by path.
- **Low.** Ordered by path.

### Markdown

The markdown has this exact shape. Numbers have no thousands separator.

```
<!-- sdd:triage-pr -->
## Review triage

20 files, 1840 changed lines.
**Read closely: 4 hunks, 96 lines.** Review normally: 6 files, 210 lines. Safe to skip: 10 files, 1534 lines.

### 1. Read closely
- [ ] `src/auth/session.ts` L42 (+12 −3) — sensitive path: auth; adds eval(
- [ ] `src/old/x.py` → `src/auth/x.py` (+0 −0) — sensitive path: auth

### 2. Review normally
- `src/lib/cart.ts` (+20 −4, 2 hunks)
- `assets/logo.png` (binary)

### 3. Safe to skip
- `package-lock.json` (+900 −600) — lockfile

### Coverage
Tiers come from path and content heuristics, not from understanding the code. "Review normally"
is not "safe": nothing fired there, which is all the triage claims. Tick each item in section 1
as you read it. An item still unticked when you approve was not reviewed — say so in the review
instead of approving silently.
```

- **File names.** A rename prints `` `old` → `new` ``.
- **`L` part.** The ` L<line>` part is printed only when `line` is not null.
- **Standard items.** These print `(+a −r, N hunks)`, with `hunk` when N is 1. A binary file
  prints `(binary)`.
- **Empty sections.** An empty section prints `_None._`.
- **Empty diff.** Markdown prints `Nothing to triage: the diff is empty.`; JSON prints the result with every count 0 and `items: []`. Both exit 0.
- **Minus sign.** The minus is U+2212, so that `-3` cannot read as a list marker.
- **Agent lines.** The skill appends a `  check: …` line under each focus item before showing
  or posting the output. JSON does not carry `check:` lines; they are the agent's reading
  notes, not tiers.

**Carrying ticks over (`--previous FILE`).** A re-run against a PR whose comment already holds
ticks must not wipe them.

- **Matching.** For each focus line, the script looks in the previous body for the same line
  text after the checkbox, comparing whole lines and ignoring `check:` lines. If that line was
  `- [x]` (or `- [X]`), the new line is ticked.
- **Changes.** When anything on the line changes (line number, counts, reasons), the tick
  drops. That is intended: changed code needs reading again.

### Skill flow (`/sdd:triage-pr [PR-number] [--base REF] [--comment]`)

1. **Source.**
   - Given a PR number, use `gh pr diff N`.
   - Given neither a number nor `--base`, use the current branch's PR, from
     `gh pr view --json number`.
   - With no PR, use `git diff <base>...HEAD`, where `<base>` is `--base` or `<MAIN_BRANCH>`.
   - `--comment` with no PR is refused, with the reason.
2. **Rules.** Pass `--rules .claude/sdd/review-triage.json` when that file exists.
3. **Previous comment.** When `--comment` is set, look up the current user with
   `gh api user --jq .login`. Among the PR's issue comments
   (`gh api repos/{owner}/{repo}/issues/N/comments --paginate`), find the most recent one whose
   author is that user and whose body starts with `<!-- sdd:triage-pr -->`. If found, save its
   body to a temp file and pass it as `--previous`.
4. **Run.** Run the script. If it exits 2, show the message and stop.
5. **Read.**
   - Read every focus hunk in the diff and write `  check: <one concrete question the human
     should answer>` under it.
   - While reading the standard files, a hunk may carry a risk the rules do not cover, for
     example a changed authorisation check in a file with a neutral name. For each such hunk,
     re-run the script with `--promote FILE:LINE=<reason>`, then redo the check lines.
   - Never edit tiers, counts or reasons by hand. The script has no demote option, and the
     skill must not move a line out of section 1.
6. **Output.**
   - With `--comment`, PATCH the comment found in step 3, or POST a new one when there is none.
     Then print the comment URL.
   - Otherwise, print the triage. The skill never approves, requests changes, or edits code.

## Test Scenarios

`tests/triage-pr/test_triage.py` uses standard-library `unittest` and is run by
`tests/triage-pr.sh`:

| # | Scenario | Asserts |
|---|---|---|
| T1 | Parsing: modified, added, deleted, renamed (100% with no hunks, 87% with hunks), binary, mode-only, quoted path, `\ No newline`, a `+++` header not counted | Status, paths, similarity, hunk starts, and added/removed counts |
| T2 | Lockfile (modified and deleted), generated, vendored, `.min.js`, `.snap` | Low with the right reason. Not content-scanned: an `eval(` inside stays low. |
| T3 | Pure rename, rename plus mode change, mode change only, empty added file | Low with `pure rename`, `pure rename`, `mode change only`, `empty file` |
| T4 | Sensitive path | Every non-whitespace hunk is focus with `sensitive path: auth`; one reason even when the path matches twice |
| T5 | Path focus beats low (`vendor/auth/x.js`); repo `low_paths` does not beat a built-in path focus | Focus |
| T6 | Rename with edits from `auth/a.py` to `util/a.py`; a no-hunk rename into `auth/` | Focus via the old path; a focus item with `line` null, printed without `L` |
| T7 | Each content rule fires on an added line, and not on a removed or context line | The reason is present or absent |
| T8 | Test weakening: removed asserts, each skip marker, a deleted test file; adding asserts does not fire | Reasons |
| T9 | Whitespace: a re-indent in `.js` (low); a re-indent in `.py` (not low); a blank-lines-only hunk (low); reordered lines (not low); a re-indented `eval(` line in `.js` (low) | Tiers; the file splits into standard and low items; totals add up |
| T10 | Binary file | Standard with `binary`; markdown prints `(binary)` |
| T11 | Ordering | Focus grouped by file and ranked by highest reason count; standard by size; low by path |
| T12 | Repo rules: `focus_paths`, `low_paths`, `focus_patterns`, case sensitivity; invalid JSON, an unknown key, a non-list value, a bad regex | Reasons; exit 2 with the file and key named |
| T13 | `--promote`: a standard hunk moves to focus and the counts move with it; an already-focus hunk gains the reason; an unknown FILE:LINE exits 2 | Items, summary, JSON carries `promoted:` |
| T14 | `--previous`: an unchanged ticked line stays ticked; a changed line loses its tick; an unticked line stays unticked | Markdown |
| T15 | Empty input; non-diff input; combined diff | Exit 0 with a message; exit 2; exit 2 |
| T16 | Markdown golden output for a mixed fixture | Byte-identical to `fixtures/mixed.expected.md` |
| T17 | JSON output | Parses; tier lines sum to `changed_lines`; items match the summary counts |
| T18 | Determinism | Two runs are identical |
| T19 | CLI via subprocess: `--diff`, stdin, `--format json`, `--rules`, a bad flag | Exit codes and output |

## QA Scenarios

Run the script as a user would, through its command line only. The tester builds each diff in a
fresh temporary git repository (`git init`, commit a base, change files, `git diff`), so every
scenario can be reproduced.

| # | Scenario | Pass when |
|---|---|---|
| Q1 | Base commit with `src/app.js`; change one function body | Markdown starts with the marker and has the counts line, the three numbered sections and Coverage; `src/app.js` is under section 2 |
| Q2 | Change `package-lock.json`, and add `subprocess.run(cmd, shell=True)` to `src/auth/login.py` | The lockfile is under section 3 with `lockfile`. The login hunk is a `- [ ]` line in section 1 with `sensitive path: auth` and `adds shell execution`. |
| Q3 | In `tests/test_cart.py`, remove two `assert` lines; add `@pytest.mark.skip` in another test; delete a third test file | All three are in section 1, with `removes assertions`, `adds skip marker` and `deletes test file`. |
| Q4 | Re-indent a block in `src/util.js`; rename a file unchanged; add a file under `dist/` | All are in section 3, with `whitespace only`, `pure rename`, `generated or vendored`. |
| Q5 | Rules file `{"focus_paths": ["^ledger/"]}`; change `ledger/rates.py` | Section 1, with exactly one reason: `repo rule: ^ledger/` |
| Q6 | Rules file with `{"focus_paths": ["("]}` | Exit 2; the message names the file and `focus_paths` |
| Q7 | Empty stdin; a plain text file that is not a diff | Exit 0 with "Nothing to triage"; exit 2 |
| Q8 | The Q2 diff with `--format json` | Valid JSON; the tier lines sum to `changed_lines` |
| Q9 | Q1 diff with `--promote src/app.js:<line>=changes pricing` | That hunk moves to section 1 with `promoted: changes pricing` |
| Q10 | Save the Q2 markdown, change its first `- [ ]` to `- [x]`, and re-run with `--previous` | That line is printed `- [x]` |

The steps that need GitHub (Stories 8 and 9: posting or updating the comment, and refusing
`--comment` without a PR) are skill behaviour. Baseline evals 001 and 002 cover them, and they
are checked by hand on this PR. Story 7's never-demote rule is covered by eval 003.
