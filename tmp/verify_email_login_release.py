"""이메일 로그인 UI 제거를 프로덕션 브라우저에서 확인한다."""
from pathlib import Path
from playwright.sync_api import sync_playwright

base = "https://placeos.co.kr"
out = Path(__file__).resolve().parents[1] / "reports" / "email_login_release"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844})
    for path, name in [("/#login", "login"), ("/#/me", "me")]:
        page.goto(base + path, wait_until="domcontentloaded")
        page.get_by_role("button", name="네이버로 계속하기", exact=True).wait_for(timeout=30000)
        page.get_by_role("button", name="카카오로 계속하기", exact=True).wait_for(timeout=30000)
        assert page.locator('input[type="email"], input[type="password"]').count() == 0
        assert page.get_by_role("button", name="이메일로 로그인", exact=True).count() == 0
        assert page.get_by_text("또는 이메일·비밀번호로 가입한 계정", exact=True).count() == 0
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)
        print(f"PASS {name}: 이메일 로그인 UI 없음 · 네이버/카카오 버튼 유지")
    browser.close()
