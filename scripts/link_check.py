"""PR에 새로 들어온 항목의 원문 링크 응답 확인. 경고만 하고 실패시키지 않는다(계획서 C5).

언론·기업 사이트 다수가 GitHub Actions에서 오는 요청을 막으므로, 실패는 "확인 필요"일 뿐이다.

    python scripts/link_check.py                 # 결과 출력
    python scripts/link_check.py --comment 12    # PR #12에 코멘트로 남김 (Actions)
"""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request

import briefing_branch
import common
import github_pr

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EspressDKAI link check)"}


def status(url: str) -> str | None:
    """문제가 없으면 None, 있으면 이유."""
    last = None
    for method in ("HEAD", "GET", "GET"):  # HEAD를 거부하는 곳이 있어 GET으로 한 번 더, 재시도 1회
        try:
            req = urllib.request.Request(url, method=method, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status < 400:
                    return None
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except Exception as e:  # 연결 실패, 시간 초과
            last = type(e).__name__
    return last


def check(base: str) -> list[tuple[str, str, str]]:
    """(항목 ID, URL, 이유) 목록."""
    failures = []
    for d in briefing_branch.pending_dates(briefing_branch.changed_paths(base)):
        path = common.DATA_DIR / "days" / f"{d}.json"
        if not path.exists():
            continue
        for item in common.load_json(path)["items"]:
            for src in item["sources"]:
                if reason := status(src["url"]):
                    failures.append((item["id"], src["url"], reason))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--comment", type=int, metavar="PR")
    args = parser.parse_args()

    failures = check(args.base)
    if failures:
        body = "⚠️ **원문 링크 확인 필요** (배포는 막지 않음)\n\n" + "\n".join(
            f"- `{item_id}` {url} — {reason}" for item_id, url, reason in failures
        )
    else:
        body = "✅ 원문 링크 모두 응답"
    print(body)
    if args.comment and failures:
        github_pr.comment(args.comment, body, marker="link-check")


if __name__ == "__main__":
    main()
