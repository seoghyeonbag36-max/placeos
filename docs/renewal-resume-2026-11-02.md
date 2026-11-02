# PPPP 리뉴얼 재개·검증 기록 (2026-11-02)

## 중단 지점과 범위

사용자가 17:53 Claude Code 사용량 소진으로 중단된 작업을 이어 마무리하도록 요청했다.
작업 트리·수정 파일·기존 HTML을 확인하고, 사용자에게 **`.claude/worktrees/renewal`의 PPPP 리뉴얼이 맞으며 Posting·Program까지 전체 마무리**임을 확인받았다.
Claude Code 대화 원문에서 정확한 마지막 호출을 확인한 것은 아니다. 확인 가능한 산출물은 Platform 검증 HTML과 Page 3D 구현·미통과 테스트였다.
루트의 `chore/jeonju-expansion`은 전날 Gold 완료 기록이 있는 별개 작업이므로 수정하지 않았다.

작업 위치는 `.claude/worktrees/renewal`, 재개 브랜치는 `fix/renewal-resume-20261102`다.
기존 미커밋 변경을 보존한 채 수정했으며 커밋·푸시·머지·배포는 하지 않았다.

대상은 기존 리뉴얼의 frontend 트윈·Posting·Program·App·API 클라이언트·출처 안내와 관련 backend Posting·Program 자리 컨텍스트,
추가 인테리어 API·설정·테스트 및 검증 스크립트다.
기존 PPPP 화면·레일·진입로·랜딩과 `ppppScreens.test.tsx`는 보존했다.
앵커 해석·집계 제외·공실 출처 규칙은 바꾸지 않았다.

## 마무리한 동작

- **Page**: 3D 장면 지연 로드, 층 선택·층 분리·공실 강조·2D 실패 대체와 기존 근거 표기를 유지했다.
  React ref 갱신을 effect로 옮기고 건물 전환 시 응답·선택 수명이 새로 시작하도록 정리했다.
  지도 스텁의 존재하지 않는 API와 중복 DOM 선택으로 실패하던 테스트를 수정했다. 기대하는 동작은 유지했다.
- **Posting**: Page가 보낸 `vfu-` 층을 그 건물의 트윈과 대조하여 선택한다. 층 면적·임대 근거가 없으면 다른 자리로 조용히 바꾸지 않는다.
  확인한 내부면적을 입력하면 기존 `area_py_override` 계약으로 계산하며 서버의 사용자 입력 출처를 표시한다.
  BEP와 Program이 동일한 면적·임대료를 쓰도록 층·면적 변경 계산에는 `resolved_inputs`를 반환한다.
  기존 건물 단위 계산의 응답 키 집합은 보존한다. 수정한 조건의 재계산이 끝나기 전에는 Program으로 넘기지 않는다.
- **Program**: 기존 CampaignStudio를 유지하고 검증 브리프 생성·지표·온라인/오프라인 초안 편집·결과 저장 화면을 함께 연결했다.
  층 매물의 자리 컨텍스트는 건물 평균 대신 그 층의 대장 면적·층 라벨·현장 미확인 한계를 사용한다.
  인테리어 화면은 Posting의 세 전략 결과, 분위기 입력, 도면·사진, 참고 링크, 생성 지시문·비용 결과 저장 및 이미지 내려받기를 제공한다.
  업종·상권 적합성 점수나 시공 가능 여부는 만들지 않는다.

## 입력과 출처

기존 Gold 건물 외곽선·대장 층별개요·층 매물·R-ONE 임대·상가정보 점포 대조를 사용한다.
공실 판정은 스냅샷이며 현장 확인이나 실시간 공실이 아니다. 내부 실측 평면도·호실 위치는 없다.
Page의 도면 겹치기는 브라우저 안에서만 읽으며 업로드만으로 면적을 판독하지 않는다.

내부면적·BEP 운영 조건·인테리어 분위기·구조 제약·도면·사진·참고 링크는 사용자 입력이다.
사용자 면적의 기존 `user_input` 출처를 유지하고 권리금 미입력의 기존 `absent`(0 전제) 계약을 유지한다.
테스트의 상호·금액·이미지는 테스트용 합성값이며 실제 수요·공실·시공 성과의 증거가 아니다.
브라우저 검사에 넣은 **40평과 BEP 운영 조건은 검증용 입력**이다.

## 검증

다음 검사를 실행했다. 최종 결과 파일은 `reports/renewal/result.json`과 `reports/pppp_screens/result.json`이다.

| 검사 | 결과 |
| --- | --- |
| frontend `npm run build` | 타입 검사·프로덕션 번들 성공. three 장면은 별도 지연 로드 청크 |
| frontend `npm run lint` | 오류·경고 없음 |
| frontend 전체 Vitest | 56파일·471건 통과 |
| backend 전체 pytest | 800 통과·7 건너뜀 |
| 마지막 Posting 응답 확장 후 backend 관련 재검사 | `test_renewal_api.py`, `test_interior.py`, `test_posting_marketing.py`, `test_program_site.py` 109건 통과 |
| Gold `data/tests/test_renewal_gold.py` | 325건 통과 |
| PPPP 실화면 보존 | 22 통과·0 실패·종료코드 0 |
| 신규 실제 브라우저 흐름 | 3D 렌더·선택 층 보존·사용자 면적 출처·서버 임대 입력·BEP·Program 인계·동의 전 생성 차단·모바일 넘침 검사 통과 |
| Gold 배포 제외 검사 | 신규 런타임 236경로에 `git check-ignore --no-index -z --stdin`: 종료코드 1·무시 경로 0 |

전체 backend 검사는 마지막 `resolved_inputs` 보완 전 실행이며, 보완 후에는 위 관련 109건을 다시 통과시켰다.
목킹한 LLM·이미지 공급자 테스트는 실제 외부 생성 성공의 증거가 아니다.

재현 명령:

```powershell
# 이 리뉴얼 작업 트리에서
cd apps/backend
py -3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8002
# 별도 터미널, 이 작업 트리의 frontend에서
cd apps/frontend
$env:PLACEOS_API_TARGET='http://127.0.0.1:8002'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
# 별도 터미널, 작업 트리 루트에서
py -3.11 scripts/renewal_flow_check.py
py -3.11 scripts/pppp_screens_check.py --base http://127.0.0.1:5173 --screens
```

## 외부 설정과 확인하지 못한 것

- 이 작업 트리에는 frontend 지도 키가 없다. 브라우저 보고서의 `네이버 지도 SDK`는 `false`다.
  네이버 바탕지도·지도 인증 자체의 성공을 주장하지 않는다. 3D 장면은 실제 외곽선으로 별도 렌더링되어 확인했다.
- 교통·주소·벤치마킹 실호출은 기존 API 키 설정에 달려 있다. 분·거리·후보를 지어내지 않았다.
- 인테리어 생성은 기본 비활성화다. 서버에 `INTERIOR_IMAGES_ENABLED=true`, `OPENAI_API_KEY`,
  모델 사용 권한이 있는 `INTERIOR_IMAGE_MODEL`을 설정해야 한다. 예시는 `.env.example`에 있다.
  로그인·전송 동의·버튼 클릭 때만 실제 유료 호출하며 자동 재시도하지 않는다.
  이번 검증에서는 유료 이미지 생성을 호출하지 않았다.
- AI 이미지는 **참고 이미지**다. 치수·피난 동선·법규·시공 견적·상권 수요를 검증하지 않는다.
  사진·도면은 선택했을 때만 전송하며 서비스 서버에 자동 저장하지 않는다.
  참고 링크는 메모로만 전달하며 원문을 자동으로 수집하지 않는다.
  실패·미설정 때는 가짜 이미지 대신 실패 안내와 지시문 저장을 제공한다.

이미지 연동 계약은 [OpenAI 공식 Image API 문서](https://developers.openai.com/api/docs/guides/image-generation)를 확인했다.
텍스트 입력은 generations, 사용자가 제공한 도면·사진이 있으면 edits로 전달한다.
처리방침과 화면의 전송 안내도 실제 전송 동작에 맞춰 추가했다.
