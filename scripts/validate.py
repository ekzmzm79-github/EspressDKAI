"""데이터 파일 형식 검사. 배포 전과 PR마다 돈다.

모든 규칙은 각 파일의 날짜를 기준으로 판정하므로, 과거 파일을 다시 검사해도
결과가 같다(예외: 미래 날짜 금지는 오늘 기준).

    python scripts/validate.py              # 오류가 있으면 종료 코드 1
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import common

QUOTE = re.compile(r"[“\"]([^”\"]*)[”\"]")


def check_day(doc: dict, path: Path, today: date) -> list[str]:
    errors = []
    rules = common.rules()
    text = rules["text"]
    sections = common.sections()
    day = date.fromisoformat(doc["date"])

    if path.stem != doc["date"]:
        errors.append(f"파일 이름과 date({doc['date']})가 다르다")
    if day > today:
        errors.append(f"미래 날짜 {doc['date']}")

    ids = [item["id"] for item in doc["items"]]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"{dup}: id 중복")
    if doc["headline"]["item_id"] not in ids:
        errors.append(f"headline.item_id {doc['headline']['item_id']}가 items에 없다")
    if len(doc["headline"]["text"]) > text["headline_max_chars"]:
        errors.append(f"headline: {text['headline_max_chars']}자 초과")

    for item in doc["items"]:
        errors += [f"{item['id']}: {e}" for e in check_item(item, day, sections, rules)]
    return errors


def check_item(item: dict, day: date, sections: dict, rules: dict) -> list[str]:
    errors = []
    text = rules["text"]
    quote = rules["quote"]

    if not item["id"].startswith(doc_prefix := day.isoformat()):
        errors.append(f"id가 파일 날짜 {doc_prefix}로 시작하지 않는다")

    section = sections.get(item["section"])
    if section is None or not section["public"]:
        errors.append(f"공개 섹션이 아니다: {item['section']}")
        return errors

    if len(item["title"]) > text["title_max_chars"]:
        errors.append(f"제목 {text['title_max_chars']}자 초과")
    if not text["card_lines_min"] <= len(item["card"]) <= text["card_lines_max"]:
        errors.append(f"카드 {text['card_lines_min']}~{text['card_lines_max']}줄이어야 한다 (지금 {len(item['card'])}줄)")
    for n, line in enumerate(item["card"], 1):
        if len(line) > text["card_line_max_chars"]:
            errors.append(f"카드 {n}번째 줄 {text['card_line_max_chars']}자 초과")
    if len(item["detail"]) > text["detail_max_chars"]:
        errors.append(f"상세 {text['detail_max_chars']}자 초과")

    quotes = [q for field in [item["title"], *item["card"], item["detail"]] for q in QUOTE.findall(field)]
    if len(quotes) > quote["max_per_item"]:
        errors.append(f"인용 {len(quotes)}회 (최대 {quote['max_per_item']}회)")
    for q in quotes:
        if len(q) > quote["max_chars"]:
            errors.append(f"인용 {len(q)}자 (최대 {quote['max_chars']}자): {q[:20]}…")

    # 첫 번째 출처가 원문. 발행일이 섹션 수집 기간 안이어야 한다
    published = date.fromisoformat(item["sources"][0]["published"])
    window = section["window"]
    earliest = day - (timedelta(days=window["days"]) if "days" in window else timedelta(hours=window["hours"]))
    if not earliest <= published <= day:
        errors.append(f"원문 발행일 {published}이 수집 기간({earliest}~{day}) 밖")

    if hiring := item.get("hiring"):
        deadline = date.fromisoformat(hiring["deadline"])
        if deadline < day:
            errors.append(f"이미 마감됨 ({deadline})")
        if "apply_start" in hiring and date.fromisoformat(hiring["apply_start"]) > deadline:
            errors.append("접수 시작일이 마감일보다 늦다")
    return errors


def check_run(doc: dict, path: Path, today: date, data_dir: Path) -> list[str]:
    errors = []
    if path.stem != doc["date"]:
        errors.append(f"파일 이름과 date({doc['date']})가 다르다")
    if date.fromisoformat(doc["date"]) > today:
        errors.append(f"미래 날짜 {doc['date']}")
    started = datetime.fromisoformat(doc["started_at"]).astimezone(common.KST).date().isoformat()
    if started != doc["date"]:
        errors.append(f"started_at(KST {started})과 date가 다르다")
    for section_id, s in doc["sections"].items():
        if s["passed"] > s["candidates"]:
            errors.append(f"{section_id}: passed가 candidates보다 많다")

    day_file = data_dir / "days" / f"{doc['date']}.json"
    if doc["status"] == "published" and not day_file.exists():
        errors.append("status가 published인데 같은 날짜의 days 파일이 없다")
    if doc["status"] == "empty" and day_file.exists():
        errors.append("status가 empty인데 같은 날짜의 days 파일이 있다")
    return errors


def check_decision(doc: dict, path: Path) -> list[str]:
    decided = datetime.fromisoformat(doc["decided_at"]).astimezone(common.KST).date()
    if decided.isoformat() != path.stem[:10]:
        return [f"파일 이름 날짜와 decided_at(KST {decided})이 다르다"]
    return []


def validate(data_dir: Path = common.DATA_DIR, today: date | None = None) -> tuple[int, dict[Path, list[str]]]:
    """(검사한 파일 수, 파일별 오류). 오류 없는 파일은 결과에 없다."""
    today = today or common.today_kst()
    results: dict[Path, list[str]] = {}
    count = 0
    for kind in common.KINDS:
        for path in common.data_files(kind, data_dir):
            count += 1
            doc = common.load_json(path)
            errors = [
                f"스키마: {'/'.join(map(str, e.absolute_path)) or '(최상위)'}: {e.message}"
                for e in common.validator(kind).iter_errors(doc)
            ]
            if not errors:  # 스키마가 맞아야 내용 규칙을 볼 수 있다
                if kind == "day":
                    errors = check_day(doc, path, today)
                elif kind == "run":
                    errors = check_run(doc, path, today, data_dir)
                else:
                    errors = check_decision(doc, path)
            if errors:
                results[path] = errors
    return count, results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=common.DATA_DIR)
    parser.add_argument("--today", type=date.fromisoformat, help="기준일 (기본: KST 오늘)")
    args = parser.parse_args()

    count, results = validate(args.data_dir, args.today)
    total = sum(map(len, results.values()))
    for path, errors in results.items():
        for e in errors:
            print(f"{path.parent.name}/{path.name}: {e}")
    print(f"검사 {count}개 파일, 오류 {total}개")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
