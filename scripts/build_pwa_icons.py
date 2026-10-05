"""PWA 홈 화면 아이콘 생성 — 레일 로고(App.css .rail-logo-mark)와 같은 남색·같은 글자 "P".

앱스토어 출시 대신 웹앱(PWA)으로 먼저 간다(docs/decision-lightweight-first-2026-10-05.md §4).
홈 화면에 추가하려면 PNG 아이콘이 필요한데(안드로이드 192·512, iOS 180), 손으로 그리면 브랜드가
바뀔 때 다시 못 만든다. 그래서 앱이 자체 호스팅하는 Pretendard Bold 로 Chromium 에서 그린다.

    python scripts/build_pwa_icons.py          # → apps/frontend/public/icons/*.png

필요: `pip install playwright` + `python -m playwright install chromium` (verify 스킬과 같은 환경).
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "apps" / "frontend" / "public" / "fonts" / "Pretendard-Bold.subset.woff2"
OUT = ROOT / "apps" / "frontend" / "public" / "icons"

NAVY = "#3A5A98"   # tokens.css --ui-navy (레일 로고 바탕)
WHITE = "#FFFFFF"  # tokens.css --surface (레일 로고 글자)

# (파일, 한 변 px, 모서리 반경 비율, 글자 크기 비율)
#  any      — 레일 로고처럼 둥근 사각형, 바깥은 투명(안드로이드가 그대로 쓴다)
#  maskable — 바탕을 꽉 채운다. OS 가 원·물방울로 잘라도 글자가 안전 영역(지름 80%) 안에 남게 작게
#  apple    — iOS 는 투명을 검게 칠하고 모서리를 스스로 깎으므로 꽉 채운다
ICONS = [
    ("icon-192.png", 192, 0.29, 0.47),
    ("icon-512.png", 512, 0.29, 0.47),
    ("icon-maskable-512.png", 512, 0.0, 0.40),
    ("apple-touch-icon.png", 180, 0.0, 0.47),
]


def _html(size: int, radius: float, font_ratio: float) -> str:
    return f"""<!doctype html><html><head><style>
@font-face {{ font-family: "Pretendard"; src: url("{FONT.as_uri()}") format("woff2"); font-weight: 700; }}
html, body {{ margin: 0; background: transparent; }}
.mark {{ width: {size}px; height: {size}px; display: flex; align-items: center; justify-content: center;
  border-radius: {round(size * radius)}px; background: {NAVY}; color: {WHITE};
  font-family: "Pretendard"; font-weight: 700; font-size: {round(size * font_ratio)}px; letter-spacing: -.02em; }}
</style></head><body><div class="mark">P</div></body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, size, radius, font_ratio in ICONS:
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(_html(size, radius, font_ratio))
            page.evaluate("document.fonts.ready")
            page.locator(".mark").screenshot(path=str(OUT / name), omit_background=True)
            page.close()
            print(f"OK {name} {size}x{size}")
        browser.close()


if __name__ == "__main__":
    main()
