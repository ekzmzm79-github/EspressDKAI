import json
import shutil
from datetime import date

import pytest

import build
from conftest import SAMPLE_DATA

TODAY = date(2026, 10, 30)


@pytest.fixture
def data(tmp_path):
    dst = tmp_path / "data"
    shutil.copytree(SAMPLE_DATA, dst)
    return dst


def write_day(data, day, items):
    doc = {"date": day, "headline": {"item_id": items[0]["id"], "text": "한 줄"}, "items": items}
    (data / "days" / f"{day}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def sample_item(item_id, url, published, **extra):
    base = json.loads((SAMPLE_DATA / "days" / "2026-10-29.json").read_text(encoding="utf-8"))["items"][0]
    base = base | {"id": item_id, "sources": [{"title": "원문", "url": url, "published": published}]}
    return base | extra


def ids(payload):
    return [i["id"] for d in payload["days"] for i in d["items"]]


def test_sample_payload():
    payload = build.collect(SAMPLE_DATA, TODAY)
    assert [d["date"] for d in payload["days"]] == ["2026-10-28", "2026-10-29", "2026-10-30"]
    assert len(ids(payload)) == 6
    assert payload["last_run"] == {"date": "2026-10-30", "status": "published", "candidates": 2, "passed": 2, "verification_edits": 0}
    assert payload["excluded"] == []


def test_duplicate_url_within_window_is_excluded(data):
    write_day(data, "2026-10-31", [sample_item("2026-10-31-01", "https://example.com/news/sample-1", "2026-10-31")])
    payload = build.collect(data, date(2026, 10, 31))
    assert "2026-10-31-01" not in ids(payload)
    assert payload["excluded"] == [{"item_id": "2026-10-31-01", "url": "https://example.com/news/sample-1", "first_seen": "2026-10-28"}]


def test_duplicate_url_after_window_is_allowed(data):
    write_day(data, "2026-11-04", [sample_item("2026-11-04-01", "https://example.com/news/sample-1", "2026-11-04")])
    assert "2026-11-04-01" in ids(build.collect(data, date(2026, 11, 4)))


def test_rejected_items_are_hidden(data):
    (data / "decisions" / "2026-10-30-1.json").write_text(json.dumps({
        "decided_at": "2026-10-30T09:00:00+09:00", "via": "drop",
        "items": [{"item_id": "2026-10-30-02", "status": "rejected", "event_key": "x", "url": "https://example.com/x"}],
    }), encoding="utf-8")
    assert "2026-10-30-02" not in ids(build.collect(data, TODAY))


def test_future_days_are_skipped():
    assert [d["date"] for d in build.collect(SAMPLE_DATA, date(2026, 10, 29))["days"]] == ["2026-10-28", "2026-10-29"]


def test_old_days_keep_only_open_hiring(data):
    path = data / "days" / "2026-10-28.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["items"][2]["hiring"]["deadline"] = "2026-12-31"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert len(ids(build.collect(data, date(2026, 11, 10)))) == 6  # 30일 안이라 모두 남는다
    assert ids(build.collect(data, date(2026, 11, 29))) == ["2026-10-28-03"]  # 30일 밖: 마감 전 채용만


def test_build_writes_site(data, tmp_path):
    item = sample_item("2026-10-31-01", "https://example.com/new", "2026-10-31", title="</script><b>x</b>")
    write_day(data, "2026-10-31", [item])
    out = tmp_path / "site"
    build.build(data, out, date(2026, 10, 31))
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "</script><b>" not in html  # 데이터 속 태그가 스크립트 블록을 끊지 못한다
    assert (out / "static" / "app.js").exists() and (out / ".nojekyll").exists()
    assert json.loads((out / "briefing.json").read_text(encoding="utf-8"))["days"][-1]["date"] == "2026-10-31"


def test_empty_data(tmp_path):
    empty = tmp_path / "data"
    for sub in ("days", "runs", "decisions"):
        (empty / sub).mkdir(parents=True)
    payload = build.build(empty, tmp_path / "site", TODAY)
    assert payload["days"] == [] and payload["last_run"] is None
