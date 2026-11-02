"""스크립트 공통: 경로, KST 날짜, 설정·데이터·스키마 로딩."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
SCHEMA_DIR = ROOT / "schema"
DATA_DIR = ROOT / "data"

KST = ZoneInfo("Asia/Seoul")
SITE_URL = "https://ekzmzm79-github.github.io/EspressDKAI/"  # 배포 페이지 (GitHub Pages)

# 데이터 종류 → (data/ 아래 폴더, 스키마 파일)
KINDS = {
    "day": ("days", "day.schema.json"),
    "run": ("runs", "run.schema.json"),
    "decision": ("decisions", "decision.schema.json"),
}


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    return now_kst().date()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@cache
def rules() -> dict:
    return load_yaml(CONFIG_DIR / "rules.yaml")


@cache
def sections() -> dict[str, dict]:
    """섹션 id → 섹션 설정. order 순."""
    confs = [load_yaml(path) for path in (CONFIG_DIR / "sections").glob("*.yaml")]
    return {c["id"]: c for c in sorted(confs, key=lambda c: c["order"])}


@cache
def validator(kind: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / KINDS[kind][1])
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def data_files(kind: str, data_dir: Path = DATA_DIR) -> list[Path]:
    """종류별 데이터 파일 목록. 파일 이름(날짜) 순."""
    return sorted((data_dir / KINDS[kind][0]).glob("*.json"))


def file_date(path: Path) -> date:
    """`2026-10-30.json`, `2026-10-30-1.json` → date(2026, 10, 30)."""
    return date.fromisoformat(path.stem[:10])


# ---------- 수집 기간 ----------

def last_run_at(before: datetime, data_dir: Path = DATA_DIR) -> datetime | None:
    """`before` 이전 날짜의 마지막 실행 시작 시각(KST). 실패한 실행은 수집하지 않았으므로 건너뛴다."""
    for path in reversed(data_files("run", data_dir)):
        if file_date(path) >= before.date():
            continue
        run = load_json(path)
        if run["status"] != "failed":
            return datetime.fromisoformat(run["started_at"]).astimezone(KST)
    return None


def window_since(section: dict, now: datetime, data_dir: Path = DATA_DIR) -> datetime:
    """섹션 수집 기간의 시작 시각.

    `since_last_run`이면 직전 실행 시각부터 (루틴 주기를 바꿔도 따라간다).
    직전 실행이 없으면 `hours`(기본 24), 너무 오래됐으면 `max_days`로 자른다.
    """
    window = section["window"]
    if window.get("since_last_run"):
        floor = now - timedelta(days=window["max_days"])
        last = last_run_at(now, data_dir)
        return max(last, floor) if last else now - timedelta(hours=window.get("hours", 24))
    if "days" in window:
        return now - timedelta(days=window["days"])
    return now - timedelta(hours=window["hours"])


def window_earliest(section: dict, day: date, data_dir: Path = DATA_DIR) -> date:
    """날짜 단위 수집 기간의 첫날 (validate용). 날짜만 있는 출처를 위해 직전 실행일을 포함한다."""
    start = datetime.combine(day, datetime.min.time(), KST)
    window = section["window"]
    if window.get("since_last_run"):
        last = last_run_at(start, data_dir)
        floor = day - timedelta(days=window["max_days"])
        return max(last.date(), floor) if last else day - timedelta(days=-(-window.get("hours", 24) // 24))
    if "days" in window:
        return day - timedelta(days=window["days"])
    return day - timedelta(days=-(-window["hours"] // 24))
