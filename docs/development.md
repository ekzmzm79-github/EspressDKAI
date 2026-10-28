# 개발 작업 규칙

## 기본

- 날짜는 항상 KST: `TZ=Asia/Seoul date +%F`
- 작업은 `claude/` 접두사 브랜치에서 하고 PR로 올린다. main에 직접 푸시하지 않는다.
- 비밀값은 저장소에 두지 않는다.

## 외부 모델 검토

검토 요청서는 `docs/reviews/`에 둔다. 진행 방식과 양식은 `docs/reviews/README.md`.

이 프로젝트에서 미리 정한 검토 지점 (`docs/implementation-plan.md` 10장):

1. 구현 계획서
2. 스키마와 `validate.py` 규칙
3. 워크플로 보안 (`/drop`, 토큰, main 보호)
4. 디자인 시안
5. `docs/runbook.md` (예약 실행 지침)
6. M1 결과와 자동화 전환

PR 설명에 해당 요청서 링크를 남긴다.
