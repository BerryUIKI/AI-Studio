"""Reject incomplete, historical or mock-only release acceptance evidence."""

import argparse
import json
from pathlib import Path
import re
from typing import Any

REQUIREMENTS = {f"R{number:02}" for number in range(1, 19)} | {f"L{number:02}" for number in range(1, 13)}
SCENARIOS = {
    "cloud-image-journey", "comfyui-image-journey", "webui-image-journey",
    "project-reopen", "masked-edit", "upscale-export", "task-recovery",
    "external-ownership", "install-update-recovery", "safe-exit", "clean-windows-package",
}


def validate_evidence(report: dict[str, Any], commit: str, directory: Path) -> list[str]:
    errors: list[str] = []
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("Expected commit must be a full 40-character Git SHA.")
    if report.get("schema_version") != 1 or report.get("commit") != commit:
        errors.append("Evidence must use schema version 1 and match the exact tested commit.")
    environment = report.get("environment")
    if not isinstance(environment, dict) or not all(environment.get(key) for key in ("os", "machine", "tested_at")):
        errors.append("Record OS, test machine and test timestamp.")
    integrations = report.get("integrations")
    if not isinstance(integrations, dict) or not all(integrations.get(key) for key in ("engines", "providers", "models")):
        errors.append("Record exact engine/provider versions and model identities.")
    for section, expected in (("requirements", REQUIREMENTS), ("scenarios", SCENARIOS)):
        records = report.get(section)
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            errors.append(f"{section}: expected an array of evidence records.")
            continue
        identifiers = [record.get("id") for record in records]
        if any(not isinstance(identity, str) for identity in identifiers):
            errors.append(f"{section}: IDs must be strings.")
            continue
        if len(identifiers) != len(set(identifiers)):
            errors.append(f"{section}: duplicate evidence IDs.")
        missing = expected - set(identifiers)
        if missing:
            errors.append(f"{section}: missing {', '.join(sorted(missing))}.")
        for record in records:
            identity = record.get("id")
            if identity not in expected:
                errors.append(f"{section}: unknown evidence ID {identity}.")
            allowed = {"live", "packaged-live"} if identity != "R17" else {"ci", "live", "packaged-live"}
            if identity == "clean-windows-package" or identity in {"L01", "L12"}:
                allowed = {"packaged-live"}
            if record.get("status") != "passed" or record.get("evidence_level") not in allowed:
                errors.append(f"{identity}: passed current-head live evidence is required; mocks, historical and unverified results cannot satisfy acceptance.")
            artifacts = record.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(f"{identity}: attach output or diagnostic artifacts.")
                continue
            for artifact in artifacts:
                if not isinstance(artifact, str):
                    errors.append(f"{identity}: invalid artifact path.")
                    continue
                path = (directory / artifact).resolve()
                if not path.is_relative_to(directory.resolve()) or not path.is_file() or path.stat().st_size == 0:
                    errors.append(f"{identity}: missing, empty or out-of-directory artifact {artifact}.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        report = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("Evidence root must be a JSON object.")
        errors = validate_evidence(report, args.commit, args.evidence.parent)
    except (OSError, ValueError) as error:
        errors = [str(error)]
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: current-head acceptance evidence for {args.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
