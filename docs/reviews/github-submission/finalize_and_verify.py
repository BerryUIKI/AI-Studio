"""Finalize the review tracker and verify all submitted GitHub issues."""

import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = "BerryUIKI/AI-Studio"


def command(arguments: list[str]) -> str:
    response = subprocess.run(["gh", *arguments], capture_output=True, text=True, encoding="utf-8", timeout=120)
    if response.returncode:
        raise RuntimeError(response.stderr)
    return response.stdout


def finalize() -> None:
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    journal = json.loads((OUT / "published.json").read_text(encoding="utf-8"))
    assert all(row["finding"] in journal for row in manifest), "Complete publication before finalizing."
    tracker = journal["tracker"]
    groups = []
    for priority in ("P1", "P2"):
        rows = [row for row in manifest if row["priority"] == priority]
        heading = "Proposed first-release blockers" if priority == "P1" else "Material improvements and validation"
        groups.append(f"### {priority}: {heading}\n\n" + "\n".join(f"- [ ] #{journal[row['finding']]['number']} — **{row['finding']}**: {row['title']}" for row in rows))
    tracker_body = (OUT / "tracker.md").read_text(encoding="utf-8")
    tracker_body = tracker_body.replace("Individual issues will be linked here after submission and verified as sub-issues of this tracker.", "\n\n".join(groups))
    complete_path = OUT / "tracker-final.md"
    complete_path.write_text(tracker_body, encoding="utf-8")
    print(command(["issue", "edit", str(tracker["number"]), "--repo", REPO, "--body-file", str(complete_path)]), flush=True)

    remote = json.loads(command(["issue", "list", "--repo", REPO, "--state", "all", "--limit", "300", "--json", "number,title,url,body,labels,state,assignees"]))
    remote_map = {row["number"]: row for row in remote}
    children = json.loads(command(["api", f"repos/{REPO}/issues/{tracker['number']}/sub_issues", "--paginate", "--slurp"]))
    child_ids = {row["number"] for page in children for row in page}
    expected_ids = {journal[row["finding"]]["number"] for row in manifest}
    assert expected_ids.issubset(child_ids), f"Missing native sub-issues: {expected_ids - child_ids}"
    assert len(expected_ids) == 44
    for draft in manifest:
        published = remote_map[journal[draft["finding"]]["number"]]
        assert published["state"] == "OPEN", draft["finding"]
        assert published["title"] == draft["title"], draft["finding"]
        assert not published["assignees"], draft["finding"]
        assert {label["name"] for label in published["labels"]} == set(draft["labels"]), draft["finding"]
        body = published["body"]
        assert f"berry-review:2026-10-05:{draft['finding']}" in body
        assert "## Acceptance criteria" in body and "## Reproduction or validation" in body
        assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", body)
        if draft["finding"] == "F23":
            assert "github.com/user-attachments/" in body, "Screenshot/fixture attachment was not uploaded."
            assert "./upscale-wrong-dimensions.jpg" not in body and "./landscape-fixture.png" not in body
    assert "#101" in remote_map[tracker["number"]]["body"]
    (OUT / "verified-remote-issues.json").write_text(json.dumps(remote, indent=2), encoding="utf-8")
    summary = {"tracker": tracker["url"], "findings": 44, "p1": 19, "p2": 25, "native_sub_issues_verified": len(expected_ids), "all_open": True, "labels_and_bodies_verified": True, "browser_evidence_uploaded": True}
    (OUT / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    index = f"# GitHub Submission Index: 2026-10-05 Review\n\nTracker: [{tracker['title']}]({tracker['url']})\n\nAll 44 findings are submitted as native sub-issues. Evidence levels and priority recommendations remain explicit. Existing labels were used; no assignees or milestones were imposed.\n\n| Finding | Priority | Evidence | GitHub issue |\n| --- | --- | --- | --- |\n"
    for row in manifest:
        issue = journal[row["finding"]]
        index += f"| {row['finding']} | {row['priority']} | {row['evidence']} | [#{issue['number']}: {issue['title']}]({issue['url']}) |\n"
    index += "\nThe screenshot and original 640 x 360 fixture are attached to F23. All source references are pinned to commit c1c5dbeaace01fc5e3fa68d8e3ebf410583b775b.\n"
    (OUT.parent / "2026-10-05-github-issue-index.md").write_text(index, encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    finalize()
