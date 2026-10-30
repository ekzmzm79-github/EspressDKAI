"""스크립트 공통: 경로, KST 날짜, 설정·데이터·스키마 로딩."""

from __future__ import annotations

import json
from datetime import date, datetime
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
