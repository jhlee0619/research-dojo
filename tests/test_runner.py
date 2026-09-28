import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("RESEARCH_DOJO_SKILL", ROOT / "plugins/research-dojo/skills/research-dojo"))
RUNNER = SKILL / "scripts/dojo.py"
spec = importlib.util.spec_from_file_location("dojo", RUNNER)
dojo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dojo)

EVALUATOR = r'''
import argparse, json, math, subprocess, sys, time
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--candidate'); p.add_argument('--output'); p.add_argument('--seed', type=int)
a = p.parse_args()
c = json.loads((Path(a.candidate)/'value.json').read_text())
mode = c.get('mode', 'ok')
if mode == 'timeout':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    Path(a.output + '.pid').write_text(str(child.pid))
    time.sleep(30)
if mode == 'pause': time.sleep(0.8)
if mode == 'large-log': print('x' * 20000)
if mode == 'nonzero': sys.exit(7)
if mode == 'nooutput': sys.exit(0)
if mode == 'code-drift': (Path(a.candidate)/'mutated.txt').write_text('changed')
if mode == 'evaluator-drift': Path(__file__).write_text(Path(__file__).read_text() + '\n# changed\n')
value = c['value'] + a.seed
if mode == 'nan': value = math.nan
if mode == 'bool': value = True
result = {'valid': mode != 'invalid', 'metrics': {'score': value}}
if mode == 'missing': result['metrics'] = {}
if mode == 'duplicate':
    Path(a.output).write_text('{"valid":true,"valid":false,"metrics":{"score":1}}')
else:
    Path(a.output).write_text(json.dumps(result))
'''


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dojo test spaces ")
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def task(self, mode="ok", value=10, seeds=None, direction="min", **limits):
        source = self.base / f"task-{len(list(self.base.iterdir()))}"
        (source / "solution").mkdir(parents=True)
        (source / "evaluator").mkdir()
        (source / "solution/value.json").write_text(json.dumps({"mode": mode, "value": value}))
        (source / "evaluator/evaluate.py").write_text(EVALUATOR)
        task = {"schema_version": 1, "name": "Controlled experiment", "goal": "Measure score",
                "metric": "score", "direction": direction, "template": "solution", "evaluator": "evaluator",
                "command": ["{python}", "{evaluator}/evaluate.py", "--candidate", "{candidate}",
                            "--output", "{metrics}", "--seed", "{seed}"],
                "seeds": seeds or [2, 5, 9], "limits": limits}
        spec_path = source / "task.json"
        spec_path.write_text(json.dumps(task))
        run = self.base / f"run-{source.name}"
        dojo.initialize(run, spec_path)
        return run

    def change(self, run, name, **values):
        (run / "candidates" / name / "value.json").write_text(json.dumps(values))

    def test_measure_rank_resume_and_export_exact_snapshot(self):
        run = self.task()
        baseline = dojo.evaluate(run, "baseline")
        self.assertEqual(baseline["values"], [12, 15, 19])
        self.assertEqual(baseline["score"], 15)
        dojo.candidate(run, "better", "baseline", "Reduce value by eight")
        self.change(run, "better", value=2)
        better = dojo.evaluate(run, "better")
        self.change(run, "better", value=999)
        dojo.candidate(run, "child", "better", "Measured parent only")
        self.assertEqual(json.loads((run / "candidates/child/value.json").read_text())["value"], 2)
        state = dojo.inspect(run, recover=True)
        self.assertEqual(state["best_attempt"], better["id"])
        self.assertEqual(len(state["attempts"]), 2)
        self.assertIn("child", state["pending_candidates"])
        output = self.base / "export"
        dojo.export(run, "best", output)
        self.assertEqual(json.loads((output / "value.json").read_text())["value"], 2)
        self.assertEqual(json.loads((output / "dojo-provenance.json").read_text())["attempt"]["id"], better["id"])
        self.assertIn("better", dojo.report(run))
        self.assertTrue((run / "report.json").exists())
        with self.assertRaises(dojo.DojoError):
            dojo.export(run, "best", output)

    def test_failed_latest_attempt_excluded_but_old_snapshot_exportable(self):
        run = self.task(seeds=[0])
        dojo.evaluate(run, "baseline")
        dojo.candidate(run, "candidate", "baseline", "Improve score")
        self.change(run, "candidate", value=1)
        first = dojo.evaluate(run, "candidate")
        self.change(run, "candidate", value=1, mode="invalid")
        self.assertEqual(dojo.evaluate(run, "candidate")["status"], "failed")
        self.assertEqual(dojo.inspect(run)["ranking"][0]["candidate_id"], "baseline")
        dojo.export(run, first["id"], self.base / "earlier")

    def test_max_direction_and_baseline_gate(self):
        run = self.task(seeds=[0], direction="max")
        dojo.candidate(run, "larger", "baseline", "Increase score")
        self.change(run, "larger", value=99)
        dojo.evaluate(run, "larger")
        self.assertIsNone(dojo.inspect(run)["best_attempt"])
        dojo.evaluate(run, "baseline")
        self.assertEqual(dojo.inspect(run)["ranking"][0]["candidate_id"], "larger")

    def test_invalid_metrics_never_rank(self):
        for mode in ("nan", "bool", "invalid", "missing", "nonzero", "duplicate", "nooutput"):
            with self.subTest(mode=mode):
                run = self.task(mode=mode, seeds=[0])
                self.assertEqual(dojo.evaluate(run, "baseline")["status"], "failed")
                self.assertEqual(dojo.inspect(run)["ranking"], [])

    def test_task_and_evaluator_are_frozen(self):
        run = self.task()
        (run / "evaluator/new.py").write_text("# accidental change")
        with self.assertRaises(dojo.DojoError):
            dojo.evaluate(run, "baseline")
        self.assertEqual(len(dojo.read_json(run / "state.json")["attempts"]), 0)

    def test_runtime_code_and_evaluator_drift_rejected(self):
        for mode in ("code-drift", "evaluator-drift"):
            with self.subTest(mode=mode):
                run = self.task(mode=mode, seeds=[0])
                self.assertEqual(dojo.evaluate(run, "baseline")["status"], "integrity_error")

    def test_timeout_kills_descendants(self):
        run = self.task(mode="timeout", seeds=[0], timeout_seconds=0.25)
        result = dojo.evaluate(run, "baseline")
        self.assertEqual(result["status"], "timeout")
        pid = int((run / "attempts/a0001/metrics-1.json.pid").read_text())
        proc = Path(f"/proc/{pid}/stat")
        if proc.exists():
            self.assertEqual(proc.read_text().rsplit(")", 1)[1].split()[0], "Z")
        self.assertEqual(dojo.inspect(run)["running_attempts"], [])

    def test_attempt_limit_and_resume_preserve_completed(self):
        run = self.task(seeds=[0], max_attempts=1)
        dojo.evaluate(run, "baseline")
        with self.assertRaises(dojo.DojoError):
            dojo.evaluate(run, "baseline")
        state = dojo.inspect(run, recover=True)
        self.assertEqual(len(state["attempts"]), 1)
        self.assertEqual(state["attempts_remaining"], 0)
        self.assertEqual(state["next_action"], "budget_exhausted")

    def test_execution_budget_ends_in_timeout(self):
        run = self.task(mode="pause", seeds=[0], execution_budget_seconds=0.15)
        self.assertEqual(dojo.evaluate(run, "baseline")["status"], "timeout")
        with self.assertRaises(dojo.DojoError):
            dojo.evaluate(run, "baseline")

    def wait_active(self, run):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            attempts = dojo.read_json(run / "state.json")["attempts"]
            if attempts and attempts[-1].get("process_group"):
                return
            time.sleep(0.02)
        self.fail("Evaluator did not start")

    def test_parallel_reservation_prevents_duplicate_evaluation(self):
        run = self.task(mode="pause", seeds=[0])
        dojo.candidate(run, "other", "baseline", "Independent variant")
        process = subprocess.Popen([sys.executable, str(RUNNER), "run", "--run", str(run), "--candidate", "baseline"], stdout=subprocess.PIPE)
        try:
            self.wait_active(run)
            other = subprocess.run([sys.executable, str(RUNNER), "run", "--run", str(run), "--candidate", "other"], capture_output=True)
            self.assertEqual(other.returncode, 2)
            self.assertIn(b"Parallel evaluation limit", other.stderr)
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None: process.kill()
            process.communicate()
        self.assertEqual(len(dojo.inspect(run)["attempts"]), 1)

    def test_sigterm_records_interruption_and_resume(self):
        run = self.task(mode="pause", seeds=[0])
        process = subprocess.Popen([sys.executable, str(RUNNER), "run", "--run", str(run), "--candidate", "baseline"], stdout=subprocess.PIPE)
        try:
            self.wait_active(run)
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=5), 1)
        finally:
            if process.poll() is None: process.kill()
            process.communicate()
        self.assertEqual(dojo.inspect(run, recover=True)["attempts"][0]["status"], "interrupted")
        self.change(run, "baseline", value=10)
        self.assertEqual(dojo.evaluate(run, "baseline")["status"], "completed")

    def test_parallel_success_keeps_both_records(self):
        run = self.task(mode="pause", seeds=[0], max_parallel=2)
        dojo.candidate(run, "other", "baseline", "Independent candidate")
        processes = [subprocess.Popen([sys.executable, str(RUNNER), "run", "--run", str(run),
                                      "--candidate", name], stdout=subprocess.PIPE)
                     for name in ("baseline", "other")]
        try:
            for process in processes:
                self.assertEqual(process.wait(timeout=5), 0)
        finally:
            for process in processes:
                if process.poll() is None: process.kill()
                process.communicate()
        attempts = dojo.inspect(run)["attempts"]
        self.assertEqual({a["candidate_id"] for a in attempts}, {"baseline", "other"})
        self.assertEqual({a["status"] for a in attempts}, {"completed"})

    def test_log_limit_enforced(self):
        run = self.task(mode="large-log", seeds=[0], max_log_bytes=100)
        self.assertEqual(dojo.evaluate(run, "baseline")["status"], "log_limit")

    def test_demo_rejects_wrong_type_in_timed_case(self):
        task = self.base / "typed-demo"
        dojo.demo(task)
        (task / "solution/solution.py").write_text('''def pairwise_squared_distance(values):
    result = len(values) * sum(x*x for x in values) - sum(values)**2
    return float(result) if len(values) == 450 else result
''')
        run = self.base / "typed-run"
        dojo.initialize(run, task / "task.json")
        self.assertEqual(dojo.evaluate(run, "baseline")["status"], "failed")

    def test_stale_supervisor_is_recovered_conservatively(self):
        run = self.task(seeds=[0])
        reservation = dojo.reserve(run, "baseline")
        self.assertEqual(dojo.inspect(run, recover=True)["attempts"][0]["status"], "running")
        reservation[3].close()
        state = dojo.read_json(run / "state.json")
        state["attempts"][0]["supervisor_pid"] = 99999999
        dojo.write_json(run / "state.json", state)
        recovered = dojo.inspect(run, recover=True)
        self.assertEqual(recovered["attempts"][0]["status"], "interrupted")
        self.assertEqual(recovered["execution_seconds_remaining"], 540)

    def test_snapshot_tamper_blocks_export(self):
        run = self.task(seeds=[0])
        dojo.evaluate(run, "baseline")
        (run / "attempts/a0001/candidate/value.json").write_text("{}")
        with self.assertRaises(dojo.DojoError):
            dojo.export(run, "best", self.base / "tampered")

    def test_path_traversal_and_symlinks_rejected(self):
        run = self.task(seeds=[0])
        with self.assertRaises(dojo.DojoError):
            dojo.candidate(run, "../escape", "baseline", "bad")
        (run / "candidates/baseline/link").symlink_to(self.base)
        with self.assertRaises(dojo.DojoError):
            dojo.evaluate(run, "baseline")

    def test_demo_runs_without_dependencies_or_keys(self):
        task = self.base / "demo"
        dojo.demo(task)
        run = self.base / "demo-run"
        dojo.initialize(run, task / "task.json")
        result = dojo.evaluate(run, "baseline")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["values"]), 3)


if __name__ == "__main__":
    unittest.main()
