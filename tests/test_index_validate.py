import json
import shutil
from datetime import date

import pytest

import index
import validate
from conftest import SAMPLE_DATA

TODAY = date(2026, 10, 30)


@pytest.fixture
def data(tmp_path):
    """샘플 데이터 복사본. 테스트마다 고쳐 쓴다."""
    dst = tmp_path / "data"
    shutil.copytree(SAMPLE_DATA, dst)
    return dst


def edit(path, fn):
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def errors_of(data, today=TODAY):
    _, results = validate.validate(data, today)
    return [e for errs in results.values() for e in errs]


# ---------- index ----------

def test_index_statuses():
    entries = index.build_index(SAMPLE_DATA, TODAY)
    by_status = {s: [e for e in entries if e["status"] == s] for s in ("published", "skipped", "rejected")}
    assert len(by_status["published"]) == 6
    assert len(by_status["skipped"]) == 3
    assert [e["url"] for e in by_status["rejected"]] == ["https://example.com/news/rumor"]


def test_index_window_keeps_open_hiring_only():
    entries = index.build_index(SAMPLE_DATA, date(2026, 11, 6))
    assert [e["event_key"] for e in entries] == ["예시전자 AI 해커톤 본선, 11월 11일"]


def test_index_ignores_future_files():
    assert all(e["date"] <= "2026-10-28" for e in index.build_index(SAMPLE_DATA, date(2026, 10, 28)))


def test_rejection_overrides_published(data):
    (data / "decisions" / "2026-10-30-1.json").write_text(json.dumps({
        "decided_at": "2026-10-30T09:00:00+09:00", "via": "pr-closed", "pr": 3,
        "items": [{"item_id": "2026-10-30-02", "status": "rejected",
                   "event_key": "예시랩 샘플-1 가격 인하", "url": "https://example.com/news/sample-1-price"}],
    }, ensure_ascii=False), encoding="utf-8")
    entries = [e for e in index.build_index(data, TODAY) if e["item_id"] == "2026-10-30-02"]
    assert [e["status"] for e in entries] == ["rejected"]
    assert entries[0]["section"] == "llm"
    assert "https://example.com/news/sample-1-price" not in index.published_urls(index.build_index(data, TODAY))


# ---------- validate ----------

def test_sample_is_valid():
    count, results = validate.validate(SAMPLE_DATA, TODAY)
    assert count == 8 and results == {}


def test_future_date_rejected():
    assert any("미래 날짜" in e for e in errors_of(SAMPLE_DATA, date(2026, 10, 29)))


DAY = "days/2026-10-28.json"


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d["items"][0].update(id="2026-10-27-01"), "id가 파일 날짜"),
    (lambda d: d["items"][1].update(id="2026-10-28-01"), "id 중복"),
    (lambda d: d["headline"].update(item_id="2026-10-28-09"), "headline.item_id"),
    (lambda d: d["items"][0].update(title="가" * 61), "제목 60자 초과"),
    (lambda d: d["items"][0].update(card=["한 줄"]), "카드 2~3줄"),
    (lambda d: d["items"][0].update(card=["가" * 81, "둘"]), "카드 1번째 줄"),
    (lambda d: d["items"][0].update(detail="가" * 601), "상세 600자 초과"),
    (lambda d: d["items"][0].update(detail="그는 “" + "가" * 41 + "”라고 했다"), "인용 41자"),
    (lambda d: d["items"][0].update(detail="“하나”와 \"둘\""), "인용 2회"),
    (lambda d: d["items"][0]["sources"][0].update(published="2026-10-25"), "수집 기간"),
    (lambda d: d["items"][2]["sources"][0].update(published="2026-10-20"), "수집 기간"),
    (lambda d: d["items"][2]["hiring"].update(deadline="2026-10-27"), "이미 마감됨"),
    (lambda d: d["items"][2]["hiring"].update(apply_start="2026-11-12"), "접수 시작일"),
    (lambda d: d["items"][0].update(section="economy"), "스키마"),
])
def test_day_rules(data, mutate, expected):
    edit(data / DAY, mutate)
    errors = errors_of(data)
    assert any(expected in e for e in errors), errors


def test_quote_within_limit_passes(data):
    edit(data / DAY, lambda d: d["items"][0].update(detail="그는 “" + "가" * 40 + "”라고 했다"))
    assert errors_of(data) == []


def test_hiring_window_is_seven_days(data):
    edit(data / DAY, lambda d: d["items"][2]["sources"][0].update(published="2026-10-21"))
    assert errors_of(data) == []


def test_file_name_must_match_date(data):
    (data / DAY).rename(data / "days" / "2026-10-27.json")
    assert any("파일 이름" in e for e in errors_of(data))


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d.update(started_at="2026-10-27T23:00:00+00:00"), None),  # UTC 27일 23시 = KST 28일 8시
    (lambda d: d.update(started_at="2026-10-28T16:00:00+00:00"), "started_at"),  # UTC 28일 16시 = KST 29일 1시
    (lambda d: d["sections"]["llm"].update(passed=9), "passed가 candidates"),
    (lambda d: d.update(status="empty"), "status가 empty"),
])
def test_run_rules(data, mutate, expected):
    edit(data / "runs" / "2026-10-28.json", mutate)
    errors = errors_of(data)
    if expected is None:
        assert errors == []
    else:
        assert any(expected in e for e in errors), errors


def test_run_published_needs_day_file(data):
    (data / DAY).unlink()
    assert any("days 파일이 없다" in e for e in errors_of(data))


def test_decision_date_must_match_file_name(data):
    edit(data / "decisions" / "2026-10-29-1.json", lambda d: d.update(decided_at="2026-10-29T20:00:00+00:00"))
    assert any("decided_at" in e for e in errors_of(data))


def test_cli_exit_code(data, capsys):
    edit(data / DAY, lambda d: d["items"][0].update(title="가" * 61))
    with pytest.raises(SystemExit) as exc:
        import sys
        sys.argv = ["validate.py", "--data-dir", str(data), "--today", "2026-10-30"]
        validate.main()
    assert exc.value.code == 1
    assert "오류 1개" in capsys.readouterr().out
