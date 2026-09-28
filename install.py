#!/usr/bin/env python3
"""Stage Research Dojo in a project and register host marketplace entries.

No account credentials, model calls, global config edits, or shell execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


NAME = "research-dojo"
MARKER = ".research-dojo-install.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".dojo-tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def hashes(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def safe_path(root, relative):
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Refusing symlinked install path: {current}")
        current = current.parent
    return path


def install(project, host, uninstall=False):
    source = Path(__file__).resolve().parent / "plugins" / NAME
    project = Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    marker = safe_path(project, MARKER)
    previous = read(marker) if marker.exists() else None
    plugin = safe_path(project, f"plugins/{NAME}")
    if previous and (not plugin.is_dir() or hashes(plugin) != previous["files"]):
        raise ValueError("Installed plugin was modified. Preserve your edits before updating/removing it.")
    if not previous and plugin.exists():
        raise ValueError("Destination plugin already exists and is not managed by this installer.")
    if uninstall and not previous:
        raise ValueError("No managed Research Dojo installation in this project.")
    requested = ["claude", "codex"] if host == "both" else [host]
    hosts = sorted(set(requested + (previous["hosts"] if previous else [])))
    if uninstall:
        hosts = previous["hosts"]
    updates, registrations = {}, {}
    for platform in hosts:
        relative = ".claude-plugin/marketplace.json" if platform == "claude" else ".agents/plugins/marketplace.json"
        path = safe_path(project, relative)
        data = read(path) if path.exists() else {
            "name": "research-dojo-local",
            **({"owner": {"name": "Research Dojo"}} if platform == "claude" else
               {"interface": {"displayName": "Research Dojo"}}),
            "plugins": []}
        if not isinstance(data.get("name"), str) or not isinstance(data.get("plugins"), list):
            raise ValueError(f"Invalid marketplace: {relative}")
        existing = [entry for entry in data["plugins"] if entry.get("name") == NAME]
        old_entry = (previous or {}).get("entries", {}).get(platform)
        if existing and (len(existing) != 1 or existing[0] != old_entry):
            raise ValueError(f"Research Dojo entry already exists or was modified in {relative}")
        entries = [entry for entry in data["plugins"] if entry.get("name") != NAME]
        entry = {"name": NAME, "source": f"./plugins/{NAME}"} if platform == "claude" else {
            "name": NAME, "source": {"source": "local", "path": f"./plugins/{NAME}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
        data["plugins"] = entries if uninstall else entries + [entry]
        updates[path] = data
        registrations[platform] = {"entry": entry, "marketplace": data["name"]}
    # Preflight everything before mutation; keep a rollback copy until all writes succeed.
    original = {p: p.read_bytes() if p.exists() else None for p in [*updates, marker]}
    with tempfile.TemporaryDirectory(prefix=".research-dojo-", dir=project) as temporary:
        backup = Path(temporary) / "previous"
        staged = Path(temporary) / "new"
        if not uninstall:
            shutil.copytree(source, staged)
            installed_hashes = hashes(staged)
        plugin.parent.mkdir(parents=True, exist_ok=True)
        if plugin.exists():
            plugin.rename(backup)
        try:
            if not uninstall:
                staged.rename(plugin)
            for path, data in updates.items():
                write(path, data)
            if uninstall:
                marker.unlink()
            else:
                write(marker, {"version": read(plugin / "plugin.json")["version"], "hosts": hosts,
                               "files": installed_hashes,
                               "entries": {h: r["entry"] for h, r in registrations.items()}})
        except BaseException:
            if plugin.exists():
                shutil.rmtree(plugin)
            if backup.exists():
                backup.rename(plugin)
            for path, content in original.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)
            raise
    return {"project": str(project), "action": "uninstalled" if uninstall else "staged",
            "plugin": str(plugin), "marketplaces": {h: r["marketplace"] for h, r in registrations.items()},
            "next": "Disable/remove the host's cached plugin if previously enabled." if uninstall else
            "Add this project as a marketplace in your host, then install/enable Research Dojo. See README.md."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True)
    p.add_argument("--host", choices=("claude", "codex", "both"), default="both")
    p.add_argument("--uninstall", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(install(args.project, args.host, args.uninstall), indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
