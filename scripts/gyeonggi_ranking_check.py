"""실제 API와 브라우저에서 경기 전체 공개 상권 순위를 확인한다."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with urllib.request.urlopen("http://localhost:8000/api/v1/ai/industry-fit?industry=restaurant", timeout=120) as response:
        data = json.load(response)
    scope = next(s for s in data["ranking_scopes"] if s["region"] == "경기도")
    assert scope["ranked_n"] == scope["public_n"] and scope["unranked_n"] == 0
    rows = [r for r in data["districts"] if r["fit_model"] == "industry-gnn-gyeonggi"]
    assert sorted(r["fit_rank"] for r in rows) == list(range(1, scope["public_n"] + 1))
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in [(1280, 900), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.add_init_script("localStorage.setItem('placeos.flow.v1', JSON.stringify({v:1,goal:'start',industryKey:'restaurant',startupRegion:'경기'}))")
            page.goto("http://localhost:5173/#/districts")
            page.get_by_role("button", name="경기", exact=True).click(timeout=120000)
            page.get_by_text(f"경기 공개 상권 {scope['public_n']}곳 중 {scope['ranked_n']}곳을 비교했어요.", exact=False).wait_for(timeout=120000)
            listing = page.get_by_role("list", name="경기 음식점 상권 순위", exact=True)
            assert listing.get_by_role("listitem").count() == 5
            page.get_by_role("button", name=f"경기 순위 {scope['public_n']}곳 모두 보기").click()
            assert listing.get_by_role("listitem").count() == scope["public_n"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.evaluate("scrollTo(0, 0)")
            page.screenshot(path=str(root / f"reports/gyeonggi_ranking_{width}.png"), full_page=False)
            checks.append({"width": width, "shown": listing.get_by_role("listitem").count(), "overflow": False})
            page.close()
        browser.close()
    report = {"scope": scope, "top5": [{"name": r["name"], "rank": r["fit_rank"]} for r in rows[:5]], "browser": checks}
    (root / "reports/gyeonggi_ranking_check_2026-11-04.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
