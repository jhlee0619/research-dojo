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
    assert data[0]["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    for platform in (".claude-plugin", ".agents/plugins"):
        marketplace = json.loads((root / platform / "marketplace.json").read_text())
        assert len(marketplace["plugins"]) == 1
        source = marketplace["plugins"][0]["source"]
        path = source["path"] if isinstance(source, dict) else source
        assert (root / path).resolve() == plugin
    skill = plugin / "skills/research-dojo"
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
    if checksums.exists():
        for line in checksums.read_text().splitlines():
            expected, relative = line.split("  ", 1)
            target = root / relative
            assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, f"Checksum mismatch: {relative}"
    return {"version": data[0]["version"], "layout": "valid", "checksums": checksums.exists(),
            "host_native_loading": "requires validation in installed Claude Code/Codex clients"}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(__file__).parent), indent=2))
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
