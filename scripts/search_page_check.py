"""검색 가로 이동과 Page 목록의 실제 WebGL 트윈 진입을 검증한다."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    out = Path("reports/pppp_screens")
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1280, 390):
            page = browser.new_page(viewport={"width": width, "height": 800})
            flow = {"v": 1, "goal": "start", "startupOrder": "region", "startupRegion": "서울"}
            page.add_init_script(f"localStorage.setItem('placeos.flow.v1', {json.dumps(json.dumps(flow))})")
            page.goto("http://localhost:5173/#/districts")
            field = page.get_by_placeholder("동네 이름으로 찾기")
            field.wait_for()
            page.locator(".fl-row").first.wait_for()
            before = field.bounding_box()
            field.fill("연희")
            page.wait_for_timeout(500)
            after = field.bounding_box()
            assert abs(before["x"] - after["x"]) < 1, (before, after)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            print(f"PASS 검색 위치 유지 · {width}px · x={before['x']} → {after['x']}", flush=True)
            page.close()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto("http://localhost:5173/#/explore?track=page&district=yeonhui")
        page.get_by_role("button", name="3D 트윈으로 보기").first.click(timeout=60000)
        page.get_by_role("dialog").wait_for()
        page.locator("[data-ready='1'] canvas").wait_for(timeout=60000)
        page.screenshot(path=str(out / "page-twin.png"))
        print("PASS Page 목록 → 실제 WebGL 3D 트윈", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
