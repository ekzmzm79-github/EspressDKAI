"""예약 실행의 브랜치·PR 처리. AI는 판단하지 않고 이 스크립트를 부른다.

    python scripts/briefing_branch.py prepare             # 수집 전: 이어 쓸 브랜치 준비
    python scripts/briefing_branch.py publish             # 작성 후: 검사 → 커밋 → 푸시 → PR 생성·갱신
    python scripts/briefing_branch.py check-paths         # PR이 data/days, data/runs 밖을 고쳤는지

열린 브리핑 PR이 있으면 그 브랜치에 이어 쓰고(계획서 C2), 없으면 main에서
`claude/briefing-<KST 날짜>` 브랜치를 새로 만든다. 브랜치를 덮어쓰지 않으므로
강제 푸시가 필요 없다. 두 섹션 모두 비는 날도 같은 브랜치에 runs 파일만 올린다.
data/runs만 바뀐 PR은 auto-merge-log 워크플로가 자동 Merge한다.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import common
import github_pr
import pr_summary
import validate

PREFIX = os.environ.get("BRIEFING_PREFIX", "claude/briefing-")
BASE = os.environ.get("BRIEFING_BASE", "main")
ALLOWED = ("data/days/", "data/runs/")


def git(*args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=common.ROOT, capture_output=True, text=True)
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {out.stderr.strip()}")
    return out.stdout.strip()


def fetch(branch: str) -> None:
    git("fetch", "-q", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")


def remote_branches() -> set[str]:
    refs = git("ls-remote", "--heads", "origin", f"{PREFIX}*").splitlines()
    return {line.split("refs/heads/", 1)[1] for line in refs}


def new_branch_name() -> str:
    """claude/briefing-<오늘>. 같은 날 닫힌 PR의 브랜치가 남아 있으면 -2, -3…"""
    name = f"{PREFIX}{common.today_kst()}"
    taken = remote_branches()
    n = 1
    while (candidate := name if n == 1 else f"{name}-{n}") in taken:
        n += 1
    return candidate


def changed_paths(base: str = f"origin/{BASE}") -> list[str]:
    """base 이후 바뀐 파일 (커밋된 것 + 아직 커밋 안 한 것)."""
    committed = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    pending = [line[3:] for line in git("status", "--porcelain", "--untracked-files=all").splitlines()]
    return sorted(set(committed) | set(pending))


def disallowed(paths: list[str]) -> list[str]:
    return [p for p in paths if not p.startswith(ALLOWED)]


def pending_dates(paths: list[str]) -> list[str]:
    return sorted({p.rsplit("/", 1)[-1][:10] for p in paths if p.startswith(ALLOWED) and p.endswith(".json")})


def prepare() -> None:
    if git("status", "--porcelain"):
        sys.exit("작업 트리가 깨끗하지 않다. 정리한 뒤 다시 실행한다.")
    fetch(BASE)
    pr = github_pr.find_open_pr(PREFIX)
    if pr:
        branch = pr["head"]["ref"]
        fetch(branch)
        git("checkout", "-q", "-B", branch, f"origin/{branch}")
        # 그사이 main에 들어온 것(거절 기록, 코드 변경)을 받는다. 데이터는 날짜별 파일이라 충돌하지 않는다
        if subprocess.run(["git", "merge", "-q", "--no-edit", f"origin/{BASE}"], cwd=common.ROOT, capture_output=True).returncode:
            git("merge", "--abort", check=False)
            sys.exit(f"{BASE}를 {branch}에 합치다 충돌. 사람이 확인해야 한다 (PR #{pr['number']})")
        dates = pending_dates(changed_paths())
        print(f"이어 쓰기: PR #{pr['number']} ({branch}) · 대기 중인 날짜 {', '.join(dates) or '없음'}")
    else:
        branch = new_branch_name()
        git("checkout", "-q", "-B", branch, f"origin/{BASE}")
        print(f"새 브리핑: {branch}를 {BASE}에서 시작")
    print(f"오늘(KST): {common.today_kst()}")


def publish() -> None:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch.startswith(PREFIX):
        sys.exit(f"브리핑 브랜치가 아니다 (지금 {branch}). prepare를 먼저 실행한다.")

    paths = changed_paths()
    if bad := disallowed(paths):
        sys.exit("data/days, data/runs 밖의 변경이 있다:\n" + "\n".join(f"  {p}" for p in bad))
    if not paths:
        sys.exit("올릴 변경이 없다.")

    count, results = validate.validate(common.DATA_DIR)
    if results:
        for path, errors in results.items():
            for e in errors:
                print(f"{path.parent.name}/{path.name}: {e}")
        sys.exit(f"형식 검사 실패: 오류 {sum(map(len, results.values()))}개. 고친 뒤 다시 publish한다.")

    dates = pending_dates(paths)
    git("add", "data/days", "data/runs")
    if git("diff", "--cached", "--name-only"):
        git("commit", "-q", "-m", f"briefing: {', '.join(dates)}")
    git("push", "-q", "origin", f"{branch}:{branch}")

    body = pr_summary.summarize(dates, common.DATA_DIR)
    title = pr_summary.title(dates)
    pr = github_pr.find_open_pr(PREFIX)
    if pr and pr["head"]["ref"] == branch:
        pr = github_pr.update_pr(pr["number"], title=title, body=body)
        action = "갱신"
    else:
        pr = github_pr.create_pr(branch, title, body, BASE)
        action = "생성"
    print(f"PR {action}: {pr['html_url']} · 날짜 {', '.join(dates)}")


def check_paths(base: str) -> None:
    bad = disallowed(changed_paths(base))
    if bad:
        print("브리핑 PR은 data/days, data/runs만 바꿀 수 있다. 범위 밖 변경:")
        print("\n".join(f"  {p}" for p in bad))
        sys.exit(1)
    print("변경 범위 확인: data/days, data/runs만 바뀜")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    sub.add_parser("publish")
    p = sub.add_parser("check-paths")
    p.add_argument("--base", default=f"origin/{BASE}")
    args = parser.parse_args()

    if args.cmd == "prepare":
        prepare()
    elif args.cmd == "publish":
        publish()
    else:
        check_paths(args.base)


if __name__ == "__main__":
    main()
