"""데이터 → 한 장짜리 카드뉴스 페이지(_site/).

표시·접힘("N일 전", "마감 임박" 등)은 브라우저가 연 시점의 날짜로 계산한다.
여기서는 브라우저가 판단할 재료만 넉넉히 넣는다.

    python scripts/build.py                      # data/ → _site/
    python scripts/build.py --data-dir tests/fixtures/sample/data --out /tmp/site
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import common

SITE_DIR = common.ROOT / "site"
OUT_DIR = common.ROOT / "_site"

# 페이지에 넣는 기간. 배포가 며칠 없어도 브라우저가 "N일 전"을 계산할 수 있게 넉넉히
PAYLOAD_DAYS = 30


def collect(data_dir: Path, today: date) -> dict:
    """페이지 데이터. 같은 원문 URL이 최근 기간 안에 이미 나왔으면 뒤의 것을 뺀다(C11)."""
    index_days = common.rules()["index_days"]
    since = today - timedelta(days=PAYLOAD_DAYS - 1)
    rejected = {
        d["item_id"]
        for path in common.data_files("decision", data_dir)
        for d in common.load_json(path)["items"]
    }

    days, excluded = [], []
    seen: dict[str, date] = {}  # 원문 URL → 처음 나온 날짜
    for path in common.data_files("day", data_dir):
        day = common.load_json(path)
        d = date.fromisoformat(day["date"])
        if d > today:
            continue
        items = []
        for item in day["items"]:
            if item["id"] in rejected:
                continue
            url = item["sources"][0]["url"]
            first = seen.get(url)
            if first is not None and (d - first).days < index_days:
                excluded.append({"item_id": item["id"], "url": url, "first_seen": first.isoformat()})
                continue
            seen.setdefault(url, d)
            # 기간이 지난 날은 마감 전 채용 항목만 남긴다
            if d >= since or ("hiring" in item and date.fromisoformat(item["hiring"]["deadline"]) >= today):
                items.append(item)
        if items:
            days.append({"date": day["date"], "headline": day["headline"], "items": items})

    runs = common.data_files("run", data_dir)
    last_run = common.load_json(runs[-1]) if runs else None

    return {
        "built_at": common.now_kst().isoformat(timespec="minutes"),
        "sections": {s["id"]: {"title": s["title"]} for s in common.sections().values() if s["public"]},
        "days": days,
        "last_run": last_run and {
            "date": last_run["date"],
            "status": last_run["status"],
            "candidates": sum(s["candidates"] for s in last_run["sections"].values()),
            "passed": sum(s["passed"] for s in last_run["sections"].values()),
            "verification_edits": sum(s["verification_edits"] for s in last_run["sections"].values()),
        },
        "excluded": excluded,
    }


def build(data_dir: Path = common.DATA_DIR, out: Path = OUT_DIR, today: date | None = None) -> dict:
    payload = collect(data_dir, today or common.today_kst())

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_DIR / "static", out / "static")

    # <script> 안에 넣으므로 "</"를 끊어 둔다
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    env = Environment(loader=FileSystemLoader(SITE_DIR), autoescape=True)
    html = env.get_template("index.html.j2").render(data_json=data_json)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "briefing.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / ".nojekyll").touch()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=common.DATA_DIR)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--today", type=date.fromisoformat, help="기준일 (기본: KST 오늘)")
    args = parser.parse_args()

    payload = build(args.data_dir, args.out, args.today)
    items = sum(len(d["items"]) for d in payload["days"])
    print(f"{args.out}: {len(payload['days'])}일 {items}개 항목, 중복 제외 {len(payload['excluded'])}개")


if __name__ == "__main__":
    main()
