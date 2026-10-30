import json
import shutil
import subprocess
from datetime import datetime, date

import pytest

import auto_merge
import common
import decisions
import validate
from conftest import SAMPLE_DATA

NOW = datetime(2026, 10, 30, 9, 15, tzinfo=common.KST)


@pytest.fixture
def data(tmp_path):
    dst = tmp_path / "data"
    shutil.copytree(SAMPLE_DATA, dst)
    return dst


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("comment, expected", [
    ("/drop 2026-10-28-01", ["2026-10-28-01"]),
    ("/drop 2026-10-28-01 2026-10-28-03\n이건 무시", ["2026-10-28-01", "2026-10-28-03"]),
    ("/drop", []),
    ("좋아요 /drop 2026-10-28-01", None),
    ("", None),
])
def test_parse_drop(comment, expected):
    assert decisions.parse_drop(comment) == expected


def test_drop_some_items(data):
    dropped, unknown = decisions.drop(data, ["2026-10-28-01", "2026-10-28-09"], 7, NOW)
    assert dropped == ["2026-10-28-01"] and unknown == ["2026-10-28-09"]
    day = load(data / "days" / "2026-10-28.json")
    assert [i["id"] for i in day["items"]] == ["2026-10-28-02", "2026-10-28-03"]
    assert day["headline"]["item_id"] == "2026-10-28-02"  # 한 줄이 가리키던 항목이 빠져 다음 항목으로
    decision = load(data / "decisions" / "2026-10-30-1.json")
    assert decision["via"] == "drop" and decision["pr"] == 7
    assert decision["items"][0]["url"] == "https://example.com/news/sample-1"
    assert validate.validate(data, date(2026, 10, 30))[1] == {}


def test_drop_whole_day(data):
    dropped, _ = decisions.drop(data, ["2026-10-29-01"], 7, NOW)
    assert dropped == ["2026-10-29-01"]
    assert not (data / "days" / "2026-10-29.json").exists()
    assert load(data / "runs" / "2026-10-29.json")["status"] == "empty"
    assert validate.validate(data, date(2026, 10, 30))[1] == {}


def test_drop_nothing_found_writes_nothing(data):
    dropped, unknown = decisions.drop(data, ["2026-10-20-01"], 7, NOW)
    assert dropped == [] and unknown == ["2026-10-20-01"]
    assert not (data / "decisions" / "2026-10-30-1.json").exists()


def test_decision_file_numbering(data):
    decisions.drop(data, ["2026-10-28-01"], 7, NOW)
    decisions.drop(data, ["2026-10-28-02"], 7, NOW)
    assert (data / "decisions" / "2026-10-30-2.json").exists()


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_record_close(tmp_path, monkeypatch):
    work = tmp_path / "work"
    for sub in ("days", "runs", "decisions"):
        (work / "data" / sub).mkdir(parents=True)
        (work / "data" / sub / ".gitkeep").touch()
    git(tmp_path, "init", "-q", "-b", "main", str(work))
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "test")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "init")
    # 닫힐 PR 브랜치: 이틀 치 + PR 안에서 /drop한 기록
    git(work, "checkout", "-q", "-b", "claude/briefing-2026-10-28")
    for day in ("2026-10-28", "2026-10-29"):
        for sub in ("days", "runs"):
            shutil.copy(SAMPLE_DATA / sub / f"{day}.json", work / "data" / sub)
    decisions.drop(work / "data", ["2026-10-28-02"], 7, NOW)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "briefing")
    git(work, "checkout", "-q", "main")

    monkeypatch.setattr(common, "ROOT", work)
    recorded = decisions.record_close(work / "data", "claude/briefing-2026-10-28", 7, NOW)
    assert sorted(recorded) == ["2026-10-28-01", "2026-10-28-02", "2026-10-28-03", "2026-10-29-01"]
    decision = load(work / "data" / "decisions" / "2026-10-30-1.json")
    assert decision["via"] == "pr-closed"
    assert validate.validate(work / "data", date(2026, 10, 30))[1] == {}


def check(name, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion}


PR = {"number": 3, "labels": [], "draft": False}


@pytest.mark.parametrize("pr, runs, ok, reason", [
    (None, [], False, "열린 브리핑 PR 없음"),
    (PR | {"labels": [{"name": "hold"}]}, [check("validate"), check("pytest")], False, "hold"),
    (PR | {"draft": True}, [check("validate"), check("pytest")], False, "초안"),
    (PR, [check("validate")], False, "검사 없음: pytest"),
    (PR, [check("validate"), check("pytest", "in_progress", None)], False, "진행 중"),
    (PR, [check("validate", conclusion="failure"), check("pytest")], False, "검사 실패"),
    (PR, [check("validate"), check("pytest"), check("merge", conclusion="skipped")], True, "검사 통과"),
])
def test_auto_merge_decide(pr, runs, ok, reason):
    result, why = auto_merge.decide(pr, runs)
    assert result is ok and reason in why
