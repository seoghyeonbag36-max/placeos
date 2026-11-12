"""리뉴얼 Page→Posting→Program 실제 로컬 API·브라우저 검사. 유료 AI 생성은 호출하지 않는다."""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:5173")
    ap.add_argument("--out", type=Path, default=Path("reports/renewal"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    base = args.base.rstrip("/")
    with urlopen(base + "/api/v1/commercial-districts/garosugil/floor-vacancies?limit=5") as response:
        floor = json.load(response)["units"][0]
    checks: dict[str, object] = {}
    errors: list[str] = []
    images: list[tuple[str, Path]] = []

    def shot(page, name: str) -> None:
        path = args.out / f"{name}.png"
        page.screenshot(path=str(path), full_page=True)
        images.append((name, path))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--enable-webgl", "--use-gl=angle", "--use-angle=swiftshader"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
        flow = {"v": 1, "goal": "start", "industryKey": "cafe", "districtId": "garosugil"}
        ctx.add_init_script(f"localStorage.setItem('placeos.flow.v1', {json.dumps(json.dumps(flow))}); localStorage.setItem('placeos.business.v1', JSON.stringify({{status:'browsing'}}));")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + f"/#/explore?track=page&district=garosugil&building={floor['building_id']}")
        page.get_by_role("button", name="3D 트윈으로 보기", exact=True).click(timeout=60000)
        dialog = page.get_by_role("dialog", name="3D 트윈", exact=False)
        dialog.wait_for()
        page.locator(".twin3d-floor h3").wait_for(timeout=60000)
        page.wait_for_function("document.querySelector('.twin3d-canvas[data-ready=\"1\"]') || document.querySelector('.twin3d-flat')")
        checks["3D ready"] = page.locator('.twin3d-canvas[data-ready="1"]').count() == 1
        checks["층 id"] = floor["id"]
        page.get_by_role("group", name="층 이동").get_by_role("button", name=f"{floor['floor_label']} 공실확정", exact=True).click()
        if checks["3D ready"]:
            page.get_by_role("button", name="층 분리", exact=True).click()
        shot(page, "02-page-desktop")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        shot(page, "02-page-mobile")
        assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        checks["모바일 트윈 가로 넘침 없음"] = True
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("button", name="이 자리로 입점 계산 → Posting", exact=True).click()
        panel = page.get_by_role("complementary", name="입점 계산", exact=True)
        panel.get_by_role("button", name="시뮬레이션", exact=True).wait_for()
        page.wait_for_function("id => document.querySelectorAll('.postconsole select')[1]?.value === id", arg=floor["id"], timeout=60000)
        selected = page.locator(".postconsole select").nth(1).input_value()
        assert selected == floor["id"], (selected, floor["id"])
        checks["선택한 층 보존"] = True
        page.get_by_placeholder("계약서·도면으로 확인한 면적").fill("40")
        with page.expect_response(lambda r: "/ai/simulate-revenue" in r.url and r.request.method == "POST"
                                  and r.request.post_data_json.get("area_py_override") == 40) as pending:
            page.get_by_role("button", name="시뮬레이션", exact=True).click()
        result = pending.value.json()
        assert result["unit_id"] == floor["id"] and result["inputs_source"]["area"] == "user_input"
        assert result["resolved_inputs"]["area_py"] == 40
        checks["면적 사용자 입력 출처"] = result["inputs_source"]["area"]
        checks["계산에 사용한 임대료(만원)"] = result["resolved_inputs"]["rent_manwon"]
        page.get_by_text("면적으로 운영 규모 잡기 · BEP 계산", exact=True).click()
        for label, value in [("영업에 사용할 면적 비율", "70"), ("좌석·설비 1개당 필요 면적", "1.2"),
                             ("월 기타 고정비", "300"), ("매출 대비 변동비율", "35"),
                             ("판매 1건당 평균 금액", "7000"), ("월 영업일", "26"), ("좌석·설비당 하루 판매 가능 건수", "5")]:
            page.get_by_role("spinbutton", name=label, exact=True).fill(value)
        page.get_by_role("region", name="면적별 BEP 결과").wait_for()
        checks["BEP 입력 계산"] = True
        shot(page, "03-posting-desktop")
        # 2026-11-10 — 검증 program 버튼은 Posting 오른쪽 칸 「비용 비교 및 결정」 쪽 안에 있다
        page.get_by_role("button", name="비용 비교 및 결정", exact=True).click()
        page.get_by_role("button", name="이 자리로 검증 program 만들기 →", exact=True).click()
        page.get_by_role("heading", name="오프라인 캠페인", exact=True).wait_for()
        page.get_by_role("heading", name="인테리어 참고안", exact=True).wait_for()
        page.get_by_placeholder("예: 카페", exact=True).wait_for()
        checks["기존 캠페인+검증 브리프+인테리어 동시 보존"] = True
        interior = page.get_by_role("region", name="인테리어 참고안", exact=True)
        interior.scroll_into_view_if_needed()
        interior.get_by_role("button", name="따뜻함", exact=True).click()
        assert interior.get_by_role("button", name="AI 참고 이미지 생성", exact=True).is_disabled()
        checks["전송 동의 전 이미지 호출 차단"] = True
        assert "40평" in page.locator(".arrival").inner_text()
        checks["Program 면적 인계"] = "40평"
        shot(page, "04-program-desktop")
        page.set_viewport_size({"width": 390, "height": 844})
        interior.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        checks["모바일 문서 가로 넘침 없음"] = not overflow
        assert not overflow
        shot(page, "04-program-mobile")
        checks["page errors"] = errors
        checks["네이버 지도 SDK"] = page.evaluate("Boolean(window.naver?.maps?.Map)")
        assert not errors, errors
        browser.close()
    (args.out / "result.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in checks.items())
    figures = "".join(f"<figure><img src='data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}' alt='{name}'><figcaption>{name}</figcaption></figure>" for name, p in images)
    (args.out / "02-04-renewal.html").write_text("<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Page·Posting·Program 검증</title><style>body{font:16px/1.6 system-ui;max-width:1200px;margin:30px auto;padding:20px}table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:8px;text-align:left}img{max-width:100%}figure{margin:24px 0}</style><h1>Page·Posting·Program 리뉴얼 검증</h1><p>실제 로컬 API·Gold·브라우저로 확인. BEP 운영값과 내부면적 40평은 검증용 사용자 입력이며 실측값이 아닙니다. AI 유료 생성은 호출하지 않았습니다.</p><table>" + rows + "</table>" + figures + "<h2>남은 외부 조건</h2><p>차량·대중교통·벤치마킹 API 키, AI 이미지 활성화·키·모델 권한과 실제 생성 결과는 운영 환경에서 별도 확인해야 합니다. 스냅샷 공실은 실시간 현장 확인이 아닙니다.</p></html>", encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
