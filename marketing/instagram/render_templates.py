"""저장된 HTML 양식을 PNG로 렌더링한다. 기존 PNG는 같은 이름으로 갱신한다."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    root = Path(__file__).resolve().parent
    with sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page(viewport={"width": 1250, "height": 2100}, device_scale_factor=1)
        for filename in ("posts.html", "stories.html"):
            source = root / filename
            if not source.exists():
                continue
            page.goto(source.as_uri())
            page.evaluate("document.fonts.ready")
            page.locator(".brand img").first.wait_for()
            page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            for art in page.locator(".art").all():
                output = root / f"{art.get_attribute('data-export')}.png"
                art.screenshot(path=str(output), animations="disabled")
                print(output.name)
        browser.close()


if __name__ == "__main__":
    main()
