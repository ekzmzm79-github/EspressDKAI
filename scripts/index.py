"""최근 처리 기록(색인)을 데이터 파일에서 파생한다.

색인은 파일로 저장하지 않는다. data/days(공개·대기), data/runs(스킵),
data/decisions(거절)를 읽어 매번 만든다. 예약 실행의 AI는 수집 전에
이 출력을 보고 중복을 판단한다.

    python scripts/index.py            # 사람·AI용 요약 (한 줄에 한 항목)
    python scripts/index.py --json     # 스크립트용
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import common


def build_index(data_dir: Path = common.DATA_DIR, today: date | None = None) -> list[dict]:
    """최근 `index_days`일 처리 기록. 날짜 오름차순.

    - published: days/에 있는 항목 (main에 공개됐거나 열린 PR에서 대기 중)
    - skipped:   runs/의 skipped (AI가 기준 미달로 뺀 후보)
    - rejected:  decisions/ (사람이 뺀 항목). 같은 item_id의 published를 덮는다
    채용 항목은 마감일이 지나지 않았으면 기간이 지나도 남긴다(화면에 계속 보이므로).
    """
    today = today or common.today_kst()
    since = today - timedelta(days=common.rules()["index_days"] - 1)

    published: dict[str, dict] = {}
    for path in common.data_files("day", data_dir):
        day = common.load_json(path)
        for item in day["items"]:
            published[item["id"]] = {
                "date": day["date"],
                "section": item["section"],
                "status": "published",
                "item_id": item["id"],
                "event_key": item["event_key"],
                "title": item["title"],
                "url": item["sources"][0]["url"],
                "reason": "",
                "deadline": item.get("hiring", {}).get("deadline"),
            }

    entries: list[dict] = []
    for path in common.data_files("decision", data_dir):
        decision = common.load_json(path)
        for d in decision["items"]:
            base = published.pop(d["item_id"], None) or {
                "date": d["item_id"][:10],
                "section": None,
                "item_id": d["item_id"],
                "deadline": None,
            }
            entries.append(base | {
                "status": "rejected",
                "event_key": d["event_key"],
                "title": d.get("title", base.get("title", "")),
                "url": d["url"],
                "reason": f"사람이 제외 ({decision['via']})",
            })
    entries.extend(published.values())

    for path in common.data_files("run", data_dir):
        run = common.load_json(path)
        for section_id, section in run["sections"].items():
            for s in section["skipped"]:
                entries.append({
                    "date": run["date"],
                    "section": section_id,
                    "status": "skipped",
                    "item_id": None,
                    "event_key": s["event_key"],
                    "title": s.get("title", ""),
                    "url": s["url"],
                    "reason": s["reason"],
                    "deadline": None,
                })

    def in_window(e: dict) -> bool:
        d = date.fromisoformat(e["date"])
        if d > today:
            return False
        if d >= since:
            return True
        return bool(e["deadline"]) and date.fromisoformat(e["deadline"]) >= today

    return sorted(filter(in_window, entries), key=lambda e: (e["date"], e["item_id"] or "", e["event_key"]))


def published_urls(entries: list[dict]) -> set[str]:
    return {e["url"] for e in entries if e["status"] == "published"}


def format_text(entries: list[dict]) -> str:
    if not entries:
        return "최근 처리 기록 없음"
    lines = []
    for e in entries:
        tail = f" | {e['reason']}" if e["reason"] else ""
        deadline = f" | 마감 {e['deadline']}" if e["deadline"] else ""
        lines.append(f"{e['date']} {e['section'] or '-'} {e['status']} | {e['event_key']} | {e['url']}{deadline}{tail}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=common.DATA_DIR)
    parser.add_argument("--today", type=date.fromisoformat, help="기준일 (기본: KST 오늘)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entries = build_index(args.data_dir, args.today)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(format_text(entries))


if __name__ == "__main__":
    main()
