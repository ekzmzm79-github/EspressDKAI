"""사람 결정 처리. GitHub Actions에서만 돈다.

    python scripts/decisions.py drop 12 "/drop 2026-11-03-02 2026-11-03-04" --data-dir pr/data
    python scripts/decisions.py record-close 12 origin/claude/briefing-2026-11-03  # 닫힌 PR의 항목을 거절로 기록

스크립트는 항상 main의 것을 쓴다(PR 브랜치의 코드를 실행하지 않는다). drop은 --data-dir로
PR 브랜치의 data/를 가리키고, record-close는 main 체크아웃에서 닫힌 브랜치를 git으로 읽는다.
결정은 data/decisions/<KST 날짜>-<n>.json으로 남고, 색인이 다음 날 중복 판단에 쓴다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import common

ITEM_ID = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}")


def write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rejected_entry(item: dict) -> dict:
    return {
        "item_id": item["id"],
        "status": "rejected",
        "event_key": item["event_key"],
        "title": item["title"],
        "url": item["sources"][0]["url"],
    }


def write_decision(data_dir: Path, via: str, pr: int, entries: list[dict], now: datetime) -> Path:
    day = now.astimezone(common.KST).date().isoformat()
    n = 1
    while (path := data_dir / "decisions" / f"{day}-{n}.json").exists():
        n += 1
    write_json(path, {
        "decided_at": now.astimezone(common.KST).isoformat(timespec="seconds"),
        "via": via,
        "pr": pr,
        "items": entries,
    })
    return path


def parse_drop(comment: str) -> list[str] | None:
    """`/drop <id> ...` 이면 id 목록, 아니면 None. 첫 줄만 본다."""
    first = comment.strip().splitlines()[0] if comment.strip() else ""
    if not first.startswith("/drop"):
        return None
    return ITEM_ID.findall(first)


def drop(data_dir: Path, ids: list[str], pr: int, now: datetime) -> tuple[list[str], list[str]]:
    """(제외한 id, 찾지 못한 id). 하루치가 모두 빠지면 days 파일을 지우고 실행 기록을 empty로 바꾼다."""
    dropped_items, unknown = [], []
    by_date: dict[str, list[str]] = {}
    for item_id in dict.fromkeys(ids):
        by_date.setdefault(item_id[:10], []).append(item_id)

    for day, day_ids in by_date.items():
        path = data_dir / "days" / f"{day}.json"
        if not path.exists():
            unknown += day_ids
            continue
        doc = common.load_json(path)
        keep = [i for i in doc["items"] if i["id"] not in day_ids]
        removed = [i for i in doc["items"] if i["id"] in day_ids]
        unknown += [i for i in day_ids if i not in {r["id"] for r in removed}]
        if not removed:
            continue
        dropped_items += removed
        if keep:
            doc["items"] = keep
            if doc["headline"]["item_id"] not in {i["id"] for i in keep}:
                doc["headline"] = {"item_id": keep[0]["id"], "text": keep[0]["title"]}
            write_json(path, doc)
        else:
            path.unlink()
            run_path = data_dir / "runs" / f"{day}.json"
            if run_path.exists():
                run = common.load_json(run_path)
                run["status"] = "empty"
                run["note"] = (run.get("note", "") + " 사람이 모든 항목을 제외함").strip()
                write_json(run_path, run)

    if dropped_items:
        write_decision(data_dir, "drop", pr, [rejected_entry(i) for i in dropped_items], now)
    return [i["id"] for i in dropped_items], unknown


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=common.ROOT, capture_output=True, text=True, check=True).stdout


def record_close(data_dir: Path, ref: str, pr: int, now: datetime) -> list[str]:
    """닫힌 PR 브랜치(ref)에 있던 항목을 전부 거절로 기록한다. 기록한 id 목록."""
    entries: dict[str, dict] = {}
    for path in git("diff", "--name-only", f"HEAD...{ref}").splitlines():
        if not path.endswith(".json"):
            continue
        if path.startswith("data/days/"):
            doc = json.loads(git("show", f"{ref}:{path}"))
            for item in doc["items"]:
                entries[item["id"]] = rejected_entry(item)
        elif path.startswith("data/decisions/"):  # PR 안에서 /drop한 것도 함께 남긴다
            for e in json.loads(git("show", f"{ref}:{path}"))["items"]:
                entries.setdefault(e["item_id"], e)
    if entries:
        write_decision(data_dir, "pr-closed", pr, list(entries.values()), now)
    return list(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("drop")
    p.add_argument("pr", type=int)
    p.add_argument("comment")
    p.add_argument("--data-dir", type=Path, default=common.DATA_DIR, help="PR 브랜치의 data/")
    p = sub.add_parser("record-close")
    p.add_argument("pr", type=int)
    p.add_argument("ref")
    args = parser.parse_args()
    now = common.now_kst()

    if args.cmd == "drop":
        ids = parse_drop(args.comment)
        if ids is None:
            sys.exit("/drop 코멘트가 아니다")
        if not ids:
            print("제외할 항목 ID가 없습니다. 예: `/drop 2026-11-03-02`")
            sys.exit(1)
        dropped, unknown = drop(args.data_dir, ids, args.pr, now)
        lines = []
        if dropped:
            lines.append("제외: " + ", ".join(f"`{i}`" for i in dropped))
        if unknown:
            lines.append("찾지 못함: " + ", ".join(f"`{i}`" for i in unknown))
        print("\n".join(lines))
        sys.exit(0 if dropped else 1)
    else:
        recorded = record_close(common.DATA_DIR, args.ref, args.pr, now)
        print(f"거절로 기록: {len(recorded)}개" + (f" ({', '.join(recorded)})" if recorded else ""))


if __name__ == "__main__":
    main()
