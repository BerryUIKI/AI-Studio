"""Publish reviewed issue drafts sequentially with a resumable audit journal."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REPO = "BerryUIKI/AI-Studio"
JOURNAL = OUT / "published.json"
MARKER = "berry-review:2026-10-05:"


def gh(arguments: list[str], timeout: int = 150) -> subprocess.CompletedProcess[str]:
    """Invoke GitHub CLI with an argument vector, never a composed shell body."""
    return subprocess.run(["gh", *arguments], capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def save(journal: dict[str, Any]) -> None:
    """Record each successful remote mutation before proceeding."""
    JOURNAL.write_text(json.dumps(journal, indent=2), encoding="utf-8")


def reconcile(journal: dict[str, Any]) -> None:
    """Recover already-created issues after any interrupted command."""
    response = gh(["issue", "list", "--repo", REPO, "--state", "all", "--limit", "300", "--json", "number,title,url,body,labels,state"])
    if response.returncode:
        raise RuntimeError(response.stderr)
    rows = json.loads(response.stdout)
    (OUT / "latest-remote-issues.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        match = re.search(re.escape(MARKER) + r"(tracker|F\d{2})", row.get("body", ""))
        if match:
            key = match.group(1)
            existing = journal.get(key)
            if existing and existing["number"] != row["number"]:
                raise RuntimeError(f"Duplicate review marker for {key}; triage before continuing.")
            journal[key] = {"number": row["number"], "url": row["url"], "title": row["title"]}
    save(journal)


def create(key: str, title: str, body_file: Path, labels: list[str], journal: dict[str, Any], attachments: list[Path] | None = None) -> None:
    """Create once, retaining the URL even if a later attachment/parent step fails."""
    args = ["issue", "create", "--repo", REPO, "--title", title, "--body-file", str(body_file)]
    for label in labels:
        args.extend(["--label", label])
    if key != "tracker":
        args.extend(["--parent", str(journal["tracker"]["number"])])
    for attachment in attachments or []:
        args.extend(["--attach", str(attachment)])
    response = gh(args)
    urls = re.findall(r"https://github\.com/BerryUIKI/AI-Studio/issues/(\d+)", response.stdout)
    if urls:
        number = int(urls[-1])
        journal[key] = {"number": number, "url": f"https://github.com/{REPO}/issues/{number}", "title": title}
        if response.returncode:
            journal[key]["post_creation_warning"] = response.stderr.strip()
        save(journal)
        print(f"{key}: {journal[key]['url']}", flush=True)
    if response.returncode or not urls:
        raise RuntimeError(f"Creation did not fully succeed for {key}: {response.stderr or response.stdout}. Reconcile before retrying.")


def publish(count: int) -> None:
    journal: dict[str, Any] = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {}
    reconcile(journal)
    if "tracker" not in journal:
        create("tracker", "[Tracking] First-release stabilization: 2026-10-05 product and technical review", OUT / "tracker.md", ["architecture", "enhancement"], journal)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    pending = [row for row in manifest if row["finding"] not in journal]
    for row in pending[:count]:
        attachments = None
        if row["finding"] == "F23":
            attachments = [ROOT / "docs/reviews/2026-10-05-evidence/upscale-wrong-dimensions.jpg", ROOT / "docs/reviews/2026-10-05-evidence/landscape-fixture.png"]
        create(row["finding"], row["title"], Path(row["body_file"]), row["labels"], journal, attachments)
    done = sum(row["finding"] in journal for row in manifest)
    print(json.dumps({"findings_published": done, "total": len(manifest), "tracker": journal["tracker"]["url"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=6)
    publish(parser.parse_args().count)
