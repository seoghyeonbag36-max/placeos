"""기존 PlaceOS 양식으로 캐러셀 초안·캡션·미리보기를 만든다."""

import html
import json
import re
import shutil
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
JOURNEY = (
    ("Platform", "상권을 읽고", "Place"),
    ("Page", "공간을 살펴보고", "Product"),
    ("Posting", "가격대를 비교하고", "Price"),
    ("Program", "검증을 준비합니다", "Promotion"),
)


def plain(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value.replace("<br>", "\n")))


def draft_content_check(posts: list[dict]) -> dict:
    assert [p["title"] for p in posts] == [
        "PlaceOS를 시작한 이유", "Platform이 뭐야?", "Page가 뭐야?", "Posting이 뭐야?", "Program이 뭐야?"
    ]
    assert [p["frame"] for p in posts[1:]] == [f"{origin} → {name}" for name, _, origin in JOURNEY]
    assert "창업과 재창업의 사이클" in posts[0]["caption"]
    for post in posts:
        assert len(post["slides"]) == 3 and post["sources"] and post["review"]
        assert len(post["caption"]) <= 2200
        visible = post["caption"] + json.dumps(post["slides"], ensure_ascii=False)
        for phrase in ("매출 보장", "성공 보장", "실시간 공실", "actual_open", "단골 고객", "3D 디지털 트윈"):
            assert phrase not in visible, f"확인되지 않은 표현: {phrase}"
    return {"result": "PASS", "posts": len(posts), "slides": 15, "pppp_mapping": "1:1"}


def make_html(posts: list[dict]) -> None:
    shutil.copy2(ROOT.parent / "templates.css", ROOT / "templates.css")
    shutil.copy2(ROOT.parent / "placeos-logo-transparent.png", ROOT / "placeos-logo-transparent.png")
    art = []
    captions = ["# PlaceOS 게시물 초안 5편", "작성일: 2026-10-10. 각 게시물은 3장 캐러셀입니다. 아래 캡션 블록을 복사해 사용합니다. 근거·검토 메모는 발행 문구에 포함하지 않습니다."]
    preview = []
    for index, post in enumerate(posts, 1):
        captions.extend([f"## {index}. {post['title']}", "### 캡션", f"```text\n{post['caption']}\n```", "### 이미지 문구·대체 텍스트"])
        links = []
        for number, slide in enumerate(post["slides"], 1):
            filename = f"{post['slug']}-{number:02}"
            inner = f"<div class='eyebrow' contenteditable='true'>{slide['eyebrow']}</div><h1 contenteditable='true'>{slide['heading']}</h1>"
            if slide.get("intro"):
                inner += f"<p class='intro' contenteditable='true'>{slide['intro']}</p>"
            if slide.get("kind") == "journey":
                tiles = []
                for name, question, origin in JOURNEY:
                    current = " current" if index == 1 or post["title"].startswith(name) else ""
                    tiles.append(f"<div class='journey-tile{current}'><small>{origin} → {name}</small><h2>{question}</h2></div>")
                inner += "<div class='journey'>" + "".join(tiles) + "</div>"
            if slide.get("rows"):
                inner += "<div class='rows'>" + "".join(
                    f"<div class='row'><span class='number'>{n:02}</span><div><h2 contenteditable='true'>{title}</h2><p contenteditable='true'>{body}</p></div></div>"
                    for n, (title, body) in enumerate(slide["rows"], 1)
                ) + "</div>"
            if slide.get("callout"):
                inner += f"<div class='callout' contenteditable='true'>{slide['callout']}</div>"
            art.append(f"<article class='art draft-art' id='{filename}' data-export='{filename}'><div class='brand'><img src='placeos-logo-transparent.png' alt='PlaceOS'><span class='series'>入점 노트 / {index:02}</span></div>{inner}<div class='foot'><strong contenteditable='true'>{slide['footer']}</strong><span>{number:02} / 03</span></div></article>".replace("入점", "입점"))
            text = plain(slide["heading"])
            if slide.get("intro"):
                text += "\n" + plain(slide["intro"])
            for title, body in slide.get("rows", []):
                text += f"\n{title}: {body}"
            if slide.get("callout"):
                text += "\n" + plain(slide["callout"])
            captions.extend([f"**{number}장 — `{filename}.png`**", text.replace("\n", "\\\n"), f"대체 텍스트: PlaceOS. {text.replace(chr(10), ' ')}"])
            links.append(f"<a href='{filename}.png'><img src='{filename}.png' alt='{html.escape(plain(slide['heading']))}'></a>")
        captions.extend(["### 내부 근거·검토 메모", f"출처 상태: {post['status']}", " · ".join(post["sources"]), post["review"]])
        preview.append(f"<section><h2>{index:02} · {post['title']}</h2><div class='thumbnails'>{''.join(links)}</div></section>")
    document = "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>PlaceOS 게시물 초안 5편</title><link rel='stylesheet' href='templates.css'><link rel='stylesheet' href='drafts.css'></head><body><div class='toolbar'>초안 · 문구 클릭 편집 · 편집 내용은 자동 저장되지 않습니다. 영구 변경은 content.json에 반영하고 재생성하세요.</div><main class='gallery'>" + "".join(art) + "</main></body></html>"
    (ROOT / "series.html").write_text(document, encoding="utf-8")
    (ROOT / "captions.md").write_text("\n\n".join(captions) + "\n", encoding="utf-8")
    (ROOT / "preview.html").write_text("<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>PlaceOS 5편 미리보기</title><style>body{margin:0;padding:32px;background:#DDE4E5;color:#1C2533;font-family:'Malgun Gothic',sans-serif}h1{font-size:28px}h2{font-size:20px;margin:24px 0 12px}.thumbnails{display:flex;gap:16px}.thumbnails img{display:block;width:260px;height:325px;border-radius:6px}a{color:#087E8E}</style></head><body><h1>PlaceOS 게시물 초안 · 5편 × 3장</h1><p><a href='series.html'>편집 원본</a> · <a href='captions.md'>캡션·대체 텍스트·근거 메모</a></p>" + "".join(preview) + "</body></html>", encoding="utf-8")


def draft_render_check() -> dict:
    checked = []
    with sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page(viewport={"width": 1250, "height": 1600}, device_scale_factor=1)
        page.goto((ROOT / "series.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        for art in page.locator(".art").all():
            filename = art.get_attribute("data-export")
            errors = art.evaluate("""e => {
                const errors = [];
                const frame = e.getBoundingClientRect();
                const footer = e.querySelector('.foot').getBoundingClientRect();
                for (const child of e.children) {
                    if (child.classList.contains('foot')) continue;
                    if (child.getBoundingClientRect().bottom > footer.top - 18) errors.push('하단 문구 겹침: '+child.className);
                }
                const walker = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
                let node;
                while (node = walker.nextNode()) {
                    if (!node.textContent.trim()) continue;
                    const range = document.createRange(); range.selectNodeContents(node);
                    for (const r of range.getClientRects()) {
                        if (r.left < frame.left + 50 || r.right > frame.right - 50 || r.bottom > frame.bottom - 45) errors.push('문구 안전 영역 이탈: '+node.textContent);
                    }
                }
                return errors;
            }""")
            assert not errors, f"{filename}: {errors}"
            art.screenshot(path=str(ROOT / f"{filename}.png"), animations="disabled")
            with Image.open(ROOT / f"{filename}.png") as image:
                assert image.size == (1080, 1350)
            checked.append(filename)
        assert len(checked) == 15
        page.set_viewport_size({"width": 900, "height": 2000})
        page.goto((ROOT / "preview.html").as_uri())
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        page.screenshot(path=str(ROOT / "preview.png"), full_page=True)
        browser.close()
    return {"result": "PASS", "png_count": len(checked), "size": [1080, 1350], "files": checked}


def main() -> None:
    posts = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
    content_result = draft_content_check(posts)
    make_html(posts)
    render_result = draft_render_check()
    results = {"draft_content_check": content_result, "draft_render_check": render_result}
    (ROOT / "verification.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
