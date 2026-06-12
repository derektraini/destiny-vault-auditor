#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = _find_repo_root(Path(__file__).resolve())
    cli = repo_root / "scripts" / "destiny-vault-auditor.py"
    return subprocess.run([sys.executable, str(cli), *sys.argv[1:]], cwd=repo_root).returncode


def _find_repo_root(start: Path) -> Path:
    for parent in start.parents:
        cli = parent / "scripts" / "destiny-vault-auditor.py"
        package = parent / "src" / "auditor"
        if cli.is_file() and package.is_dir():
            return parent
    raise SystemExit("Could not find destiny-vault-auditor repo root.")


if __name__ == "__main__":
    raise SystemExit(main())
