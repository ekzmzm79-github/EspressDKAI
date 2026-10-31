"""이어 쓰기 PR 흐름. 로컬 bare 저장소를 origin으로 두고 GitHub API는 가짜로 바꾼다."""

import shutil
import subprocess

import pytest

import briefing_branch
import common
import pr_summary
from conftest import SAMPLE_DATA


def run(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class FakeGitHub:
    def __init__(self):
        self.pr = None
        self.calls = []

    def find_open_pr(self, prefix):
        return self.pr if self.pr and self.pr["head"]["ref"].startswith(prefix) else None

    def create_pr(self, branch, title, body, base="main"):
        self.pr = {"number": 1, "html_url": "https://example.com/pr/1", "title": title, "body": body,
                   "head": {"ref": branch}}
        self.calls.append("create")
        return self.pr

    def update_pr(self, number, **fields):
        self.pr |= fields
        self.calls.append("update")
        return self.pr


@pytest.fixture
def repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    run(tmp_path, "init", "-q", "-b", "main", str(work))
    run(work, "config", "user.email", "t@example.com")
    run(work, "config", "user.name", "test")
    for sub in ("days", "runs", "decisions"):
        (work / "data" / sub).mkdir(parents=True)
        (work / "data" / sub / ".gitkeep").touch()
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "init")
    run(work, "remote", "add", "origin", str(origin))
    run(work, "push", "-q", "origin", "main")

    gh = FakeGitHub()
    monkeypatch.setattr(common, "ROOT", work)
    monkeypatch.setattr(common, "DATA_DIR", work / "data")
    monkeypatch.setattr(briefing_branch, "github_pr", gh)
    return work, origin, gh


def add_day(work, day):
    for sub in ("days", "runs"):
        shutil.copy(SAMPLE_DATA / sub / f"{day}.json", work / "data" / sub / f"{day}.json")


def test_new_then_continue(repo, capsys):
    work, origin, gh = repo

    briefing_branch.prepare()
    assert "새 브리핑" in capsys.readouterr().out
    add_day(work, "2026-10-28")
    briefing_branch.publish()
    assert gh.calls == ["create"]
    assert gh.pr["title"] == "브리핑 2026-10-28"

    # 다음 날: 그사이 main에 거절 기록이 들어왔다. 사람은 아직 Merge하지 않았다
    run(work, "checkout", "-q", "main")
    shutil.copy(SAMPLE_DATA / "decisions" / "2026-10-29-1.json", work / "data" / "decisions")
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "decision")
    run(work, "push", "-q", "origin", "main")
    run(work, "branch", "-q", "-D", gh.pr["head"]["ref"])  # 새 컨테이너처럼 로컬 브랜치 없음

    briefing_branch.prepare()
    out = capsys.readouterr().out
    assert "이어 쓰기: PR #1" in out and "2026-10-28" in out
    assert (work / "data" / "decisions" / "2026-10-29-1.json").exists()  # main 변경을 받았다
    add_day(work, "2026-10-29")
    briefing_branch.publish()
    assert gh.calls == ["create", "update"]
    assert gh.pr["title"] == "브리핑 2026-10-28 ~ 2026-10-29 (2일)"
    assert "## 2026-10-28" in gh.pr["body"] and "## 2026-10-29" in gh.pr["body"]

    remote_files = run(origin, "ls-tree", "-r", "--name-only", gh.pr["head"]["ref"])
    assert "data/days/2026-10-29.json" in remote_files


def test_closed_pr_branch_is_not_reused(repo):
    """닫힌 PR의 브랜치가 원격에 남아 있으면 덮어쓰지 않고 새 이름을 쓴다(강제 푸시 없음)."""
    work, origin, gh = repo
    today = briefing_branch.PREFIX + str(common.today_kst())
    run(work, "checkout", "-q", "-b", today)
    (work / "data" / "days" / "old.txt").write_text("old")
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "old")
    run(work, "push", "-q", "origin", today)
    run(work, "checkout", "-q", "main")

    briefing_branch.prepare()
    add_day(work, "2026-10-28")
    briefing_branch.publish()
    assert gh.pr["head"]["ref"] == f"{today}-2"
    assert "data/days/old.txt" in run(origin, "ls-tree", "-r", "--name-only", today)  # 옛 브랜치는 그대로


def test_publish_rejects_paths_outside_data(repo):
    work, _, gh = repo
    briefing_branch.prepare()
    add_day(work, "2026-10-28")
    (work / "README.md").write_text("x")
    with pytest.raises(SystemExit, match="밖의 변경"):
        briefing_branch.publish()
    assert gh.calls == []


def test_publish_stops_on_invalid_data(repo):
    work, _, gh = repo
    briefing_branch.prepare()
    # 실행 기록은 published인데 하루치 브리핑 파일이 없다
    shutil.copy(SAMPLE_DATA / "runs" / "2026-10-28.json", work / "data" / "runs")
    with pytest.raises(SystemExit, match="형식 검사 실패"):
        briefing_branch.publish()
    assert gh.calls == []


def test_prepare_requires_clean_tree(repo):
    work, _, _ = repo
    (work / "stray.txt").write_text("x")
    with pytest.raises(SystemExit, match="깨끗하지"):
        briefing_branch.prepare()


def test_pending_dates():
    paths = ["data/days/2026-10-28.json", "data/runs/2026-10-28.json", "data/runs/2026-10-29.json", "data/days/.gitkeep"]
    assert briefing_branch.pending_dates(paths) == ["2026-10-28", "2026-10-29"]


def test_summary_marks_duplicate(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(SAMPLE_DATA, data)
    path = data / "days" / "2026-10-30.json"
    path.write_text(path.read_text(encoding="utf-8").replace("sample-1-price", "sample-1"), encoding="utf-8")
    body = pr_summary.summarize(["2026-10-30"], data)
    assert "중복으로 제외 예정" in body
    assert pr_summary.common.SITE_URL in body
    assert body.index("**LLM 개발사**") < body.index("**AI 채용·해커톤**")


def test_check_paths_allows_drop_record_but_publish_does_not():
    """/drop이 PR 브랜치에 남기는 거절 기록은 PR 검사를 통과하고, AI의 publish는 여전히 막는다."""
    paths = ["data/days/2026-10-28.json", "data/decisions/2026-10-30-1.json"]
    assert briefing_branch.disallowed(paths, briefing_branch.PR_ALLOWED) == []
    assert briefing_branch.disallowed(paths) == ["data/decisions/2026-10-30-1.json"]
