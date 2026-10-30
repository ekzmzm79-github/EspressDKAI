"""GitHub PR 조회·생성·갱신 (REST API, `gh api`).

클라우드 세션에서는 GraphQL이 막혀 `gh pr ...` 명령을 쓸 수 없다(계획서 C10).
그래서 PR 조작은 모두 이 모듈을 거친다. GitHub Actions에서도 그대로 동작한다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

import common


def repo() -> str:
    """owner/repo. Actions에서는 GITHUB_REPOSITORY, 그 밖에는 origin 주소에서."""
    if env := os.environ.get("GITHUB_REPOSITORY"):
        return env
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=common.ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    match = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise RuntimeError(f"origin 주소에서 저장소를 알 수 없다: {url}")
    return match.group(1)


def api(path: str, method: str = "GET", fields: dict | None = None) -> dict | list:
    cmd = ["gh", "api", "-X", method, f"repos/{repo()}/{path}"]
    stdin = None
    if fields is not None:
        cmd += ["--input", "-"]
        stdin = json.dumps(fields)
    out = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api {method} {path} 실패: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def find_open_pr(branch: str) -> dict | None:
    owner = repo().split("/")[0]
    prs = api(f"pulls?state=open&head={owner}:{branch}")
    return prs[0] if prs else None


def create_pr(branch: str, title: str, body: str, base: str = "main") -> dict:
    return api("pulls", "POST", {"head": branch, "base": base, "title": title, "body": body})


def update_pr(number: int, **fields) -> dict:
    return api(f"pulls/{number}", "PATCH", fields)


def comment(number: int, body: str, marker: str | None = None) -> None:
    """PR 코멘트. marker가 있으면 같은 marker를 가진 기존 코멘트를 고쳐 쓴다."""
    if marker:
        body = f"<!-- {marker} -->\n{body}"
        for c in api(f"issues/{number}/comments?per_page=100"):
            if c["body"].startswith(f"<!-- {marker} -->"):
                api(f"issues/comments/{c['id']}", "PATCH", {"body": body})
                return
    api(f"issues/{number}/comments", "POST", {"body": body})
