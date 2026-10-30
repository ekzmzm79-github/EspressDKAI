# 개발 작업 규칙

## 기본

- 날짜는 항상 KST: `TZ=Asia/Seoul date +%F`
- 작업은 `claude/` 접두사 브랜치에서 하고 PR로 올린다. main에 직접 푸시하지 않는다.
- 클라우드 세션에서 GitHub 조작은 REST API(`gh api repos/...`)로 한다. `gh pr list`·`gh pr create` 같은 GraphQL 명령은 막혀 있다.
- 클라우드 세션에서는 강제 푸시, 원격 브랜치 삭제, 저장소 설정 변경이 막혀 있다. 이런 일은 Actions나 사용자에게 맡긴다.
- 비밀값은 저장소에 두지 않는다.
- 테스트용 샘플 데이터는 `tests/fixtures/`에만 둔다. `data/`에 들어간 것은 실제로 공개된다.
- 커밋 전에 `python3 -m pytest -q`를 돌린다.
- PR은 항상 main을 대상으로 올린다. 다른 PR 브랜치 위에 쌓지 않는다.

## 외부 모델 검토

검토 요청서는 `docs/reviews/`에 둔다. 진행 방식과 양식은 `docs/reviews/README.md`.

이 프로젝트에서 정한 검토 지점 (`docs/implementation-plan.md` 10장):

- M3 디자인 단계: 화면 스크린샷과 질문을 담아 Gemini에 UX·디자인 검토

그 밖에도 필요하다고 판단되면 요청서를 만들고, PR 설명에 링크를 남긴다.
