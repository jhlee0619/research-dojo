# Pairwise squared distances

Minimize runtime while preserving the exact sum of squared pairwise differences for integer sequences.

Metric: `elapsed_ms` (min); score = median of fixed seeds.

| Rank | Candidate | Attempt | Score | Samples | Code SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| 1 | moments | a0002 | 0.018839 | [0.031848, 0.018818, 0.018839] | aff74fc9455a |
| 2 | prefix | a0003 | 0.078538 | [0.105879, 0.068073, 0.078538] | 93029dfdad51 |
| 3 | baseline | a0001 | 7.251017 | [7.11411, 7.251017, 7.524779] | 015b8fb9286a |

## Evaluation history

| Attempt | Candidate | Status | Seconds | Error |
| --- | --- | --- | ---: | --- |
| a0001 | baseline | completed | 0.278 |  |
| a0002 | moments | completed | 0.188 |  |
| a0003 | prefix | completed | 0.194 |  |

## Hypotheses

- **baseline** (parent: None): Unmodified starting solution
- **moments** (parent: baseline): Use the algebraic moments identity
- **prefix** (parent: baseline): Accumulate contributions from preceding values

Best measured attempt: a0002.
Results describe this fixed evaluator only. Native host model usage is not measured here.
