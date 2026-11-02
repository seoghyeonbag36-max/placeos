"""실제 지도 SDK 인증·타일·PPPP 표면 검사. 키·요청 전체 URL은 보고서에 기록하지 않는다."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    out = Path("reports/renewal")
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"base": "http://localhost:5173", "auth_http_statuses": [], "page_errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--host-resolver-rules=MAP localhost 127.0.0.1"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
        ctx.add_init_script("localStorage.setItem('placeos.business.v1',JSON.stringify({status:'browsing'}));")
        page = ctx.new_page()
        page.on("response", lambda r: report["auth_http_statuses"].append(r.status)
                if "oapi.map.naver.com/v3/auth" in r.url else None)
        page.on("pageerror", lambda _: report["page_errors"].append("browser page error"))
        page.goto("http://localhost:5173/#/explore?track=page&district=garosugil", timeout=60000)
        page.get_by_role("group", name="지도 데이터 레이어").wait_for(timeout=60000)
        try:
            page.wait_for_function("Boolean(window.naver?.maps?.Map) && document.querySelectorAll('.map-canvas img').length > 0", timeout=40000)
            page.wait_for_function("[...document.querySelectorAll('.map-canvas img')].some(i=>i.complete && i.naturalWidth>0)", timeout=20000)
            page.locator(".b-name").first.wait_for(timeout=60000)
            page.wait_for_timeout(1500)
        except Exception:
            report["wait_completed"] = False
        report["sdk_available"] = page.evaluate("Boolean(window.naver?.maps?.Map)")
        report["loaded_map_images"] = page.evaluate("[...document.querySelectorAll('.map-canvas img')].filter(i=>i.complete && i.naturalWidth>0).length")
        report["building_rows"] = page.locator(".b-name").count()
        report["map_error_visible"] = page.get_by_text("지도를 불러오지 못했습니다", exact=False).is_visible()
        report["tracks_visible"] = {name: page.get_by_role("button", name=name, exact=True).is_visible()
                                    for name in ["Platform", "Page", "Posting", "Program"]}
        page.screenshot(path=str(out / "live-naver-map-desktop.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(500)
        page.screenshot(path=str(out / "live-naver-map-mobile.png"))
        browser.close()
    report["passed"] = bool(report["sdk_available"] and report["loaded_map_images"] > 0
                             and not report["map_error_visible"] and all(report["tracks_visible"].values())
                             and not report["page_errors"])
    (out / "naver-map-live.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
