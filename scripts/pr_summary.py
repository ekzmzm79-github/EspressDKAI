"""브리핑 PR 본문(검토 요약) 생성.

AI가 자유롭게 쓰지 않고 데이터에서 만든다. 사람은 휴대폰에서 이것만 보고
Merge·/drop·닫기를 정한다.

    python scripts/pr_summary.py 2026-10-30 2026-10-31
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import build
import common


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def title(dates: list[str]) -> str:
    if len(dates) == 1:
        return f"브리핑 {dates[0]}"
    return f"브리핑 {dates[0]} ~ {dates[-1]} ({len(dates)}일)"


def summarize(dates: list[str], data_dir: Path = common.DATA_DIR, today: date | None = None) -> str:
    """dates: 이 PR에서 새로 들어온 날짜들 (오름차순)."""
    sections = common.sections()
    payload = build.collect(data_dir, today or common.today_kst())
    excluded = {e["item_id"]: e for e in payload["excluded"]}

    lines = [
        f"# {title(dates)}",
        "",
        "- **전체 승인:** Merge → 검사 후 자동 배포",
        "- **일부 제외:** 코멘트로 `/drop <항목 ID>` (여러 개는 공백으로 구분)",
        "- **전체 거절:** Merge 없이 PR 닫기",
    ]

    for d in dates:
        day_path = data_dir / "days" / f"{d}.json"
        run_path = data_dir / "runs" / f"{d}.json"
        run = common.load_json(run_path) if run_path.exists() else None
        lines += ["", f"## {d}"]

        if run is None:
            lines.append("실행 기록 없음")
        else:
            secs = run["sections"]
            lines.append(
                f"실행 {run['status']} · 수집 {sum(s['candidates'] for s in secs.values())}"
                f" · 통과 {sum(s['passed'] for s in secs.values())}"
                f" · 검증 수정 {sum(s['verification_edits'] for s in secs.values())}"
            )
            if run.get("note"):
                lines.append(f"> {run['note']}")

        if day_path.exists():
            day = common.load_json(day_path)
            lines += ["", f"**오늘의 한 줄** ({day['headline']['item_id']}): {day['headline']['text']}"]
            for section_id, conf in sections.items():
                items = [i for i in day["items"] if i["section"] == section_id]
                if not items:
                    continue
                lines += ["", f"**{conf['title']}** {len(items)}개", "", "| ID | 제목 | 원문 | 검증 |", "|---|---|---|---|"]
                for i in items:
                    src = i["sources"][0]
                    check = "통과" if i["verification"]["status"] == "pass" else f"수정 {i['verification']['edits']}"
                    if i["id"] in excluded:
                        check += " · ⚠️ 중복으로 제외 예정"
                    extra = f" (마감 {i['hiring']['deadline']})" if "hiring" in i else ""
                    lines.append(f"| `{i['id']}` | {_cell(i['title'])}{extra} | [{src['published']}]({src['url']}) | {check} |")
                over = run and run["sections"].get(section_id, {}).get("over_max_reason")
                if over:
                    lines.append(f"\n권장 최대치 초과 이유: {over}")
        else:
            lines.append("공개할 항목 없음")

        skipped = [(sid, s) for sid, sec in (run["sections"].items() if run else []) for s in sec["skipped"]]
        if skipped:
            lines += ["", "<details><summary>스킵 " + str(len(skipped)) + "개</summary>", ""]
            lines += [f"- {sections[sid]['title']}: {_cell(s['event_key'])} — {_cell(s['reason'])}" for sid, s in skipped]
            lines += ["", "</details>"]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dates", nargs="+")
    parser.add_argument("--data-dir", type=Path, default=common.DATA_DIR)
    parser.add_argument("--today", type=date.fromisoformat)
    args = parser.parse_args()
    print(summarize(sorted(args.dates), args.data_dir, args.today), end="")


if __name__ == "__main__":
    main()
