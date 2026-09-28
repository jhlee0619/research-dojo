#!/usr/bin/env python3
"""Validate the packaged layout without a model API or installed host CLI."""
import hashlib
import json
from pathlib import Path
import re
import sys


def verify(root):
    root = Path(root).resolve()
    plugin = root / "plugins/research-dojo"
    manifests = [plugin / "plugin.json", plugin / ".claude-plugin/plugin.json", plugin / ".codex-plugin/plugin.json"]
    data = [json.loads(p.read_text()) for p in manifests]
    assert {m["name"] for m in data} == {"research-dojo"}, "Manifest names differ"
    assert len({m["version"] for m in data}) == 1, "Manifest versions differ"
    assert {m["license"] for m in data} == {"CC-BY-NC-4.0"}, "Manifest licenses differ"
    assert data[0]["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    for platform in (".claude-plugin", ".agents/plugins"):
        marketplace = json.loads((root / platform / "marketplace.json").read_text())
        assert len(marketplace["plugins"]) == 1
        source = marketplace["plugins"][0]["source"]
        path = source["path"] if isinstance(source, dict) else source
        assert (root / path).resolve() == plugin
    skill = plugin / "skills/research-dojo"
    version = re.search(r'^VERSION = "([^"]+)"$', (skill / "scripts/dojo.py").read_text(), re.M)
    assert version and version.group(1) == data[0]["version"], "Runner version differs"
    for directory in (plugin, skill):
        for name in ("LICENSE", "NOTICE.md"):
            assert (directory / name).read_bytes() == (root / name).read_bytes(), f"Bundled notice differs: {directory / name}"
    assert (root / "LICENSE").read_text().startswith("Attribution-NonCommercial 4.0 International\n")
    for name, counterpart in (("README.md", "README.ko.md"), ("README.ko.md", "README.md")):
        readme = (root / name).read_text()
        assert f"]({counterpart})" in readme, f"Missing language link: {name}"
        for link in re.findall(r"\]\(([^)]+)\)", readme):
            relative = link.split("#", 1)[0]
            if relative and "://" not in relative:
                assert (root / relative).is_file(), f"Missing README reference: {link}"
    text = (skill / "SKILL.md").read_text()
    assert text.startswith("---\nname: research-dojo\n")
    assert "[TODO" not in text
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if "://" not in link:
            assert (skill / link).is_file(), f"Missing skill reference: {link}"
    for role in ("implementer", "debugger", "reviewer"):
        content = (plugin / "agents" / f"{role}.md").read_text()
        assert f"name: {role}\n" in content and "description:" in content
    for path in root.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    checksums = root / "SHA256SUMS"
    assert checksums.is_file(), "Missing SHA256SUMS"
    listed = set()
    for line in checksums.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        target = root / relative
        assert relative not in listed, f"Duplicate checksum: {relative}"
        assert root in target.resolve().parents, f"Checksum path escapes project: {relative}"
        listed.add(relative)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, f"Checksum mismatch: {relative}"
    excluded = {".git", "__pycache__", ".venv", "dist", "demo-task", "demo-run", "selected-solution"}
    packaged = {p.relative_to(root).as_posix() for p in root.rglob("*")
                if p.is_file() and not p.is_symlink()
                and not excluded.intersection(p.relative_to(root).parts)
                and p.name not in ("SHA256SUMS", ".research-dojo-install.json")
                and p.suffix not in (".pyc", ".zip")}
    assert listed == packaged, f"Checksum coverage differs: {sorted(listed ^ packaged)}"
    return {"version": data[0]["version"], "layout": "valid", "checksums": checksums.exists(),
            "host_native_loading": "requires validation in installed Claude Code/Codex clients"}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(__file__).parent), indent=2))
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
