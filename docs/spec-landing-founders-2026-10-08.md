# 창업자용 랜딩 — 명세와 카피 근거 (2026-10-08)

로그인 전 첫 화면(`apps/frontend/src/pages/Landing.tsx` · `Landing.css`). [prd-landing.md](prd-landing.md)(09-07)를 **대체하지 않는다** — 그 문서는 독자가
**투자자**이고, 이 페이지는 **창업자**다. 투자자용 랜딩이 필요해지면 그 문서를 따로 쓴다.

## 0. 왜 만들었나

첫 화면이 로그인 벽이었다(10-02 #81). 인스타·광고로 온 사람이 서비스가 무엇인지 보기 전에 가입부터 요구받았다.
랜딩이 그 앞에서 「무엇을 하고, 무엇을 못 하고, 가입하면 무엇을 받는지」를 말한다.

## 1. 독자와 흐름

독자: **업종이 정해진 창업자 · 지금 상권에서 업종을 바꾸거나 같은 업종으로 상권을 옮기려는 사업자**(2026-09-13 주요 고객 재정의).
세 목적 문구는 앱의 시작 카드와 **같은 코드**(`lib/businessProfile.GOALS`)를 쓴다 — 랜딩과 앱의 말이 어긋나지 않게.

| URL | 로그아웃 상태에서 보이는 것 |
|---|---|
| `/` · `/#how` 같은 랜딩 앵커 | **랜딩** |
| `#signup` · `#login` | 가입·로그인(`Home`) — 랜딩의 CTA 가 가는 곳 |
| `#account` · `#feedback` | 가입·로그인(`Home`) — 로그아웃·세션 만료 직후 해시가 남아 있어도 쓰던 사람을 소개로 보내지 않는다 |
| `#admin` | 관리자 커버리지(변경 없음) |

`Home` 의 「← PlaceOS 소개」는 해시를 비워 랜딩으로 돌린다. 브라우저 뒤로가기도 같다.
`Home` 은 이미 열려 있는 동안 해시만 `#signup ↔ #login` 으로 바뀌어도 따라간다.

## 2. 카피 규칙 — 어기면 거짓 광고다

1. **숫자는 `lib/landingFacts.ts` 한 곳에서만.** 지금은 서빙 거점 수 하나(81). `tests/test_landing_facts.py` 가 `data.config.page_hubs.ACTIVE_HUBS` 와 어긋나면 운다.
2. **쓰지 않는 것**: 공실 예측 정확도(LSTM 두 축은 **확인 대기** — CLAUDE.md KPI①) · 업종 추천 적중률(기준선 대비 +3.4%p 일 뿐 — 광고 숫자가 못 된다) · 고객 수·파일럿 실적(0건) · 요금(정해지지 않음) · 시장 규모.
3. **「아직 못 하는 것」 절을 빼지 않는다.** 시범 운영 단계에서 가장 믿을 만한 문장이 거기 있다.
4. **금지 표현**: AI 기반 · 혁신적인 · 원스톱 · 올인원 · 차세대 · 최적의 · 완벽한.

`pages/Landing.test.tsx` 가 2·4 와 숫자 허용 목록(81 · 단계 번호 1~4)을 잠근다. 변조(「정확도 92%」·「혁신적인」)를 넣어 세 테스트가 빨개지는 것을 2026-10-08 에 확인했다.

## 3. 문장 → 근거

| 랜딩의 문장 | 근거 |
|---|---|
| 서울 **81개** 상권 · 건물·층 단위 | `LANDING_HUBS` · `pppp_status` Page 게이트 「Tier1 대장 실측 81/81」 · [apply/data-sources.md](apply/data-sources.md) |
| 건축물대장 + 상가 정보를 맞춰 층 단위로 센다 | 공실 레이어 `stores+ledger` · [feature-page.md](feature-page.md) |
| 한국부동산원 R-ONE 공실률과 나란히, 다르면 다른 대로 | API `anchor_pct` · `pppp_status` 「R-ONE 앵커 대조 보유 81/81」 |
| 세 가지 가격대(고급화·가성비·기능중심)로 비용·회수 기간 | [feature-posting.md](feature-posting.md) 3-Tier |
| 모객·자리 연계·「안 나오면 접는다」 기각 조건 | [feature-program.md](feature-program.md) §0-V 검증 지표(기각 조건) |
| 생성한 계획이 입력에 없는 금액·경험을 지어내지 않았는지 검사 | `services/ha_guard.py`(HA 후처리) |
| 업종 추천은 「가장 흔한 업종」 기준과 비교 | CLAUDE.md KPI① 거점 사전분포 베이스라인 |
| 공실 「예측」은 아직 검증 전 · 화면의 공실률은 센 값 | CLAUDE.md KPI① LSTM 확인 대기 · 공실률은 대장+상가 정보 집계 |
| 지금은 결제 없이 · 요금은 정해지지 않음 | [decision-lightweight-first-2026-10-05.md](decision-lightweight-first-2026-10-05.md) §3(PG 금지) · 08-26 결정 2(무상 파일럿) |
| 영업 중인 가게의 홍보는 다루지 않는다 | CLAUDE.md Program 행(2026-09-17 대상 재정의) |
| 서울만 · 경기와 지방은 볼 수 없다 | 고양·파주 20거점은 서빙 보류(CLAUDE.md 「거점」 행) |
| 임대 시세는 공식 통계 기준 · 호가와 다를 수 있다 | 임대 레이어 R-ONE(`pppp_status` 4대 히트맵) |

## 4. 공개 홍보 전에 막아야 하는 것

- ⚠ **구글 로그인이 아직 「테스트 중」이다.** 가입 화면은 구글 버튼을 먼저 그리는데, 테스트 사용자가 아닌 방문자가 누르면 구글이 막는다.
  이메일 가입은 접어 둔 채다. **인스타·광고로 사람을 보내기 전에** [runbook-custom-domain-placeos-kr-2026-10-08.md](runbook-custom-domain-placeos-kr-2026-10-08.md) §5 를 끝내거나, 그 전에는 홍보를 하지 않는다.
- **링크 미리보기(OG)** 는 없다. 도메인이 살아난 뒤 같은 런북 §4 의 `index.html` 항목으로 넣는다(먼저 넣으면 죽은 주소를 가리킨다).
- **상표**는 이름의 선등록이 없다는 데까지 확인했다 → [finding-placeos-trademark-2026-10-08.md](finding-placeos-trademark-2026-10-08.md). 광고비는 변리사 확인 뒤.

## 5. 일부러 넣지 않은 것

- **앱 화면 캡처.** 지도 화면은 네이버 지도 타일을 담는다 — 타일을 광고 소재로 쓸 수 있는지 확인하지 않았다. 그리고 화면은 자주 바뀌어 캡처가 낡는다(이 저장소가 반복해 당한 양식).
  대신 이미 있는 자체 일러스트(`design/assets/illustrations/iso-commercial-building.svg` · 랜딩 전용 — 앱 화면에 넣지 않는다)를 썼다.
  캡처를 넣으려면 **지도 타일이 없는 패널**(층 스택 · 3-Tier 카드)만 요소 단위로 찍고, 찍은 날짜와 갱신 절차를 이 문서에 적는다.
- 문의 폼·뉴스레터 — 받는 개인정보를 늘리면 처리방침·탈퇴를 같이 고쳐야 한다(decision-lightweight-first). 문의는 `mailto` 하나다.
- 가격·고객 후기·언론 — 없는 것을 슬롯으로도 두지 않았다.

## 6. 바꾼 파일

`pages/Landing.tsx` · `pages/Landing.css` · `lib/landingFacts.ts` · `components/TrackIcons.tsx`(레일 아이콘을 App 에서 옮김) · `design/assets/iso-commercial-building.svg` ·
`App.tsx`(로그아웃 상태 해시 분기) · `pages/Home.tsx`(소개 링크 · 해시 추종) · 테스트 `Landing.test.tsx` · `AppAuth.test.tsx` · `tests/test_landing_facts.py`.
메인 번들 225.05 → 231.67 kB(gzip 76.5 → 79.2).
