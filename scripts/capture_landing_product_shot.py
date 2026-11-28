"""랜딩 첫 화면의 제품 그림(apps/frontend/src/design/assets/product-floor-stack.png)을 다시 찍는다 (2026-11-28).

왜 있나. 랜딩의 그림은 **실제 화면의 캡처**다 — 빈 자리 상세(#/space/…)의 「이 건물의 층」(월세 줄 · 추정 안내 · 층 그림 · 범례).
화면이 바뀌면 그림이 낡아 거짓 광고가 되므로, 층 그림·월세 줄·안내문을 건드린 PR 은 이 스크립트로 다시 찍는다.

지켜야 할 것
  - 건물이 특정되면 안 된다 — 제목(지번 주소)·상권 이름·지도는 **잘라낸다**(월세 줄부터 범례까지만 찍는다).
  - 값을 지어내지 않는다 — 로컬 백엔드가 읽는 Gold 의 실제 빈 자리다. 합성 건물을 만들어 찍지 않는다.
  - 네이버 지도·거리뷰는 찍지 않는다(재게시 제약) — 우리가 그린 층 그림만 쓴다.
  - 캡션(「실제 화면입니다. 건물 정보는 가렸고, 월세는 호가가 아닌 추정입니다」)과 alt 의 층 설명을 그림과 맞춘다.

쓰는 법 (백엔드 :8000 + 프런트 :5173 을 먼저 띄운다 — 로컬 실화면은 5173 만 네이버가 허용한다)
  py -3.11 -I scripts/capture_landing_product_shot.py                     # 기본: 불광 5층 건물 3층
  py -3.11 -I scripts/capture_landing_product_shot.py --district garosugil --space vfu-1168010800100060013-1
  후보 고르기: floor-vacancies 응답에서 층수 5~8 · 영업 중 층이 있고 빈 층이 둘 이상인 건물이 설명이 된다.

결과: 750 x ~734 PNG(약 40KB). 찍은 뒤 alt·캡션의 층 설명(빈 층·영업 중·상가 아님)이 그림과 맞는지 눈으로 확인한다.
"""
import argparse
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

FLOW_KEY = "placeos.flow.v1"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "apps/frontend/src/design/assets/product-floor-stack.png"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5173")
    ap.add_argument("--district", default="bulgwang")
    ap.add_argument("--space", default="vfu-1138010200101090020-3")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    def get(path: str):
        with urllib.request.urlopen(args.base + path, timeout=90) as r:
            return json.loads(r.read().decode("utf-8"))

    industries = get("/api/v1/ai/industries").get("industries", [])
    industry = next((i for i in industries if i.get("model_label")), industries[0])
    units = get(f"/api/v1/commercial-districts/{args.district}/floor-vacancies?limit=50")
    units = units if isinstance(units, list) else units.get("units") or units.get("items") or []
    item = next((u for u in units if u["id"] == args.space), None)
    if item is None:
        raise SystemExit(f"{args.space} 는 {args.district} 의 빈 자리 목록에 없다 — 자료가 새로 들어오며 빠졌을 수 있다")
    flow = {"v": 1, "goal": "start", "industryKey": industry["key"], "districtId": args.district, "spaceId": item["id"],
            "spaceLabel": item.get("floor_label") or "",
            "spaceAt": {"buildingId": item["building_id"], "name": "", "lat": item["lat"], "lng": item["lng"]}}

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--hide-scrollbars"])
        # 높이 1000 — 하단 고정 버튼(저장 · 본전 보기)이 잘라낼 영역 아래에 놓이게 한다
        ctx = b.new_context(viewport={"width": 390, "height": 1000}, device_scale_factor=2)
        ctx.add_init_script(f"localStorage.setItem('{FLOW_KEY}', {json.dumps(json.dumps(flow))})")
        pg = ctx.new_page()
        pg.goto(f"{args.base}/#/space/{args.space}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector(".fl-stack.is-big", timeout=45000)
        pg.wait_for_timeout(3000)
        r = pg.evaluate("""() => {
          const k = document.querySelector('.fl-keys').getBoundingClientRect();
          const s = document.querySelector('.fl-stack-row').getBoundingClientRect();
          return {keysTop: k.top + scrollY, stackBottom: s.bottom + scrollY};
        }""")
        # 위: 지도 블록 가장자리(월세 줄 위 약 12px)가 찍히지 않게 6px 만 남긴다 · 폭 375: 앱 칼럼 오른쪽 15px 는 칼럼 밖 배경이다
        y0 = max(0, r["keysTop"] - 6)
        y1 = r["stackBottom"] + 20
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=args.out, clip={"x": 0, "y": y0, "width": 375, "height": y1 - y0})
        print("층 그림:", pg.locator(".fl-stack.is-big").first.get_attribute("aria-label"))
        print("저장:", args.out, f"({375 * 2} x {round((y1 - y0) * 2)})")
        b.close()


if __name__ == "__main__":
    main()
