# Task and runner protocol

## Contents

1. Task schema
2. Evaluator output
3. CLI operations
4. Storage and recovery
5. Interpretation

## Task schema

Create `task.json`, `solution/`, and `evaluator/` in a task directory. The runner
needs Python 3.10+ and POSIX (Linux/macOS/WSL), with no pip dependencies. Install
task-specific dependencies in the environment. Snapshots reject symlinks and
omit empty directories, `.git`, `.venv`, `venv`, and Python caches.

```json
{
  "schema_version": 1,
  "name": "Pairwise squared distances",
  "goal": "Reduce runtime while preserving exact integer results",
  "metric": "elapsed_ms",
  "direction": "min",
  "template": "solution",
  "evaluator": "evaluator",
  "command": ["{python}", "{evaluator}/evaluate.py", "--candidate", "{candidate}", "--output", "{metrics}", "--seed", "{seed}"],
  "seeds": [3, 17, 41],
  "limits": {"max_attempts": 16, "max_parallel": 1, "timeout_seconds": 60, "execution_budget_seconds": 600, "max_log_bytes": 10000000}
}
```

Source paths resolve relative to `task.json`. Initialization copies both source
and evaluator; later edits to the originals do not change a run. Use small source
templates rather than copying virtual environments or large installed packages.

`command` is an argv array executed without a shell. Literal placeholders:
`{python}`, `{candidate}`, `{evaluator}`, `{metrics}`, `{seed}`. The output path
must be passed using `{metrics}`. Working directory is the evaluated candidate
snapshot. Put temporary outputs/caches outside it, for example with `tempfile`.
Evaluated code must remain unchanged. Python bytecode writing is disabled.

Each seed launches an independent evaluator process; score is the median. Timeout
covers the entire attempt, including all seeds. The execution budget counts
summed evaluator wall time, not host LLM tokens or time between user sessions.
Active attempts reserve up to their timeout. Failed/time-limited attempts count
toward the attempt limit. Abandoned attempts may consume their full reservation.

## Evaluator output

After checking correctness, write UTF-8 JSON to the supplied metrics path:

```json
{"valid": true, "metrics": {"elapsed_ms": 12.3}, "details": {"checks": 8}}
```

Require Boolean `true` and a finite numeric objective (not a Boolean). Nonzero
exit, missing/malformed output, duplicate keys, incorrect results, NaN and Infinity
invalidate an attempt. Logs cannot replace structured metrics. Each seed gets a
fresh output path. Additional metrics are retained but do not affect ranking.

Changed evaluator/task/evaluated-code hashes reject an attempt. This detects
accidental drift, not malicious same-user code. Evaluator design determines
scientific validity; the runner cannot prove the grader measures the objective.

## CLI operations

Prefix commands with `python3 /absolute/path/to/skill/scripts/dojo.py`:

| Command | Effect |
| --- | --- |
| `doctor` | Report platform and optional host CLI discovery; no model call |
| `demo --output TASK` | Copy the self-contained CPU task to a new directory |
| `init --task TASK/task.json --run RUN` | Freeze evaluator/task and create baseline |
| `candidate --run RUN --id C --parent baseline --hypothesis TEXT` | Copy last successful measured parent, or source if never successful |
| `run --run RUN --candidate C` | Reserve budget, snapshot, evaluate fixed seeds, record |
| `status --run RUN` | Inspect state, ranking, pending work, budgets |
| `resume --run RUN` | Reconcile stale attempts and return a plan; no implicit execution |
| `report --run RUN [--format json]` | Write Markdown/JSON reports; print chosen format |
| `export --run RUN --attempt best --output NEW_DIR` | Export measured solution with provenance |

Exit codes: 0 success, 1 recorded unsuccessful evaluation, 2 invalid input or
operation/budget. Failed trials retain logs and status. Reporting is available
after budget exhaustion. Existing run/export directories are never overwritten.

## Storage and recovery

Store frozen `task.json`/`evaluator/`, editable `candidates/`, measured
`attempts/<id>/candidate/`, seed commands/logs/metrics, `state.json`, and reports.
The state file is authoritative and includes timestamped events. Writes use
advisory locking and atomic replacement. Use a local filesystem with POSIX lock
and rename semantics; network filesystems are not a coordination backend.

SIGINT/SIGTERM and timeouts kill evaluator process groups and record failure.
`resume` marks a vanished supervisor interrupted only after its child group has
exited. An active orphan retains its reservation; inspect it before continuing.
SIGKILL/machine crashes cannot be gracefully handled. This is not a background
daemon or a job scheduler.

The latest attempt per candidate determines ranking eligibility. A failed retry
excludes that candidate until a successful retry. Earlier successful attempts
remain exportable explicitly by ID. A valid baseline is required to select an
overall winner. Ties prefer earlier attempts. Export verifies hashes and never
includes later unmeasured edits.

## Interpretation

Keep criteria fixed. Use separate held-out validation for final scientific claims,
as a new run rather than silently changing a development evaluator. Timing tests
should run sequentially on one machine; inspect samples for noise. Tiny differences
may not be meaningful. Reviewer opinions supplement measurements. Research Dojo
independently implements an AIRA-inspired draft/improve/debug/analyze loop; it is
not upstream AIRA Dojo or a reproduction of its benchmark results.
