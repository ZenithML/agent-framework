# learn

Learn any subject with an AI tutor that tracks what you actually know.

Most AI study tools generate content and chat. This plugin covers the rest of the learning
loop: a goal, placement, a plan sized to your time, tutoring that makes you do the thinking,
grading against objective checks, spaced review, and honest progress. Everything rests on one
learner model that records graded evidence and derives mastery from it, so an AI's impression
that you "get it" never counts.

## Install

```
/plugin install learn --marketplace ZenithML/agent-framework
```

Or from a checkout: `/plugin marketplace add /path/to/agent-framework`, then
`/plugin install learn@sdd-harness`.

## Skills

| Skill | Does |
|---|---|
| `/learn:learn` | Entry point: finds the learner, reports progress, routes to the right skill |
| `/learn:learn-goal` | Turns an aim into can-do outcomes, a date, a time budget and a success test |
| `/learn:learn-diagnose` | Adaptive placement, at most ten items, no teaching |
| `/learn:learn-session` | Plans the session (due reviews, then new concepts), tutors with a hint ladder, grades and records |
| `/learn:learn-eval` | Content gate plus three simulated learners scored against the tutoring standard |

Standards: [learner model](standards/learner-model.md) and [tutoring](standards/tutoring.md).

## The first subject: cyber resilience (SOC, SIEM, NDR)

`packs/soc-foundations` has 12 concepts and 31 items: log sources, Windows logon and process
events, network logs, searching and aggregating like a SIEM, MITRE ATT&CK mapping, alert
triage, Sigma rules, password-spray and beaconing detection, and the first hour of an
incident.

Answers are graded objectively wherever possible:

| Item type | Graded by |
|---|---|
| `choice` | the keyed option |
| `hunt` | the answer computed from the generated data (an IP, a user, a count) |
| `sql-detect` | running the learner's SQL over labelled logs: every malicious entity caught, false positives under a cap |
| `sigma` | converting the learner's Sigma rule with pySigma's SQLite backend and running it over labelled logs |
| `order` | key orderings of incident-response steps (contain before recover, and so on) |

The logs are synthetic and generated per seed, so every retry after a success uses fresh
data with different hosts, users and addresses. The content is defensive only.

## The command line

The skills drive `scripts/learn.py` (Python 3 standard library). You can use it directly:

```bash
LEARN="python3 plugins/learn/scripts/learn.py"
$LEARN init --pack soc-foundations
$LEARN goal set --statement "Work a SOC queue" --concepts soc.detect.spray,soc.ndr.beacon --target-date 2027-01-31
$LEARN diagnose                       # next placement item
$LEARN item spray-2                   # show an item; --tutor adds hints and the reference
$LEARN query --item spray-2 "SELECT IpAddress, COUNT(*) FROM auth GROUP BY 1"
$LEARN grade spray-2 --answer "SELECT ..." --hints 1 --confidence 0.6
$LEARN status                         # mastery per concept, replayed from evidence
$LEARN plan                           # next session
$LEARN pack check soc-foundations     # content gate
```

State lives in `$LEARN_HOME`, or `./.learn` when unset.

Grading Sigma needs [pySigma](https://github.com/SigmaHQ/pySigma) and its SQLite backend.
These are the only packages outside the standard library. When they are not installed,
`learn.py` runs them through [uv](https://docs.astral.sh/uv/) with pinned versions, so
nothing is installed globally.

## Design

The full design, with the prior-art survey and the 21-skill catalogue this slice starts on,
is the "AI learning skills: prior art and design" document in the Zenith platform project.
This plugin implements its first vertical slice: the learner model plus goal, placement,
planning, tutoring, objective grading, review and a pedagogy evaluation.
