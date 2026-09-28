"""Fixed correctness and timing evaluation; only the candidate is editable."""
import argparse
import importlib.util
import json
from pathlib import Path
import random
import statistics
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("candidate_solution", Path(args.candidate) / "solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = module.pairwise_squared_distance
    rng = random.Random(args.seed)
    cases = [[], [7], [1, 2], [-10, 0, 10], [4] * 30, [10**20, -10**20, 0]]
    cases += [[rng.randint(-10000, 10000) for _ in range(n)] for n in (5, 31, 120)]
    for values in cases:
        expected = len(values) * sum(x * x for x in values) - sum(values) ** 2
        before = list(values)
        actual = fn(values)
        if not isinstance(actual, int) or isinstance(actual, bool) or actual != expected or values != before:
            Path(args.output).write_text(json.dumps({"valid": False, "metrics": {}, "details": {"error": "Incorrect result or mutated input"}}))
            return
    values = [rng.randint(-10000, 10000) for _ in range(450)]
    expected = len(values) * sum(x * x for x in values) - sum(values) ** 2
    timings = []
    for _ in range(5):
        before = list(values)
        started = time.perf_counter_ns()
        actual = fn(values)
        timings.append((time.perf_counter_ns() - started) / 1_000_000)
        if not isinstance(actual, int) or isinstance(actual, bool) or actual != expected or values != before:
            raise ValueError("Benchmark correctness failed")
    Path(args.output).write_text(json.dumps({"valid": True, "metrics": {"elapsed_ms": statistics.median(timings)},
                                           "details": {"correctness_cases": len(cases) + 5, "timings_ms": timings}}))


if __name__ == "__main__":
    main()
