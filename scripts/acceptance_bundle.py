"""Scaffold a release-acceptance bundle and self-check it locally.

Usage:
  python scripts/acceptance_bundle.py init  --out ./bundle --commit <sha>
  python scripts/acceptance_bundle.py status --bundle ./bundle
  python scripts/acceptance_bundle.py check --bundle ./bundle --commit <sha>

`init` writes evidence.json from docs/acceptance/evidence-template.json with the
commit filled in, plus an artifacts/ directory. `status` prints which records are
still unverified. `check` runs the same validator CI uses.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "acceptance" / "evidence-template.json"
VERIFIER = ROOT / "scripts" / "verify-release-evidence.py"

PACKAGED_ONLY = {"clean-windows-package", "L01", "L12"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    bundle = out / "bundle"
    artifacts = bundle / "artifacts"
    if bundle.exists() and any(bundle.iterdir()):
        print(f"refusing to overwrite non-empty {bundle}", file=sys.stderr)
        return 1
    artifacts.mkdir(parents=True, exist_ok=True)
    data = _load(TEMPLATE)
    data["commit"] = args.commit
    _save(bundle / "evidence.json", data)
    total = len(data["scenarios"]) + len(data["requirements"])
    print(f"created {bundle / 'evidence.json'} with {total} records")
    print(f"put evidence files in {artifacts}")
    print("fill environment/integrations, then run: status, then check")
    return 0


def _records(data: dict) -> list[dict]:
    return data["scenarios"] + data["requirements"]


def cmd_status(args: argparse.Namespace) -> int:
    bundle = Path(args.bundle).resolve()
    data = _load(bundle / "evidence.json")
    pending = [r["id"] for r in _records(data) if r.get("status") != "passed"]
    done = len(_records(data)) - len(pending)
    print(f"passed: {done}/{len(_records(data))}")
    if data.get("commit", "").startswith("REPLACE"):
        print("commit: NOT SET")
    else:
        print(f"commit: {data['commit']}")
    missing_env = [k for k, v in data.get("environment", {}).items() if not v]
    missing_int = [k for k, v in data.get("integrations", {}).items() if not v]
    if missing_env:
        print(f"environment missing: {', '.join(missing_env)}")
    if missing_int:
        print(f"integrations missing: {', '.join(missing_int)}")
    if pending:
        print(f"pending ({len(pending)}): {', '.join(pending)}")
    else:
        print("all records marked passed")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    bundle = Path(args.bundle).resolve()
    python = shutil.which("python") or sys.executable
    result = subprocess.run(
        [python, str(VERIFIER), "--evidence", str(bundle / "evidence.json"), "--commit", args.commit],
        cwd=ROOT,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a bundle skeleton")
    init.add_argument("--out", required=True)
    init.add_argument("--commit", required=True)
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="show what is still unverified")
    status.add_argument("--bundle", required=True)
    status.set_defaults(func=cmd_status)

    check = sub.add_parser("check", help="run the CI validator locally")
    check.add_argument("--bundle", required=True)
    check.add_argument("--commit", required=True)
    check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
