# PlaceOS 게시물 초안 5편

2026-10-10 작성. 기존 PlaceOS 청록색·로고·1080×1350 양식을 바탕으로 각 주제를 3장 캐러셀로 만들었다. 대상은 입점을 준비하는 자영업자와 브랜드 담당자다.

1. PlaceOS를 시작한 이유 — 공실을 창업과 재창업의 사이클이 끊긴 자리로 보는 창업자의 관점.
2. Platform이 뭐야? — Place → Platform, 상권을 사업의 무대로 읽기.
3. Page가 뭐야? — Product → Page, 상권 안의 후보 공간 살펴보기.
4. Posting이 뭐야? — Price → Posting, 입점 가격대와 비용 가정 비교.
5. Program이 뭐야? — Promotion → Program, 아이템 검증의 실행과 판단 기준 준비.

## 파일 사용

- `preview.html`: 5편을 한눈에 확인. PNG를 누르면 개별 이미지를 연다.
- `preview.png`: 전체 미리보기. 인스타그램에 게시할 원본은 개별 PNG다.
- `01-why-placeos-01.png`~`05-program-03.png`: 총 15장. 주제별 01→02→03 순서로 업로드한다.
- `captions.md`: 각 게시물의 캡션·이미지 문구·대체 텍스트. 내부 출처와 검토 메모는 캡션에 포함하지 않는다.
- `series.html`: 문구를 클릭해 검토할 수 있는 편집 원본. 브라우저 편집은 자동 저장되지 않는다.
- `content.json`: 문구의 저장 원본. 영구 변경은 여기에서 한다.
- `build_drafts.py`: HTML과 PNG 생성 및 검증. 로고와 기존 CSS를 부모 폴더에서 복사한다.

```powershell
python marketing/instagram/drafts-2026-10-10/build_drafts.py
```

필요 환경: Python·Pillow·Playwright·Playwright Chromium. 기존 패키지와 같은 환경이다. 출력 파일은 이 폴더 안에서 갱신된다. 기존 게시물·스토리 파일과 제품 코드는 수정하지 않는다.

## 출처와 범위

첫 게시물의 시작 계기는 2026-10-10 사용자가 직접 제공했다. 공실에 대한 관점으로 서술하며 공실 발생의 모든 원인을 입증한 통계로 쓰지 않는다. SNS·AI·IT 데이터 활용은 창업의 의도다. 모든 SNS 데이터가 현재 기능에 배선됐다는 뜻이 아니다.

네 기능은 `CLAUDE.md`의 PPPP Framework와 `docs/feature-platform.md`, `docs/feature-page.md`, `docs/feature-posting.md`, `docs/feature-program.md`의 정의를 기준으로 설명한다. Program은 팝업·가오픈·MVP 등 아이템 검증을 중심으로 설명했다. 코드에서 작업 중인 새 모드는 확정 기능으로 홍보하지 않았다.

수치·매물·고객 후기·공실 원인 통계·성과를 생성하지 않았다. 4칸 흐름 도식은 개념 설명이며 실제 제품 화면이나 실측 데이터가 아니다. 기능 정의 설명용 초안이며 현재 모든 운영 경로가 정상임을 증명하는 게시물이 아니다. 실제 계정 게시와 광고 집행은 수행하지 않았다.

통과 조건: `draft_content_check`(5편·각 3장·PPPP 대응·출처·캡션 분량·미확인 표현)와 `draft_render_check`(15장·1080×1350·문구 안전 영역·하단 겹침). 결과는 `verification.json`에 기록한다.
