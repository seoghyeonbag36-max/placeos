# 인스타그램 데이터 — 공식 Graph API 로만 모은다 (2026-11-22)

> **결정(사용자 2026-11-22)**: 「Platform 의 SNS/IT 데이터 범위 — 인스타그램 데이터도 수집할 것」.
> **이 문서의 판단**: 공식 Instagram Graph API(해시태그 검색)만 쓴다. 비공식 수집(스크래핑·로그인 크롤링·수집 대행)은 쓰지 않는다.
> 수집기·Gold·화면은 만들었고 배포한다. **실제 수치는 아직 0건이다** — 이 계정에 인스타 공식 API 키가 없다(`--check` 결과 · 아래 §4).

## 1. 공식 문서로 확인한 것 (2026-11-22 · 출처는 §6)

| 항목 | 내용 |
|---|---|
| 어느 API | **Instagram API with Facebook Login**(graph.facebook.com) 만 해시태그 검색을 지원한다. Instagram Login 쪽은 「지원 안 함」. 최신 그래프 API 는 **v27.0**(2026-11-04) |
| 호출 | `GET /ig_hashtag_search?user_id=&q=` → 해시태그 id · `GET /{id}/top_media`(인기 게시물) · `GET /{id}/recent_media`(**최근 24시간** 게시물) · 쪽마다 최대 50건 · `after` 커서만 · `GET /{ig-user}/recently_searched_hashtags`(지난 7일에 검색한 태그 id) |
| 받는 칸 | caption · comments_count · like_count(주인이 숨기면 없음) · media_type · permalink · timestamp · media_url 등. **계정 이름(username)은 요청할 수 없다** |
| 전체 게시물 수 | **공식으로는 없다** — 해시태그 노드는 id·name 뿐이다. 그래서 화면은 「최근 24시간 표본」이라고 밝힌다 |
| 한도 | 한 프로페셔널 계정이 **이어지는 7일 동안 고유 해시태그 30개**. 같은 태그를 다시 검색하면 다시 세지 않는다. top/recent 를 부르는 것도 검색으로 센다. 2027-02-16 부터 top_media 는 한 번에 200건 상한 |
| 준비물 | 인스타 **비즈니스·크리에이터 계정** + 연결된 **페이스북 페이지** · Meta 앱 · 권한 `instagram_basic`(페이지 역할을 비즈니스 관리자로 받았으면 `pages_read_engagement` 등 하나 더) · 기능 **Instagram Public Content Access** — **앱 심사 + 비즈니스 인증**이 있어야 실데이터를 받는다 · 페이지 작업 권한이 있는 사용자의 토큰(장기 토큰 약 60일 · 갱신 가능) |
| 심사 위험 | 기능 페이지의 허용 용도(캠페인 해시태그 추적 · 브랜드 여론 · 이벤트 참가자 확인 · 고객 응대)에 **상권 분석은 없다** → 승인이 보장되지 않는다. 심사용 화면 녹화가 필요하다 |
| 심사 전 | 개발 모드(Standard Access)에서 앱 역할이 있는 사람이 해시태그 검색을 시험할 수 있는지는 **공식 문서에 없다(미확인)** |

## 2. 약관 — 무엇을 지키나 (Meta 플랫폼 약관 · 한국어판 조항 번호)

- **판매 금지**(§3.a.iv) — 플랫폼 데이터는 집계·익명·가공 데이터를 포함한다(§12.l). → **인스타 집계는 유료 상품(공실 진단 상세 리포트·광고·가격 산정)에 싣지 않는다.**
  `apps/backend/tests/test_instagram_context.py::test_paid_products_do_not_read_instagram` 이 유료 경로가 인스타 모듈을 읽지 않음을 잠근다. 무료 Platform 화면에만 보인다.
- **필요 없으면 지운다**(§3.d.i.2.a) · 그 제품을 그만두면 지운다(§3.d.i.2.b) · 요청이 오면 고치거나 지운다(§3.d.i.1).
  → Bronze 는 집계만, Gold 는 거점 최신 1건만 둔다. 인스타를 그만두면 `data/gold/platform_instagram.json` 과 Bronze `platform13/*/instagram_hashtags.json` 을 지운다.
- **문서가 허용한 목적으로만 처리**(§3.a.viii) · 핵심 기능·처리를 크게 바꾸면 다시 심사(§3.a.vii) — 심사 때 보여 준 용도 밖으로 쓰지 않는다.
- **재식별 금지**(§3.a.vi) · 사용자 프로필 만들기 금지(§3.a.v) — 계정·본문을 남기지 않고, 함께 쓰인 태그는 **서로 다른 게시물 5건 이상 · 20자 이하**만 싣는다.
- ⚠ 「집계가 §3.d.i.2.d 의 비식별 예외에 드는가」·고정 보관 기간·표시 요건은 **확인 못 했다**(Developer Policies · 인스타 전용 데이터 처리 문서는 이번에 못 읽었다) → 변호사 자문 E4 ⑩ 으로 넘긴다.

## 3. 왜 비공식 수집을 쓰지 않나

- 인스타그램 이용약관이 허가 없는 자동 수집을 금지한다. 해시태그 페이지는 로그인을 요구한다 — 로그인 크롤링은 계정·약관 위반이다.
- 수집 대행(유료 스크래퍼)도 같은 약관 위험을 사는 것이고, M&A 실사에서 약관 위반 데이터 파이프라인은 감점 항목이다(사업 목표 — CLAUDE.md).
- CrowdTangle 은 2024-08-14 에 닫혔고(보도), Basic Display API 는 2024-12-04 부터 오류를 낸다(Meta 개발자 문서 검색 결과 — 페이지 본문은 못 읽음), Meta Content Library 는 비영리·학술 기관만 신청할 수 있다 → 쓸 수 있는 공식 길은 위 해시태그 검색 하나다.
- 비공식 수집을 하려면 **사용자의 별도 결정**이 필요하다(비용 · 약관 위험을 사용자가 지는 일이다).

## 4. 만든 것

| 층 | 파일 | 내용 |
|---|---|---|
| 대응표 | `data/config/instagram_hashtags.py` | 서울 81거점 → 대표 해시태그 하나(규칙 + 예외 16개 · 다른 뜻으로 더 쓰이는 이름은 역·동 이름으로: 수유 → 수유역 등) · 같은 태그를 쓰는 거점(잠실 · 잠실 관광특구)은 한 번만 검색 |
| 수집 | `data/collectors/instagram_hashtags.py` | 공식 API 만 · `--check`(한도를 쓰지 않고 키·계정·남은 한도 확인) · 7일 30태그 한도 안에서 가장 오래전에 모은 거점부터 · 이번 7일에 이미 검색한 태그는 20시간 뒤 한도 없이 다시 · 호출 한도·토큰 만료(코드 4·17·32·190·613)면 멈추고 지금까지 저장 · **토큰은 어디에도 찍지 않는다**(오류 문구에서도 지운다) · **계정·본문·링크·게시물 id 를 남기지 않는다** |
| Gold | `data/pipelines/build_instagram_gold.py` → `data/gold/platform_instagram.json` | 수집 전에도 81거점의 해시태그와 `pending` 을 싣는다(컨테이너에는 `data/config` 가 없다) · 태그가 바뀐 거점은 옛 값을 버린다 · 30일이 지나면 화면이 「지난 값」이라고 말한다 |
| API | `app/services/instagram_context.py` · `platform_profile.identity()["instagram"]` | `GET /api/v1/commercial-districts/{id}/platform` 의 `identity.instagram` · 수집된 거점만 출처 줄에 인스타를 적는다 |
| 화면 | `components/InstagramPanel.tsx` · `PlatformConsole` | 「상권 특성 자세히 보기 › 밖에서 뭐라고 불리나」의 인스타그램 칸 · 수집된 거점만 결론 줄(③)에 「인스타 #태그 최근 24시간 n건」 · 수집 전이면 이유(연결 전 / 차례 대기 / 태그 없음)와 태그 링크만 · 검색어 링크 칸 문장도 상태에 맞춘다 |
| 테스트 | `data/tests/test_instagram_hashtags.py`(13) · `apps/backend/tests/test_instagram_context.py`(5) · `InstagramPanel.test.tsx`(4) · `PlatformConsole.test.tsx`(+1) | 가짜 Graph 만 부른다 · 한도 · 태그 공유 · 토큰·계정·본문 누출 없음 · 수집 전 수치 없음 · 유료 경로 차단 |

랜딩·단계 머리 문구에는 **인스타그램을 아직 쓰지 않았다** — 수치가 0건인 동안 쓰면 거짓 광고다(랜딩 규칙). 수집이 돌기 시작하면 `Landing.tsx` Platform 본문에 더한다.

## 5. 연결하는 법 — 사용자 몫

1. 인스타그램 계정을 **비즈니스(또는 크리에이터)** 로 바꾸고 **페이스북 페이지**에 연결한다.
2. developers.facebook.com 에서 앱(비즈니스 유형)을 만들고 「Instagram API with Facebook Login」을 붙인다. 권한 `instagram_basic` · `pages_show_list` · (비즈니스 관리자로 받은 페이지면) `pages_read_engagement`.
3. 기능 **Instagram Public Content Access** 를 신청한다 — **비즈니스 인증 + 앱 심사**(해시태그를 입력해 검색하고 결과를 보여 주는 화면 녹화). 용도 설명은 「상권(동네) 단위 해시태그 반응을 집계해 무료 화면에 보여 주며 계정·본문은 저장하지 않는다」로 사실대로 적는다. 승인은 보장되지 않는다(§1 심사 위험).
4. 페이지 작업 권한이 있는 사용자의 **장기 토큰**을 받아 `data/.env` 에 `INSTAGRAM_ACCESS_TOKEN=…` · `IG_USER_ID=…`(인스타 프로페셔널 계정 id)를 넣는다. 약 60일마다 갱신한다. ⚠ 토큰은 저장소에 커밋하지 않는다.
5. `python -m data.collectors.instagram_hashtags --check` → `connected: True` 와 남은 한도 확인 →
   `python -m data.collectors.instagram_hashtags` → `python -m data.pipelines.build_instagram_gold` → Gold 커밋·배포. 81거점 한 바퀴는 약 3주(주 30태그).

## 6. 출처 (2026-11-22 조회)

- 해시태그 검색 가이드 — developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search
- IG Hashtag · recent_media · top_media · recently_searched_hashtags 참조 — developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag(/recent-media · /top-media) · …/ig-user/recently_searched_hashtags
- Instagram Public Content Access 기능 — developers.facebook.com/docs/features-reference/instagram-public-content-access
- Instagram Platform 개요(로그인 제품 비교) · 시작하기 — developers.facebook.com/docs/instagram-platform/overview · …/instagram-api-with-facebook-login/get-started
- 그래프 API 변경 기록(v27.0) — developers.facebook.com/docs/graph-api/changelog/ · 접근 수준 — …/graph-api/overview/access-levels · 장기 토큰 — …/facebook-login/guides/access-tokens/get-long-lived
- Meta 플랫폼 약관 — developers.facebook.com/terms/ · Meta Content Library 자격 — transparency.meta.com/researchtools/meta-content-library
- 미확인(공식 페이지 본문을 못 읽음): Basic Display 종료 공지 · CrowdTangle 종료(보도) · 심사 전 개발 모드 동작 · 시스템 사용자 토큰 수명 · 인스타 전용 데이터 처리 정책
