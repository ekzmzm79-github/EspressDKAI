import copy
from datetime import date, datetime

import pytest

import common
from conftest import SAMPLE_DATA


@pytest.mark.parametrize("kind", common.KINDS)
def test_sample_data_matches_schema(kind):
    files = common.data_files(kind, SAMPLE_DATA)
    assert files, f"{kind} 샘플이 없다"
    for path in files:
        errors = list(common.validator(kind).iter_errors(common.load_json(path)))
        assert not errors, f"{path.name}: {errors[0].message}"


def _day():
    return common.load_json(SAMPLE_DATA / "days" / "2026-10-28.json")


def _errors(doc):
    return list(common.validator("day").iter_errors(doc))


def test_hiring_item_requires_hiring_block():
    doc = _day()
    hiring_item = next(i for i in doc["items"] if i["section"] == "hiring")
    del hiring_item["hiring"]
    assert _errors(doc)


def test_llm_item_rejects_hiring_block():
    doc = _day()
    llm_item = next(i for i in doc["items"] if i["section"] == "llm")
    llm_item["hiring"] = copy.deepcopy(doc["items"][2]["hiring"])
    assert _errors(doc)


def test_date_format_is_checked():
    doc = _day()
    doc["items"][0]["sources"][0]["published"] = "2026/10/27"
    assert _errors(doc)


def test_datetime_format_is_checked():
    run = common.load_json(SAMPLE_DATA / "runs" / "2026-10-28.json")
    run["started_at"] = "2026-10-28 07:23"
    assert list(common.validator("run").iter_errors(run))


def test_sections_config():
    secs = common.sections()
    assert set(secs) == {"llm", "hiring"}
    assert all(s["public"] for s in secs.values())


def test_kst_date():
    now = common.now_kst()
    assert now.utcoffset().total_seconds() == 9 * 3600
    assert common.today_kst() == now.date()


def test_file_date():
    assert common.file_date(SAMPLE_DATA / "decisions" / "2026-10-29-1.json") == date(2026, 10, 29)
