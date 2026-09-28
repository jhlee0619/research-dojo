#!/usr/bin/env python3
"""Research Dojo: a local, API-free experiment ledger and evaluator runner.

Python 3.10+, Linux/macOS/WSL. Native host agents supply hypotheses and code;
this program never calls an LLM or launches an agent CLI.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

VERSION = "1.0.0"
IGNORE = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class DojoError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise DojoError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (ValueError, OSError) as exc:
        raise DojoError(f"Cannot read JSON {path}: {exc}") from exc


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".dojo-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise DojoError(f"Expected a real directory: {root}")
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE)
        for name in dirs + names:
            if (Path(current) / name).is_symlink():
                raise DojoError(f"Symlinks are not supported in experiment snapshots: {name}")
        for name in sorted(names):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = Path(current) / name
            if not path.is_file():
                raise DojoError(f"Not a regular file: {path}")
            yield path, path.relative_to(root)


def tree_hash(root):
    digest = hashlib.sha256()
    for path, relative in files(root):
        digest.update(relative.as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination)
    listing = list(files(source))
    if destination.exists():
        raise DojoError(f"Destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        for path, relative in listing:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    except BaseException:
        shutil.rmtree(destination)
        raise


def positive(value, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DojoError(f"{label} must be a positive number")
    if not math.isfinite(value) or value <= 0 or (integer and not isinstance(value, int)):
        raise DojoError(f"Invalid {label}: {value}")
    return value


def validate_task(task):
    allowed = {"schema_version", "name", "goal", "metric", "direction", "template",
               "evaluator", "command", "seeds", "limits"}
    if not isinstance(task, dict) or set(task) - allowed:
        raise DojoError("Task must be an object with documented fields only")
    if task.get("schema_version") != 1:
        raise DojoError("Task schema_version must be 1")
    for field in ("name", "goal", "metric", "template", "evaluator"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise DojoError(f"Task requires nonempty {field}")
    if task.get("direction") not in ("min", "max"):
        raise DojoError("direction must be min or max")
    command = task.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(s, str) and s for s in command):
        raise DojoError("command must be a nonempty argv array, not a shell string")
    allowed_tokens = {"python", "candidate", "evaluator", "metrics", "seed"}
    for arg in command:
        if set(re.findall(r"\{([^{}]+)\}", arg)) - allowed_tokens:
            raise DojoError(f"Unknown command placeholder in {arg!r}")
    if not any("{metrics}" in arg for arg in command):
        raise DojoError("command must pass {metrics} to the evaluator")
    seeds = task.setdefault("seeds", [0, 1, 2])
    if (not isinstance(seeds, list) or not seeds or len(seeds) > 100 or
            not all(isinstance(s, int) and not isinstance(s, bool) and 0 <= s < 2**32 for s in seeds)):
        raise DojoError("seeds must contain 1..100 unsigned 32-bit integers")
    defaults = {"max_attempts": 16, "max_parallel": 1, "timeout_seconds": 60,
                "execution_budget_seconds": 600, "max_log_bytes": 10_000_000}
    limits = task.setdefault("limits", {})
    if not isinstance(limits, dict) or set(limits) - defaults.keys():
        raise DojoError("Unknown limit field")
    for field, default in defaults.items():
        positive(limits.setdefault(field, default), field,
                 integer=field in ("max_attempts", "max_parallel", "max_log_bytes"))
    return task


def integrity(root):
    return {"task": hashlib.sha256((root / "task.json").read_bytes()).hexdigest(),
            "evaluator": tree_hash(root / "evaluator")}


def ensure_integrity(root, state):
    if integrity(root) != state["integrity"]:
        raise DojoError("Task or evaluator changed. Restore the original or start a new run.")


@contextlib.contextmanager
def transaction(root):
    if os.name != "posix":
        raise DojoError("Use Linux, macOS or Windows Subsystem for Linux (WSL)")
    import fcntl
    root = Path(root).resolve()
    if not (root / "state.json").is_file():
        raise DojoError(f"No run at {root}; use init first")
    with (root / ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_json(root / "state.json")
        try:
            yield root, state
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def save(root, state, event, **details):
    state["events"].append({"time": now(), "event": event, **details})
    write_json(root / "state.json", state)


def process_token(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def alive(pid, token=None):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return token is None or process_token(pid) in (token, None)


def group_alive(pid):
    if not pid:
        return False
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def activity_is_locked(root, attempt_id):
    import fcntl
    with (root / "attempts" / attempt_id / ".active").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return False


def reap_stale(root, state):
    changed = []
    for attempt in state["attempts"]:
        if attempt["status"] != "running" or activity_is_locked(root, attempt["id"]):
            continue
        # An orphan process retains its reservation. Never guess that it is safe to rerun.
        if group_alive(attempt.get("process_group")):
            continue
        attempt.update(status="interrupted", ended_at=now(),
                       duration_seconds=attempt["reserved_seconds"],
                       error="Supervisor disappeared; reservation charged conservatively")
        changed.append(attempt["id"])
    return changed


def consumption(state):
    return sum(a["reserved_seconds"] if a["status"] == "running" else a.get("duration_seconds", 0)
               for a in state["attempts"])


def ranking(state, task):
    latest = {}
    for attempt in state["attempts"]:
        latest[attempt["candidate_id"]] = attempt
    valid = [a for a in latest.values() if a["status"] == "completed"]
    # Without a valid baseline, report measurements but do not choose a winner.
    if not any(a["candidate_id"] == "baseline" for a in valid):
        return []
    return sorted(valid, key=lambda a: ((a["score"] if task["direction"] == "min" else -a["score"]), a["id"]))


def initialize(run, task_path):
    root, spec = Path(run).resolve(), Path(task_path).resolve()
    task = validate_task(read_json(spec))
    template = (spec.parent / task["template"]).resolve()
    evaluator = (spec.parent / task["evaluator"]).resolve()
    for source in (template, evaluator):
        if root == source or source in root.parents:
            raise DojoError("Run directory must not be inside the template or evaluator")
    if root.exists():
        raise DojoError(f"Run path already exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".dojo-init-", dir=root.parent))
    try:
        snapshot(template, staging / "candidates/baseline")
        snapshot(evaluator, staging / "evaluator")
        task["template"] = "candidates/baseline"
        task["evaluator"] = "evaluator"
        write_json(staging / "task.json", task)
        state = {"schema_version": 1, "runner_version": VERSION, "created_at": now(),
                 "integrity": integrity(staging), "candidates": {
                     "baseline": {"parent": None, "hypothesis": "Unmodified starting solution", "created_at": now()}},
                 "attempts": [], "events": []}
        save(staging, state, "initialized")
        # Rename only if no concurrent initializer has claimed this path.
        if root.exists():
            raise DojoError(f"Run path already exists: {root}")
        staging.rename(root)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"run": str(root), "baseline": str(root / "candidates/baseline")}


def candidate(run, candidate_id, parent, hypothesis):
    if not ID_RE.fullmatch(candidate_id) or candidate_id == "baseline":
        raise DojoError("Candidate ID must be 1..64 lowercase letters/digits/_/- and not baseline")
    if not hypothesis.strip():
        raise DojoError("A candidate needs a concrete hypothesis")
    with transaction(run) as (root, state):
        ensure_integrity(root, state)
        if candidate_id in state["candidates"] or parent not in state["candidates"]:
            raise DojoError("Candidate exists or parent is unknown")
        attempts = [a for a in state["attempts"] if a["candidate_id"] == parent and a["status"] == "completed"]
        previous = attempts[-1] if attempts else None
        source = root / (f"attempts/{previous['id']}/candidate" if previous else f"candidates/{parent}")
        if previous and tree_hash(source) != previous["code_sha256"]:
            raise DojoError("Parent experiment snapshot changed")
        snapshot(source, root / "candidates" / candidate_id)
        state["candidates"][candidate_id] = {"parent": parent,
            "parent_attempt": previous["id"] if previous else None, "hypothesis": hypothesis, "created_at": now()}
        save(root, state, "candidate_created", candidate_id=candidate_id)
        return {"candidate_id": candidate_id, "directory": str(root / "candidates" / candidate_id)}


def reserve(run, candidate_id):
    with transaction(run) as (root, state):
        ensure_integrity(root, state)
        changed = reap_stale(root, state)
        if changed:
            save(root, state, "recovered", attempts=changed)
        task = validate_task(read_json(root / "task.json"))
        limits = task["limits"]
        if candidate_id not in state["candidates"]:
            raise DojoError("Unknown candidate")
        active = [a for a in state["attempts"] if a["status"] == "running"]
        if any(a["candidate_id"] == candidate_id for a in active):
            raise DojoError("This candidate already has an active evaluation")
        if len(active) >= limits["max_parallel"]:
            raise DojoError("Parallel evaluation limit reached")
        if len(state["attempts"]) >= limits["max_attempts"]:
            raise DojoError("Attempt limit reached")
        remaining = limits["execution_budget_seconds"] - consumption(state)
        if remaining <= 0.01:
            raise DojoError("Execution budget exhausted")
        attempt_id = f"a{len(state['attempts']) + 1:04d}"
        folder = root / "attempts" / attempt_id
        snapshot(root / "candidates" / candidate_id, folder / "candidate")
        import fcntl
        activity = (folder / ".active").open("a+b")
        fcntl.flock(activity.fileno(), fcntl.LOCK_EX)
        attempt = {"id": attempt_id, "candidate_id": candidate_id, "status": "running",
                   "started_at": now(), "supervisor_pid": os.getpid(), "supervisor_token": process_token(os.getpid()),
                   "process_group": None, "reserved_seconds": min(limits["timeout_seconds"], remaining),
                   "code_sha256": tree_hash(folder / "candidate"), "values": []}
        state["attempts"].append(attempt)
        save(root, state, "evaluation_started", attempt_id=attempt_id)
        return root, task, dict(attempt), activity


def kill_group(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def evaluate(run, candidate_id):
    root, task, attempt, activity = reserve(run, candidate_id)
    directory = root / "attempts" / attempt["id"]
    started = time.monotonic()
    process = None
    status, error, values = "completed", None, []
    old_handler = signal.getsignal(signal.SIGTERM)
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for index, seed in enumerate(task["seeds"]):
            output = directory / f"metrics-{index + 1}.json"
            replacements = {"python": sys.executable, "candidate": str(directory / "candidate"),
                            "evaluator": str(root / "evaluator"), "metrics": str(output), "seed": str(seed)}
            command = []
            for argument in task["command"]:
                for key, value in replacements.items():
                    argument = argument.replace("{" + key + "}", value)
                command.append(argument)
            write_json(directory / f"command-{index + 1}.json", command)
            log = directory / f"output-{index + 1}.log"
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=str(seed),
                       DOJO_CANDIDATE=replacements["candidate"], DOJO_METRICS=str(output), DOJO_SEED=str(seed))
            with log.open("wb") as stream:
                process = subprocess.Popen(command, cwd=directory / "candidate", env=env,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                                           pass_fds=(activity.fileno(),))
                with transaction(root) as (_, state):
                    stored = next(a for a in state["attempts"] if a["id"] == attempt["id"])
                    stored["process_group"] = process.pid
                    save(root, state, "process_started", attempt_id=attempt["id"], seed=seed)
                while process.poll() is None:
                    if time.monotonic() - started >= attempt["reserved_seconds"]:
                        status = "timeout"
                        raise DojoError("Evaluation time limit exceeded")
                    if log.stat().st_size > task["limits"]["max_log_bytes"]:
                        status = "log_limit"
                        raise DojoError("Evaluation log limit exceeded")
                    time.sleep(0.03)
                exit_code = process.returncode
                kill_group(process)  # also clean up children left behind after a successful parent exit
                process = None
            if time.monotonic() - started > attempt["reserved_seconds"]:
                status = "timeout"
                raise DojoError("Evaluation time limit exceeded")
            if log.stat().st_size > task["limits"]["max_log_bytes"]:
                status = "log_limit"
                raise DojoError("Evaluation log limit exceeded")
            if exit_code:
                raise DojoError(f"Evaluator exited with code {exit_code}; inspect {log.name}")
            if output.is_symlink() or (output.exists() and output.stat().st_size > 1_000_000):
                raise DojoError("Invalid metrics file")
            result = read_json(output)
            if not isinstance(result, dict) or result.get("valid") is not True:
                raise DojoError("Evaluator did not validate the solution")
            metric = result.get("metrics", {})
            value = metric.get(task["metric"]) if isinstance(metric, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise DojoError(f"Missing or non-finite metric: {task['metric']}")
            values.append(value)
    except KeyboardInterrupt:
        status, error = "interrupted", "Evaluation interrupted"
    except (DojoError, OSError, ValueError) as exc:
        if status == "completed":
            status = "failed"
        error = str(exc)
    finally:
        kill_group(process)
        signal.signal(signal.SIGTERM, old_handler)
    elapsed = time.monotonic() - started
    with transaction(root) as (_, state):
        stored = next(a for a in state["attempts"] if a["id"] == attempt["id"])
        try:
            ensure_integrity(root, state)
            if tree_hash(directory / "candidate") != attempt["code_sha256"]:
                raise DojoError("Evaluated code changed during execution")
        except (DojoError, OSError) as exc:
            status, error = "integrity_error", str(exc)
        stored.update(status=status, ended_at=now(), duration_seconds=elapsed,
                      process_group=None, values=values, error=error)
        if status == "completed":
            stored["score"] = statistics.median(values)
        save(root, state, "evaluation_finished", attempt_id=attempt["id"], status=status)
        write_json(directory / "result.json", stored)
        activity.close()
        return dict(stored)


def inspect(run, recover=False):
    with transaction(run) as (root, state):
        ensure_integrity(root, state)
        if recover:
            recovered = reap_stale(root, state)
            if recovered:
                save(root, state, "recovered", attempts=recovered)
        task = read_json(root / "task.json")
        ranked = ranking(state, task)
        last = {a["candidate_id"]: a for a in state["attempts"]}
        pending = [key for key in state["candidates"] if key not in last]
        failed = [key for key, a in last.items() if a["status"] not in ("running", "completed")]
        running = [a["id"] for a in state["attempts"] if a["status"] == "running"]
        attempts_remaining = max(0, task["limits"]["max_attempts"] - len(state["attempts"]))
        seconds_remaining = max(0, task["limits"]["execution_budget_seconds"] - consumption(state))
        exhausted = attempts_remaining == 0 or seconds_remaining <= 0.01
        return {"run": str(root), "task": task, "candidates": state["candidates"],
                "attempts": state["attempts"], "ranking": ranked,
                "best_attempt": ranked[0]["id"] if ranked else None,
                "pending_candidates": pending, "failed_candidates": failed, "running_attempts": running,
                "attempts_remaining": attempts_remaining,
                "execution_seconds_remaining": seconds_remaining,
                "next_action": "wait_for_active_evaluations" if running else
                    ("budget_exhausted" if exhausted else "evaluate_baseline" if not ranked else "evaluate_pending_candidates" if pending else
                     "repair_or_create_candidate_within_budget")}


def report(run, json_format=False):
    summary = inspect(run)
    root = Path(summary["run"])
    write_json(root / "report.json", summary)
    task = summary["task"]
    def esc(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = [f"# {esc(task['name'])}", "", esc(task["goal"]), "",
             f"Metric: `{esc(task['metric'])}` ({task['direction']}); score = median of fixed seeds.", "",
             "| Rank | Candidate | Attempt | Score | Samples | Code SHA-256 |",
             "| --- | --- | --- | ---: | --- | --- |"]
    for rank, a in enumerate(summary["ranking"], 1):
        lines.append(f"| {rank} | {a['candidate_id']} | {a['id']} | {a['score']:.9g} | {esc(a['values'])} | {a['code_sha256'][:12]} |")
    if not summary["ranking"]:
        lines += ["", "No ranked result: a validated baseline is required."]
    lines += ["", "## Evaluation history", "", "| Attempt | Candidate | Status | Seconds | Error |",
              "| --- | --- | --- | ---: | --- |"]
    for a in summary["attempts"]:
        lines.append(f"| {a['id']} | {a['candidate_id']} | {a['status']} | {a.get('duration_seconds', 0):.3f} | {esc(a.get('error') or '')} |")
    lines += ["", "## Hypotheses", ""]
    for key, c in summary["candidates"].items():
        lines.append(f"- **{key}** (parent: {c['parent']}): {esc(c['hypothesis'])}")
    lines += ["", f"Best measured attempt: {summary['best_attempt'] or 'none'}.",
              "Results describe this fixed evaluator only. Native host model usage is not measured here.", ""]
    text = "\n".join(lines)
    (root / "report.md").write_text(text, encoding="utf-8")
    return summary if json_format else text


def export(run, attempt_id, destination):
    with transaction(run) as (root, state):
        ensure_integrity(root, state)
        if attempt_id == "best":
            ranked = ranking(state, read_json(root / "task.json"))
            if not ranked:
                raise DojoError("No validated winner")
            attempt_id = ranked[0]["id"]
        attempt = next((a for a in state["attempts"] if a["id"] == attempt_id), None)
        if not attempt or attempt["status"] != "completed":
            raise DojoError("Export requires a completed, validated attempt")
        source = root / "attempts" / attempt_id / "candidate"
        if tree_hash(source) != attempt["code_sha256"]:
            raise DojoError("Measured snapshot changed; cannot export")
        target = Path(destination).resolve()
        if target == root or root in target.parents:
            raise DojoError("Export to a new directory outside the run")
        snapshot(source, target)
        write_json(target / "dojo-provenance.json", {"run": str(root), "attempt": attempt,
                                                    "evaluation_integrity": state["integrity"]})
        return {"directory": str(target), "attempt_id": attempt_id, "score": attempt["score"]}


def demo(destination):
    source = Path(__file__).resolve().parent.parent / "assets" / "cpu-demo"
    snapshot(source, Path(destination).resolve())
    return {"task": str(Path(destination).resolve() / "task.json")}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("init", "candidate", "run", "status", "resume", "report", "export"):
        q = sub.add_parser(action)
        q.add_argument("--run", required=True, help="Experiment directory")
        if action == "init":
            q.add_argument("--task", required=True)
        elif action == "candidate":
            q.add_argument("--id", required=True)
            q.add_argument("--parent", default="baseline")
            q.add_argument("--hypothesis", required=True)
        elif action == "run":
            q.add_argument("--candidate", required=True)
        elif action == "report":
            q.add_argument("--format", choices=("json", "markdown"), default="markdown")
        elif action == "export":
            q.add_argument("--attempt", default="best")
            q.add_argument("--output", required=True)
    sub.add_parser("doctor")
    sub.add_parser("demo").add_argument("--output", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.action == "init":
            result = initialize(args.run, args.task)
        elif args.action == "candidate":
            result = candidate(args.run, args.id, args.parent, args.hypothesis)
        elif args.action == "run":
            result = evaluate(args.run, args.candidate)
        elif args.action in ("status", "resume"):
            result = inspect(args.run, recover=args.action == "resume")
        elif args.action == "report":
            result = report(args.run, args.format == "json")
        elif args.action == "export":
            result = export(args.run, args.attempt, args.output)
        elif args.action == "demo":
            result = demo(args.output)
        else:
            result = {"version": VERSION, "python": sys.version.split()[0], "platform": sys.platform,
                      "runner_supported": os.name == "posix" and sys.version_info >= (3, 10),
                      "claude_cli": shutil.which("claude"), "codex_cli": shutil.which("codex"),
                      "requires_llm_api_key": False,
                      "note": "Native agent availability must be checked inside the host session."}
        print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if args.action == "run" and result["status"] != "completed" else 0
    except (DojoError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
