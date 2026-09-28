#!/usr/bin/env python3
"""Regenerate checksums and create a deterministic archive of this release."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def build(output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    if output.exists() or root == output or root in output.parents:
        raise ValueError("Choose a new archive path outside this project")
    excluded = {".git", "__pycache__", ".venv", "dist", "demo-task", "demo-run", "selected-solution"}
    files = [p for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()
             and not excluded.intersection(p.relative_to(root).parts)
             and p.name not in ("SHA256SUMS", ".research-dojo-install.json") and p.suffix not in (".pyc", ".zip")]
    checksum = root / "SHA256SUMS"
    checksum.write_text("\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}" for p in files) + "\n")
    files.append(checksum)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo((Path(root.name) / path.relative_to(root)).as_posix(), (2026, 9, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    print(output)
    print(hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    build(parser.parse_args().output)
