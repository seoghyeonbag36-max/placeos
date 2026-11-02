# 외부 API 키 연결·실호출 검증 (2026-11-02)

## 결과

| 대상 | 실호출 결과 |
| --- | --- |
| 네이버 지도 | 인증 HTTP 200 · SDK 로드 · 타일 이미지 41개 · 건물 목록 841행 · PPPP 네 트랙 표시 · 브라우저 오류 없음 |
| 카카오 주소 검색 | HTTP 200 · `status=ok` · 입력 주소의 실제 좌표 반환 |
| 카카오모빌리티 차량 소요 | HTTP 200 · `status=ok` · 제공자 소요시간·거리 반환 |
| ODsay 대중교통 | HTTP 200 · `status=ok` · 제공자 소요시간·거리·요금 반환 |
| 벤치마킹 점포 | HTTP 200 · 가로수길 카페 후보 45곳 반환 |
| 인근 교통 접근성 | HTTP 200 · 기존 지하철·버스·주차장 응답 확인. TMAP 키는 없어 도보시간 실호출은 미검증 |
| OpenAI 새 키 인증 | `GET /v1/models` HTTP 200 · `gpt-image-2.5-flare` 포함 이미지 모델 목록 확인 |
| 이미지 실제 생성 | 앱에서 공급자까지 요청 도달. 공급자 HTTP 429 · `credit_balance_exhausted` · `insufficient_quota` |
| 참고 이미지 편집 | 생성된 첫 이미지를 참고 이미지로 쓸 예정이었으나, 생성 실패로 실행하지 않음 |

키 인증 성공과 이미지 생성 성공은 별개다. 공급자가 잔여 API 크레딧이 없다고 반환했으므로 추가 호출을 중단했다.
이미지는 생성되지 않았으며 성공한 것처럼 대체 이미지를 넣지 않았다. 크레딧 충전·결제 설정 변경은 수행하지 않았다.

## 설정과 수정

- 루트에 있던 지도·카카오·ODsay 키를 리뉴얼 작업 트리의 무시되는 `.env`에 연결했다.
  키 원문은 코드·문서·보고서·콘솔에 출력하지 않았다.
- 사용자가 처음 입력한 OpenAI 형식 키는 `LLM_API_KEY` 아래 있었다. 이를 `OPENAI_API_KEY`로 분리하고,
  Anthropic용 `LLM_API_KEY`에 잘못 들어 있던 같은 값을 제거했다. 이전 키는 공급자 인증에서 401로 거부됐고,
  사용자가 새 키로 교체한 뒤 인증 200을 확인했다. Anthropic용 텍스트 LLM 키는 별도 설정이 필요하다.
- 리뉴얼 `.env`의 이미지 기능은 새 키 인증 통과 후 활성화했다. 기본 모델은 계정 모델 목록에서 확인했다.
  이 설정은 로컬 작업 트리용이며 프로덕션 배포·환경변수 변경은 하지 않았다.
- 인증 이미지 클라이언트가 `/auth/ai/interior-preview`로 잘못 호출하던 오류를 실화면에서 발견했다.
  기존 인증 요청 도우미 `accountRequest`로 바꿔 정확히 `/api/v1/ai/interior-preview`로 보내도록 수정했고,
  테스트도 전체 경로를 검증하도록 강화했다.
- 검증 계정은 별도의 로컬 SQLite DB에만 생성했고 검사 종료 후 삭제했다. 운영 DB와 계정은 사용하지 않았다.

## 근거 산출물·재현

`reports/renewal/`에 다음 근거가 있다. 키·JWT 원문은 포함하지 않는다.

- `naver-map-live.json`, `live-naver-map-{desktop,mobile}.png`
- `external-api-live.json`
- `openai-access.json`
- `openai-image-provider-status.json`
- `interior-image-live.json` — 앱의 502와 공급자 직접 진단의 429를 구분하여 읽는다.

```powershell
# 리뉴얼 작업 트리 루트, 로컬 백엔드 8002·프론트 5173을 먼저 실행
py -3.11 scripts/renewal_map_live_check.py
# 크레딧 해결 후에만: 실제 생성 1회 + 참고 이미지 편집 1회
py -3.11 scripts/renewal_image_live_check.py --run
```

지도 키에 등록된 `http://localhost:5173`을 사용한다. 같은 포트의 다른 IPv6 개발 서버와 혼동하지 않도록
브라우저 검사에서 localhost를 리뉴얼 서버의 127.0.0.1로 연결한다.

최종 경로 수정은 인테리어 테스트 2건·frontend 타입 검사·프로덕션 빌드·린트로 확인했다.
전체 PPPP 화면 보존 가드는 수정하지 않았다. 이 검증에서는 배포·커밋·푸시를 하지 않았다.
