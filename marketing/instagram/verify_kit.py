"""인스타그램 산출물의 파일·문구·렌더링·출처 계약을 검증한다."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent


def logo_export_check() -> dict[str, object]:
    with Image.open(ROOT / "placeos-logo-transparent.png") as logo:
        assert logo.mode == "RGBA", "로고에 알파 채널이 필요합니다."
        assert logo.getchannel("A").getextrema() == (0, 255), "투명 영역을 확인하세요."
        dimensions = logo.size
    with Image.open(ROOT / "placeos-profile.png") as avatar:
        assert avatar.width == avatar.height and avatar.width >= 1024
    return {"result": "PASS", "logo_size": dimensions}


def instagram_copy_check() -> dict[str, object]:
    bio = (ROOT / "bio.txt").read_text(encoding="utf-8").strip()
    assert 0 < len(bio) <= 150, "소개글은 150자 이하여야 합니다."
    assert bio in (ROOT / "02-profile.md").read_text(encoding="utf-8")
    return {"result": "PASS", "bio_characters": len(bio)}


def template_render_check() -> dict[str, object]:
    checked = []
    with sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page(viewport={"width": 1250, "height": 2100})
        for filename in ("posts.html", "stories.html"):
            page.goto((ROOT / filename).as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            for art in page.locator(".art").all():
                name = art.get_attribute("data-export")
                expected = (1080, 1920 if "story" in art.get_attribute("class").split() else 1350)
                with Image.open(ROOT / f"{name}.png") as output:
                    assert output.size == expected, f"{name}: 크기 오류"
                errors = art.evaluate("""e => {
                    const errors = [];
                    const frame = e.getBoundingClientRect();
                    const footer = e.querySelector('.foot').getBoundingClientRect();
                    for (const child of e.children) {
                        if (child.classList.contains('foot')) continue;
                        const r = child.getBoundingClientRect();
                        if (r.bottom > footer.top - 12) errors.push('하단 문구와 겹침: ' + child.className);
                    }
                    for (const text of e.querySelectorAll('h1,h2,p,strong,.series,.eyebrow,.choices span')) {
                        const r = text.getBoundingClientRect();
                        if (r.left < frame.left || r.right > frame.right || r.bottom > frame.bottom) errors.push('문구가 캔버스 밖에 있음');
                        if (text.scrollWidth > text.clientWidth + 2) errors.push('문구 가로 넘침: ' + text.textContent);
                    }
                    return errors;
                }""")
                assert not errors, f"{name}: {errors}"
                checked.append(name)
        browser.close()
    assert len(checked) == 7
    return {"result": "PASS", "templates": checked}


def ad_source_check() -> dict[str, object]:
    guide = (ROOT / "05-ad-guide.md").read_text(encoding="utf-8")
    links = re.findall(r"https://[^)\s]+", guide)
    assert len(links) >= 6
    assert all(urlparse(link).hostname in {"www.facebook.com", "www.facebookblueprint.com"} for link in links)
    assert "첫 실험 제안" in guide and "420,000" in guide and "미확인" in guide
    return {"result": "PASS", "official_source_links": len(links), "note": "링크·출처 구분의 정적 검증이며 실제 광고 계정 검증은 아님"}


def main() -> None:
    result = {check.__name__: check() for check in (
        logo_export_check, instagram_copy_check, template_render_check, ad_source_check
    )}
    (ROOT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
