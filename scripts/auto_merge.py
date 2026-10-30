"""정오 자동 Merge (계획서 C8). auto-merge 워크플로가 부른다.

열린 브리핑 PR이 있고, `hold` 라벨이 없고, 필수 검사가 모두 통과했으면 Merge한다.
Merge는 GitHub App 토큰으로 하므로 main push가 deploy 워크플로를 깨운다.
"""

from __future__ import annotations

import os
import sys

import github_pr

PREFIX = os.environ.get("BRIEFING_PREFIX", "claude/briefing-")
REQUIRED = {"validate", "pytest"}
HOLD = "hold"


def decide(pr: dict | None, check_runs: list[dict]) -> tuple[bool, str]:
    """(Merge할지, 이유)."""
    if pr is None:
        return False, "열린 브리핑 PR 없음"
    if HOLD in {label["name"] for label in pr.get("labels", [])}:
        return False, f"PR #{pr['number']}에 {HOLD} 라벨"
    if pr.get("draft"):
        return False, f"PR #{pr['number']}은 초안"
    runs = {r["name"]: r for r in check_runs}
    missing = REQUIRED - runs.keys()
    if missing:
        return False, f"검사 없음: {', '.join(sorted(missing))}"
    for r in check_runs:
        if r["status"] != "completed":
            return False, f"검사 진행 중: {r['name']}"
        if r["conclusion"] not in ("success", "skipped", "neutral"):
            return False, f"검사 실패: {r['name']} ({r['conclusion']})"
    return True, f"PR #{pr['number']} 검사 통과"


def main() -> None:
    pr = github_pr.find_open_pr(PREFIX)
    checks = github_pr.api(f"commits/{pr['head']['sha']}/check-runs?per_page=100")["check_runs"] if pr else []
    ok, reason = decide(pr, checks)
    print(reason)
    if not ok:
        return
    github_pr.api(f"pulls/{pr['number']}/merge", "PUT", {"merge_method": "merge", "sha": pr["head"]["sha"]})
    print(f"Merge: {pr['html_url']}")


if __name__ == "__main__":
    sys.exit(main())
