# Release validation — 1.0.0

Date: 2026-09-28. Environment: Linux, Python 3.12.14, local CPU.

## Automated checks

23 tests passed: 18 runner tests and 5 installer tests.

Runner coverage includes real evaluator subprocesses, fixed-seed median scoring,
minimum/maximum objectives, baseline gating, invalid/non-finite/Boolean/missing
metrics, duplicate JSON keys, evaluator exit failures, hash drift, exact measured
snapshot export, failed retry eligibility, time/log/attempt limits, descendant
cleanup, SIGTERM, stale recovery, disjoint parallel evaluations, and prevention
of duplicate/concurrency-limited evaluations. Paths containing spaces are used.

Installer coverage includes install/update/remove, preservation of unrelated
marketplace entries and user experiments, refusing modified/unmanaged plugin
files, entry collisions, and symlinked destinations.

Package validation checks both host manifests and the portable manifest, local
marketplace source paths, linked Skill resources, agent definitions, Python
syntax, and checksums. The Skill Creator validator also passed.

## Native subagent workflow

A separate coordinator used the Skill with no implementation context. Two native
subagents independently wrote a moments-identity candidate and a prefix-recurrence
candidate in disjoint directories. The coordinator evaluated baseline and both
candidates sequentially. A separate read-only reviewer inspected the fixed
evaluator, raw metrics/logs, ledger, and measured code; it accepted the evidence
within that experiment's scope. The coordinator exported the exact winning
snapshot. No model API key, SDK, nested CLI session, or model server was used.

The reviewer identified an omitted integer-type assertion in the demo's timed
checks. The assertion was added, a regression test now rejects a float-returning
timed branch, and the same candidate implementations were evaluated again with
the final evaluator. Initial review evidence is retained separately and describes
the earlier evaluator accurately.

## Final evaluator smoke run

| Candidate | Median milliseconds | Per-seed milliseconds (3, 17, 41) |
| --- | ---: | --- |
| Baseline | 7.251017 | 7.114110, 7.251017, 7.524779 |
| Moments identity | 0.018839 | 0.031848, 0.018818, 0.018839 |
| Prefix recurrence | 0.078538 | 0.105879, 0.068073, 0.078538 |

All three passed the final evaluator. These timings demonstrate successful real
execution and ranking on the bundled length-450 integer example; they are not a
general performance claim. Optimized calls are very short, machine load was not
controlled, and other validation activity overlapped this smoke run. No held-out
dataset or scaling study was performed. Nine preliminary cases and five repeated
timed calls are checked per seed, including integer type and input non-mutation.

Raw final run files are in `validation/sample-run/`. Historic absolute paths in
commands and reports record the build environment; for a portable re-run, copy
the bundled demo with `dojo.py demo` and initialize a fresh run. The sample's
completed ledger and snapshots can still be inspected or exported by passing
the sample's current path to `dojo.py`.

## Not exercised here

- Actual Claude Code and Codex CLI Plugin loaders: executables are absent in the
  build environment. Manifests follow official formats and are checked locally;
  use `claude plugin validate` and the documented host installation checks.
- macOS and Python 3.10 execution: included as CI matrix targets but not run in
  this environment.
- GitHub Actions execution, public marketplace submission, or external hosting.
- Adversarial code isolation: this runner is not a security sandbox.
- Recovery from arbitrary hardware/storage failures or daemonized hostile code.
