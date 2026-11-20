# 결정 — Claude 확장 10개 중 4개 설치 (2026-11-19)

사용자가 「무료 레포 10개」 목록을 주고 PlaceOS 에 맞는 것을 설치·연동하라고 했다. 각 저장소를 `gh api` 로 트리·훅·매니페스트·README 까지 읽고, 설치 뒤 `claude plugin details` 로 상시 토큰 비용을 쟀다.
이전(2026-10-11) 확장팩 키트가 판정했던 5개(superpowers · ui-ux-pro-max · last30days · humanizer · caveman)는 그 판정에 11-16 토큰 절감 결정을 더해 다시 봤다.

## 결론

| # | 저장소 | 판정 | 이유 (한 줄) |
|---|---|---|---|
| 1 | unslop | ✅ 설치 | 훅 0 · 의존 0. 「AI 티 나는 UI」 점검 — 화면 리뉴얼·글꼴 점검 작업(11-02·11-09)과 직결 |
| 2 | ui-ux-pro-max | ✅ 설치 (조건부) | 접근성·차트 질의 DB 가 쓸모. **단 일반 템플릿 권고라 아래 규칙으로만 쓴다** |
| 3 | diagram-design | ✅ 설치 + PlaceOS 스킨 | 데이터 3계층·흐름·로드맵 도식을 SVG/PNG 로. 한글 라벨 규칙(Noto Sans KR · 12px 하한)을 이미 갖췄다 |
| 4 | humanizer | ✅ 설치 (조건부) | 영문 논문 원고용. 한국어 효과는 미확인 |
| 5 | last30days | ⛔ 보류 | Reddit·X·HN 위주 — 한국 상권 담론(네이버 카페·블로그)을 못 본다. 첫 실행이 CLI 를 더 깔고 브라우저 쿠키 접근을 묻는다 |
| 6 | Scrapling | ⛔ 보류 | 수집 소스가 전부 공식 API 다(`data/collectors/` · `data/requirements.txt` 의 playwright·bs4 는 주석 처리). 이 라이브러리의 차별점은 스텔스 브라우저·Cloudflare Turnstile 처리·TLS 지문 위장(README)이라 약관이 있는 사이트에 쓰면 Exit 대상(네이버·카카오·직방) 실사에서 리스크가 된다. 수집 병목은 쿼터지 도구가 아니다 |
| 7 | book-to-skill | ⛔ 보류 | 변환할 책 PDF 가 없다. `npx` 설치는 COMSPEC 문제로도 막힌다 → 필요할 때 |
| 8 | Ponytail | ⛔ 제외 | SessionStart·SubagentStart·**UserPromptSubmit** node 훅 3개(프롬프트마다 node 기동) + 세션마다 규칙·저장소 지도 주입. 11-16 에 걷어낸 「프롬프트마다 주입」과 같은 구조. 「가벼운 대안 먼저」는 이미 규칙이다 |
| 9 | Caveman | ⛔ 제외 | **로컬 프록시** + 텔레메트리(IP·설치 ID) + 「원시인 말투」가 「한국어 상세히」와 충돌. 10-11 에도 제외 |
| 10 | Superpowers | ⛔ 제외 | 스킬 15개 + SessionStart 훅이 기존 `/verify` `/director` `/codex-handoff` 와 겹치고, 병렬 서브에이전트 방법론이 이 계정의 세션 한도와 부딪힌다(메모리 workflow-fanout-hits-session-limit) |

## 설치 상태 (실측)

- 4개 모두 **훅 0 · MCP 0 · 에이전트 0**. 상시 토큰: unslop ~250 · ui-ux-pro-max ~1,073 · diagram-design ~694 · humanizer ~124 = **약 2.1k/세션**. 호출 시 +10k 안팎(스킬 본문).
- scope = **local** → `.claude/settings.local.json`(gitignore). 공유 `settings.json`·클라우드 세션은 영향 없다. 마켓플레이스 4개는 사용자 설정에 등록됐다.
- 새 세션 또는 `/reload-plugins` 뒤에 스킬이 보인다.

## PlaceOS 에서 쓰는 규칙

- **공통**: 색은 토큰만(`src/styles/tokens.css`), **Tailwind·shadcn 도입 금지**, ⛔ **PPPP 네 화면·레일·진입로·랜딩 네 질문은 빼거나 숨기지 않는다**(CLAUDE.md · 가드 `ppppScreens.test.tsx`). 스킬이 이와 충돌하는 변경을 권하면 따르지 않는다.
- **unslop**: 점검·레드라인용. 「화면 구성·순서·기능은 그대로」 가 스킬 원칙이라 PPPP 보존과 같은 방향이다. 문구 패스에서 근거 표기(「자료 부족」 · 「구분 불가」 · 신뢰구간)는 지우지 않는다. 한 번에 한 화면.
- **ui-ux-pro-max**: `--domain ux|chart|…` **질의형으로만** 쓴다. ⚠ `--design-system` 은 쓰지 않는다 — 실측에서 「PlaceOS 부동산 대시보드」 질의에 Glassmorphism · Hero-Centric · Cinzel 서체를 권했다(우린 Pretendard + 토큰). 특히 `--persist` 는 저장소에 MASTER.md 를 쓴다. 스킬이 `python3` 를 부르면 이 PC 에선 Store 스텁이라 `py -3.11` 로 바꾼다.
- **diagram-design**: 프로젝트 마커 `.diagram-design`(`profile: placeos`) → 프로필 `~/.diagram-design/profiles/placeos.md` 가 자동 선택돼 첫 도식의 스킨 확인 게이트가 없다. 색은 `tokens.css` 에서 가져왔고 밝은 배경 글자 대비를 위해 accent 를 `--brand` 보다 어둡게(`#0A7686`) 잡았다. 스킬의 `verify-contrast.py` 20개 검사 통과. PPPP 네 트랙 색(`--track-*`)·`--naver-green` 은 accent 로 쓰지 않는다. docx 에 넣을 땐 PNG 로 내보내고 한글 폰트는 별도 확인.
- **humanizer**: 영문 원고 한정. 수치·인용·판정어는 불변이고 고친 뒤 `python scripts/check_application.py` 를 다시 돌린다. 한국어 문서에는 효과를 확인하기 전까지 쓰지 않는다.

## 되돌리기

```bash
claude plugin uninstall unslop@heydamir --scope local          # 나머지도 같은 형식
claude plugin uninstall ui-ux-pro-max@ui-ux-pro-max-skill --scope local
claude plugin uninstall diagram-design@diagram-design --scope local
claude plugin uninstall humanizer@humanizer --scope local
claude plugin marketplace remove heydamir                      # 마켓플레이스 4개도
rm -r ~/.diagram-design && rm .diagram-design                  # 스킨·마커
```
토큰이 아쉬우면 ui-ux-pro-max 만 먼저 끈다: `claude plugin disable ui-ux-pro-max@ui-ux-pro-max-skill --scope local` (상시 ~1k 로 4개 중 절반).

## 다시 볼 조건

- last30days — 한국어 소스(네이버·카카오)를 지원하거나, 논문 문헌 조사에 arXiv 만 따로 쓸 일이 생기면.
- Scrapling — 공식 API 가 없는 소스가 **데이터 병목** 으로 확인되고 약관 검토가 끝나면.
- book-to-skill — 변환할 도서·보고서 PDF 가 정해지면(저작권 확인 후).
- Superpowers — 세션 한도 문제가 풀리고 병렬 에이전트를 다시 쓰기로 하면.

## 검증

- 실행함: 설치 4건 `claude plugin list` enabled · 설치본 훅/MCP/에이전트 0(`claude plugin details`) · 공유 `settings.json` 변경 0 · `verify-contrast.py` 통과 · ui-ux-pro-max `search.py` 질의 정상(파일 쓰기 없음).
- 실행함(새 세션 로드): `claude -p` 별도 세션의 init 에 4개 플러그인·스킬 10개(+diagram-design 명령 7개) 로드, 프로젝트 `design` 스킬과 이름 충돌 없음, ruflo 플러그인 미로드.
- 실행함(diagram-design 실사용): PPPP 네 단계 도식 `docs/diagrams/pppp-four-steps.html` (Steps · `fit` 976×400). `self_check.py` · `verify_geometry.py` 통과 · PNG 렌더로 눈 검토(1차에서 세로 빈 띠 결함 → `fit` 으로 재구성) · `export_svg.py` 가 한글 보존·엄격 XML 파싱 통과. `verify-steps.py` 의 10건은 전부 색 지적(기본 스킨 hex 하드코딩)이며 같은 파일의 색만 기본 스킨으로 치환한 사본은 통과 → 구조 결함 아님.
- 실행함(PNG @2): `docs/diagrams/pppp-four-steps.png` 1952×800. ⚠ 첫 내보내기는 1952×**802** 였다 — 헬퍼의 기본 뷰포트(1280×720)에서 `body` 세로 가운데 정렬 + eyebrow·h1 소수 높이 때문에 SVG 가 `y=201.39` 에 놓이고 요소 스크린샷이 박스를 올림했다. 래퍼 CSS 를 위쪽 정렬 + 정수 줄 높이(16px·40px)로 고정해 `y=136` 이 되었고 정확히 800 이 나왔다(도식 SVG 는 그대로). 다른 도식을 내보낼 때 크기가 +1px 어긋나면 같은 원인이다.
- 실행함(SVG): `docs/diagrams/pppp-four-steps.svg` (8.1KB). 엄격 XML 파싱 · `<title>` 첫 자식 · 한글 6문장 보존 · `rgba(` 0 · 스크립트·이미지·외부 href 0 · id 는 `pppp-four-steps-` 로 네임스페이스. 단독 SVG 를 브라우저로 렌더해 PNG 와 픽셀 비교: 1952×800 동일 크기, 8/255 넘게 다른 픽셀 0.077%(최대 74/255 · 128 초과 0 — 선 가장자리 안티앨리어싱). ⚠ 글꼴은 Google Fonts `@import` 라 열 때 네트워크 요청이 있고, 원격 글꼴을 안 받는 도구(Word·오프라인 Illustrator 등)는 대체 글꼴로 그린다 → 보고서(docx)에는 PNG 를 쓴다. 오프라인용은 `export_svg.py --system-fonts`.
- 실행함(`/unslop` 실호출): 별도 `claude -p` 세션(읽기 전용)으로 랜딩 점검 → 지적 12건(상 0 · 중 4 · 하 8), 랜딩 파일 변경 0. 슬래시 명령이 본문을 주입했다(`Skill` 도구 호출 0건이어도 해시 경로 `signs.md` 를 정확히 읽음). 재측정으로 #1(의견 보내기가 푸터 링크를 덮음)·#8(h1 자간 −0.04em) 확인, #2 는 행 높이 차이만 확인. ⚠ 한 번에 26턴 · 약 $0.83 · 계정 5시간 한도가 97% 까지 올랐다. 전문 → docs/finding-landing-unslop-audit-2026-11-19.md
- **미실행**: humanizer 한국어 품질 · diagram-design 을 슬래시 명령으로 호출(이번엔 `SKILL.md`·레퍼런스를 읽고 절차를 직접 따랐다) · `lint-skin.py`(설치본 기본 스타일 가이드와 대조해 프로필 색을 못 읽는다).
