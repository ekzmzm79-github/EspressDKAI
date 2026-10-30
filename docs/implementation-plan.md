# EspressDKAI 구현 계획서

- 작성: 2026-10-28 · 개정: 2026-10-30 · 상태: **확정 (v1)**
- 바탕: 「EspressDKAI 기획서: AI 동향 카드뉴스 브리핑」(2026-10-28)
- 이 문서는 기획서의 "무엇을"을 "어떻게 만들지"로 옮긴 것이다. 기획서와 다른 부분은 0장에 모아 두었다.

---

## 0. 기획서 대비 변경 사항

기획서 검토 과정에서 합의한 변경이다. 이 문서의 나머지 부분은 모두 이 변경을 반영한다.

| # | 기획서 | 변경 | 이유 |
|---|---|---|---|
| C1 | 날짜 기준 명시 없음 | 모든 날짜는 **KST**(`Asia/Seoul`) 기준 | 클라우드 컨테이너 시계는 UTC. 7:30 KST는 UTC 전날 22:30이라 날짜가 하루 밀린다 |
| C2 | 매일 새 PR | **이어 쓰기 PR 하나** (`claude/briefing`). 열린 PR이 있으면 같은 브랜치에 그날 커밋을 추가 | Merge를 미루면 다음 날 실행이 어제 데이터를 못 보고 중복을 만들며, PR끼리 충돌한다 |
| C3 | AI가 `data/index.json` 수정 | AI는 **그날 파일만 새로 만든다**(추가 전용). 색인은 스크립트가 파일들에서 매번 파생 | 공유 파일을 여러 PR이 고치면 충돌한다. 추가 전용이면 충돌이 원리적으로 없다 |
| C4 | 형식 검사는 Merge 후 | **PR 단계에서도 검사**(상태 체크). Merge 후에는 배포 직전 한 번 더 | 휴대폰에서 ✅/❌를 보고 Merge한다. 깨진 데이터가 main에 들어가지 않는다 |
| C5 | 링크 응답 실패 시 배포 중단 | 링크 검사는 **경고만**. 배포를 막는 건 스키마·날짜·인용 길이 등 기계 판정 항목 | 언론·기업 사이트 다수가 Actions IP에 403을 준다 |
| C6 | 인용 15단어 미만 | 인용 **40자 이하**(따옴표 안 글자 수) | 한국어는 단어 수 판정이 애매하다 |
| C7 | 매일 7:30 | 매일 **7:23 KST** (`CRON_TZ=Asia/Seoul 23 7 * * *`) | 정각·30분은 예약이 몰려 지연된다 |
| C8 | 사람이 매번 Merge | M2 관문 통과 후 **정오 자동 Merge** 스위치 추가(기본 꺼짐) | 거부할 시간을 남긴 자동화. Claude가 아니라 GitHub Actions가 수행 |
| C9 | 명시 없음 | Actions가 만든 변경이 다른 워크플로를 깨우도록 **GitHub App 토큰** 사용 | `GITHUB_TOKEN`으로 만든 커밋·Merge는 다른 워크플로를 트리거하지 않는다 |
| C10 | 명시 없음 | 클라우드 세션의 GitHub 조작은 **REST API**(`gh api`)만 쓴다 | 클라우드 세션에서는 GraphQL이 막혀 `gh pr list`, `gh pr create`가 동작하지 않는다 |
| C11 | 명시 없음 | 최근 7일 안에 공개된 원문 URL과 같은 항목은 **화면 생성 시 자동 제외**. 데이터 파일은 고치지 않는다 | 같은 기사를 다시 볼 필요는 없고, 데이터를 몰래 고치지 않으려고 |

---

## 1. 전체 구조

```
[07:23 KST] Claude 예약 작업 (클라우드 세션, 구독 사용량)
   ├─ claude/briefing 브랜치 준비 (열린 PR 있으면 이어 쓰기)
   ├─ 색인 확인: python scripts/index.py  → 최근 7일 처리 기록 (main + 열린 PR)
   ├─ 수집 → 취합·초안 → 검증 서브에이전트(원문 대조)
   ├─ data/days/<날짜>.json, data/runs/<날짜>.json 작성
   ├─ python scripts/validate.py  (로컬, 네트워크 없이)
   └─ 커밋·푸시, PR 생성 또는 갱신 (PR 본문은 스크립트가 생성)

[PR 이벤트] pr-check.yml : 형식 검사 → 상태 체크 ✅/❌, 링크 검사 경고
[PR 코멘트] drop.yml     : /drop <id> (저장소 주인만) → 항목 제거 커밋
[PR 닫힘]   record-close : Merge 없이 닫힘 → data/decisions/에 rejected 기록
[main push] deploy.yml   : 검사 → build.py → GitHub Pages
[12:00 KST] auto-merge.yml (M2 이후, 스위치) : 검사 통과 + hold 라벨 없음 → Merge → 배포
```

Claude가 하는 일은 **아침 수집 하나뿐**이다. 검사·Merge·배포·거절 기록은 전부 GitHub Actions 스크립트가 하므로 구독 사용량을 쓰지 않는다.

---

## 2. 저장소 구조

```
CLAUDE.md                      # 작업 종류 라우터 (짧게)
docs/
  runbook.md                   # 예약 실행이 따르는 작업 규칙 (AI용)
  development.md               # 개발 작업 규칙, 검토 요청 규칙
  implementation-plan.md       # 이 문서
  reviews/                     # 외부 모델 검토 요청서와 답변
config/
  sections/llm.yaml            # 출처, 수집 기간, 권장 최대치, 공개 여부
  sections/hiring.yaml
  rules.yaml                   # 공통 선정·인용 길이 기준
schema/
  day.schema.json
  run.schema.json
  decision.schema.json
data/                          # AI가 쓰는 곳은 days/, runs/ 뿐
  days/YYYY-MM-DD.json         # 하루치 브리핑 (추가 전용)
  runs/YYYY-MM-DD.json         # 실행 지표 (추가 전용)
  decisions/YYYY-MM-DD-<n>.json# 사람 결정(rejected) 기록 — Actions만 씀
scripts/                       # Python 3.12, 표준 라이브러리 + jsonschema, jinja2, pyyaml
  prepare_branch.py            # 예약 실행 시작 시 이어 쓸 브랜치 결정
  github_pr.py                 # PR 조회·생성·갱신 (REST)
  index.py                     # 최근 7일 색인을 파생해 출력
  validate.py
  pr_summary.py                # PR 본문 생성
  drop.py                      # /drop 처리
  build.py                     # site/ 템플릿 + data → _site/
site/                          # 카드뉴스 템플릿 (HTML/CSS/바닐라 JS)
tests/                         # 스크립트 단위 테스트, 화면 스크린샷 테스트
.github/workflows/
  pr-check.yml  deploy.yml  drop.yml  record-close.yml
  auto-merge-log.yml  auto-merge.yml
```

**색인은 파일로 저장하지 않는다(C3).** `scripts/index.py`가 `data/days/`(공개된 것), `data/runs/`(스킵 기록), `data/decisions/`(거절 기록)를 읽어 최근 7일 처리 기록을 매번 만들어 낸다. 기획서의 `index.json`이 하던 역할은 그대로이고 저장 방식만 다르다. 7일이 지난 기록은 읽을 때 무시하므로 `prune_index.py`는 필요 없다.

---

## 3. 데이터 형식

기획서의 형식을 거의 그대로 쓰고, 아래만 추가·변경한다.

**`data/days/YYYY-MM-DD.json`**
- 기획서 형식 + 항목별 `deadline`(채용·해커톤 필수, `YYYY-MM-DD`), `published_at`(원문 발행일)
- `id`는 `YYYY-MM-DD-NN`. 날짜 부분은 파일 날짜와 같아야 한다.

**`data/runs/YYYY-MM-DD.json`**
- 섹션별 수집 후보 수, 통과 수, 제외 목록(`event_key`, `url`, 이유), 검증 수정 수, 건너뛴 이유
- 스킵한 항목도 여기에 남아서 다음 날 중복 판단에 쓰인다.

**`data/decisions/YYYY-MM-DD-<n>.json`** (Actions만 작성)
- `{ "item_id", "status": "rejected", "via": "drop" | "pr-closed", "at" }`

**같은 날 다시 실행하면** 그날 파일을 덮어쓴다(수동 Run now로 다시 돌리는 경우).

---

## 4. 이어 쓰기 PR 흐름 (C2)

예약 실행이 시작할 때 브랜치를 이렇게 정한다. 이 판단은 AI가 아니라 `scripts/prepare_branch.py`가 한다.

1. `claude/briefing`의 **열린 PR이 있으면** 그 브랜치를 받아 이어 쓴다.
2. **없으면** main에서 `claude/briefing`을 새로 만든다(이전 브랜치가 남아 있으면 덮어쓴다. Merge·닫힘 후 브랜치 자동 삭제 설정을 켜 둔다).
3. 오늘 데이터를 커밋하고, `pr_summary.py`로 PR 본문을 **날짜별 섹션**으로 다시 만든다.
4. PR 조회·생성·본문 갱신은 모두 REST API로 한다(C10). `scripts/github_pr.py`가 감싼다.

**두 섹션 모두 비는 날:** 열린 PR이 있으면 `runs/` 파일만 거기에 추가한다. 없으면 `claude/log-<날짜>` PR을 따로 올리고, `data/runs/`만 바뀐 PR은 `auto-merge-log.yml`이 자동 Merge한다(배포 없음).

**늦게 승인하거나 순서가 바뀌어도 안전한 이유**

| 상황 | 처리 |
|---|---|
| 토·일이 한 PR에 쌓인 뒤 일요일에 Merge | 둘 다 공개. 화면은 날짜 기준이라 토요일 것은 "1일 전"으로 접힘 |
| 마감 지난 채용 항목을 늦게 승인 | 화면 스크립트가 마감일과 오늘을 비교해 표시하지 않음 |
| 같은 원문 URL이 7일 안에 이미 공개됨 | `build.py`가 화면에서 건너뜀 (C11) |
| 다른 기사, 같은 사건 | 기계 판정 불가. 다음 날 AI가 열린 PR 데이터까지 포함한 색인을 보고 판단 |

---

## 5. 검사 (`scripts/validate.py`)

| 구분 | 항목 | 실패 시 |
|---|---|---|
| 차단 | JSON 스키마 | ❌ |
| 차단 | 파일 날짜·`id` 일치, `id` 중복, 날짜가 KST 오늘 이후가 아님 | ❌ |
| 차단 | LLM 섹션 원문 발행일이 수집 기간 안 | ❌ |
| 차단 | 채용 항목 `deadline` 필수 | ❌ |
| 차단 | 인용 40자 이하, 항목당 1회 | ❌ |
| 차단 | 카드 2~3줄, 줄당 길이 상한 | ❌ |
| 차단 | 바뀐 파일이 `data/days/`, `data/runs/` 밖 (Claude PR일 때) | ❌ |
| 경고 | 원문 링크 응답 (Actions에서만, 재시도 1회) | PR 코멘트로 경고만 |
| 제외 | 최근 7일 공개 항목과 원문 URL 중복 (C11) | `build.py`가 건너뛰고, PR 요약에 "중복으로 제외" 표시 |

"원문 문장을 옮기지 않는다"는 기계로 완벽히 판정할 수 없다. 검증 서브에이전트의 원문 대조와 사람 승인에 맡기고, 원문과 요약의 긴 공통 문자열 검사는 넣지 않는다(실제 문제가 생기면 그때 추가).

---

## 6. GitHub Actions와 권한

| 워크플로 | 트리거 | 하는 일 |
|---|---|---|
| `pr-check.yml` | `pull_request` | `validate.py`, 링크 경고 코멘트 |
| `deploy.yml` | main push, `workflow_call` | 검사 → `build.py` → Pages 배포 |
| `drop.yml` | `issue_comment` | 작성자가 저장소 주인일 때만 `/drop <id>` 처리 후 커밋 |
| `record-close.yml` | `pull_request: closed` (Merge 아님) | 남은 항목 전부 `data/decisions/`에 rejected로 main에 기록 |
| `auto-merge-log.yml` | `pull_request` | `data/runs/`만 바뀐 PR 자동 Merge |
| `auto-merge.yml` | `schedule` 03:00 UTC = 12:00 KST | 저장소 변수 `AUTO_MERGE=on`이고 ✅이고 `hold` 라벨이 없으면 Merge 후 `deploy.yml` 호출 |

**토큰(C9):** 개인용 GitHub App을 하나 만들어 그 토큰으로 커밋·Merge한다. 그래야 `drop.yml`의 커밋이 `pr-check.yml`을 다시 돌리고, 자동 Merge가 배포를 깨운다. 앱 키는 저장소 Secrets에만 둔다. (대안: 세분화된 PAT. 만료 관리가 번거로워 앱을 권장)

**`/drop` 보안:** `issue_comment` 워크플로는 기본 브랜치 코드로 실행되므로, PR 브랜치의 스크립트를 실행하지 않는다. 코멘트 작성자 확인은 `github.event.comment.user.login == github.repository_owner`로 한다.

**main 보호:** 직접 푸시 금지, `pr-check` 통과 필수. GitHub App만 우회 허용(`record-close.yml`이 main에 기록해야 하므로).

---

## 7. 웹 화면

- **정적 페이지 한 장**, 프레임워크 없이 HTML·CSS·바닐라 JS. `build.py`가 Jinja2 템플릿에 데이터를 넣는다.
- 데이터는 최근 7일 치를 `briefing.json`으로 함께 배포하고, **표시·접힘은 브라우저가 계산**한다(기획서 그대로).
- 휴대폰 세로(390px) 기준, 넓은 화면은 여러 열. 라이트·다크 모드. 한국어 단일.
- **디자인은 마지막에 한다.** M0~M2는 구조만 갖춘 기본 템플릿으로 운영하고, 디자인 단계(M3)에서 Claude의 Design 캔버스로 시안 2~3개 → 선택 → `site/`에 반영한다.
- **화면 테스트:** Playwright로 샘플 데이터 화면을 390px·1280px, 라이트·다크로 스크린샷 찍는다. "N일 전", "마감 임박" 같은 날짜 표시는 시계를 고정해 테스트한다.

---

## 8. AI 지침 구성

- **`CLAUDE.md`**: 작업 종류 라우터만 둔다. 예약 실행은 매일 이 파일을 읽으므로 짧게 유지한다.
- **`docs/runbook.md`**: 예약 실행 절차. 기획서의 선정 규칙, 중복 판단(의미 비교), 저작권 규칙, 검증 서브에이전트 지시, 실패 시 행동.
- **`docs/development.md`**: 이 프로젝트의 개발 규칙과 검토 지점. 일반적인 검토 요청 규칙은 클라우드 환경의 전역 지침에 있다.
- **예약 작업 프롬프트**는 한 줄로 둔다: "`docs/runbook.md`에 따라 오늘(KST) 브리핑을 실행하라." 규칙은 저장소에만 둬서 버전 관리한다.

---

## 9. 단계별 진행

| 단계 | 산출물 | 관문 |
|---|---|---|
| **M0 뼈대** | 아래 PR 5개 | 샘플 PR에서 ✅/❌, `/drop`, 닫힘 기록, 배포가 동작 |
| **M1 수동 실행** | `docs/runbook.md`, 클라우드 세션에서 수동 실행 반복 | 3회 연속 PR까지 성공. 웹 검색 도구 동작, 공모전 출처 확정 |
| **M2 자동화** | 7:23 예약 작업 연결 | 1주 연속 무인 실행, 거절률 확인 → 자동 Merge 켤지 결정 |
| **M3 디자인** | Design 캔버스 시안 → `site/` 반영 | Gemini UX·디자인 검토 반영 |
| **M4 알리기** | 지표 화면, README | — |
| **M5 선택** | Codex 교차 검토 실험 | — |

### M0 세부 (PR 단위)

| PR | 범위 | 완료 기준 |
|---|---|---|
| **M0-1 기반** | `requirements.txt`, `config/`, `schema/`, `scripts/common.py`(KST 날짜·데이터 로딩), 테스트용 샘플 데이터(`tests/fixtures/`), pytest, 테스트 워크플로 | 샘플 데이터가 스키마를 통과하고 CI에서 pytest가 돈다 |
| **M0-2 색인·검사** | `index.py`, `validate.py` | 정상·위반 샘플마다 기대한 결과. 색인이 main과 브랜치 데이터를 합쳐 7일 범위를 낸다 |
| **M0-3 화면 생성·배포** | `build.py`(URL 중복 제외 포함), 기본 템플릿, `deploy.yml`, Pages 설정 | 샘플 데이터로 Pages에 페이지가 뜬다 |
| **M0-4 PR 흐름** | `github_pr.py`, `prepare_branch.py`, `pr_summary.py`, `pr-check.yml` | 클라우드 세션에서 샘플 데이터로 이어 쓰기 PR을 만들고, 두 번째 실행이 같은 PR에 붙는다 |
| **M0-5 사람 결정** | GitHub App 토큰, `drop.py`·`drop.yml`, `record-close.yml`, `auto-merge-log.yml`, `auto-merge.yml`(꺼진 상태), main 보호·브랜치 자동 삭제 설정 | `/drop`, PR 닫힘 기록, 로그 PR 자동 Merge가 실제로 동작 |

샘플 데이터는 `tests/fixtures/`에만 둔다. `data/`에 넣으면 실제로 공개되기 때문이다.

---

## 10. 외부 모델 검토

- 계획서 검토는 생략한다.
- M3 디자인 단계에서 화면 스크린샷과 질문을 담은 요청서를 만들어 **Gemini에 UX·디자인 검토**를 받는다.
- 그 밖에도 진행 중 필요하다고 판단되면 `docs/reviews/`에 요청서를 만든다(양식: `docs/reviews/README.md`).

---

## 11. 결정 사항

| # | 질문 | 결정 |
|---|---|---|
| Q1 | Actions 토큰: GitHub App vs PAT | **GitHub App** (만료 관리 없음, 이 저장소에만 권한) |
| Q2 | 최근 7일 공개 항목과 URL이 같은 항목 | **자동 제외** (C11). 초반 며칠 검수 후 자동 운영할 계획이라 같은 기사를 다시 볼 필요 없음 |
| Q3 | 원문 문장 복사 검사 | **넣지 않음.** 요약 수준에서 큰 문제는 없을 것으로 봄 |
| Q4 | 사이트 언어 | **한국어 단일** |
