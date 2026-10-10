# PlaceOS 인스타그램 시작 패키지

입점을 준비하는 자영업자·브랜드 담당자를 위한 브랜드와 콘텐츠 양식. 작성일 2026-10-09.

| 순서 | 결과 | 파일 |
|---|---|---|
| 1 | 로고·프로필 심볼·브랜드 방향 | `01-brand.md`, `placeos-logo-transparent.png`, `placeos-profile.png` |
| 2 | 계정 소개글·하이라이트·이름 후보 | `02-profile.md`, `bio.txt` |
| 3 | 3장 캐러셀·자료 양식·첫 캡션 | `03-post-guide.md`, `posts.html`, `post-01`~`post-04` PNG |
| 4 | 투표·체크리스트·링크 스토리 | `04-story-guide.md`, `stories.html`, `story-01`~`story-03` PNG |
| 5 | 광고 목표·타깃·예산·측정 조건 | `05-ad-guide.md` |

브랜드 메시지: **좋은 입점은, 상권을 읽는 것부터.**

## 사용 순서

1. 프로필에는 `placeos-profile.png`를 등록한다. 로고는 AI 생성 PNG 시안이다.
2. `bio.txt`를 복사하고 실제 서비스 링크를 확인한다. 사용자 이름의 가용성은 미확인이다.
3. `post-01-cover.png` → `post-02-checklist.png` → `post-03-cta.png` 순서로 캐러셀을 구성하고 가이드의 캡션을 붙인다.
4. 스토리 PNG를 올리고 투표·링크 스티커를 안내 영역 위에 추가한다.
5. 자료 양식 `post-04-data-template.png`는 검증한 실제 데이터로 교체한 뒤 내보낸다. 미발행 양식을 그대로 게시하지 않는다.
6. 광고는 목적지·문의 운영·측정이 준비된 상태에 맞춰 가이드를 적용한다. 예산은 제안이며 실제 집행은 별도다.

## 편집과 내보내기

HTML 양식을 브라우저에서 열어 문구를 클릭하면 편집할 수 있다. 브라우저에서 바꾼 문구는 자동 저장되지 않는다. 영구 변경은 HTML 파일에 반영하고 아래 명령으로 PNG를 재생성한다. 창을 캡처하는 대신 각 캔버스를 지정된 크기로 출력한다.

```powershell
python marketing/instagram/render_templates.py
python marketing/instagram/verify_kit.py
```

필요한 환경: Python, Pillow, Playwright와 Playwright Chromium. 이번 환경에서 설치된 구성으로 실행했다. 편집 후 긴 문구가 겹치면 문구를 줄이고 다시 렌더링한다. HTML·CSS·로고 PNG는 같은 폴더에 둔다.

로고는 built-in image_gen으로 생성했다. 게시물·스토리는 글자를 정확히 편집할 수 있는 HTML/CSS로 구성했다. 생성 프롬프트는 `01-brand.md`에 있다.

출처: 제품 구조는 저장소 AGENTS.md, 브랜드 컬러는 `design/brand/naver-brand.md`. 광고 공식 근거는 `05-ad-guide.md`의 각 관련 문단에 연결했다. 실측 상권 수치·성과·후기·행사 데이터는 이 패키지에서 새로 만들지 않았다. 지도는 개념도다.

검증 결과는 `verification.json`에 저장한다. 광고 출처 검사는 링크와 제안/미확인 표기 확인이며 실제 계정의 설정 확인이나 광고 성과 검증을 뜻하지 않는다. 계정 생성·게시·광고 집행·커밋·푸시는 수행하지 않았다.
