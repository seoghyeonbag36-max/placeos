#!/usr/bin/env python
"""PPPP 화면 보존 규칙의 실화면 검사 — jsdom 가드가 원리상 못 보는 것을 실제 브라우저로 잰다.

## 왜 필요한가

2026-10-21 사용자 확정 규칙: 「Platform/Page/Posting/Program 의 구현 화면은 절대 화면에서 제외하지 않는다」
(루트 CLAUDE.md 「PPPP 화면 보존 규칙」 · docs/decision-pppp-screens-always-on-2026-10-21.md).

가드 테스트 `apps/frontend/src/ppppScreens.test.tsx` 는 CI 에서 돌고 빨개지면 배포를 막는다. 그런데 jsdom 이라
두 가지는 원리상 못 본다:

  1. **CSS 파일로 숨김** — jsdom 은 CSS 파일을 읽지 않는다. 레일 버튼을 `display:none` 으로 감춰도 초록이다.
  2. **브라우저가 낸 이벤트의 순서** — 탭의 `<a href>` · 주소창 · 뒤로가기가 낸 hashchange 는 리스너 사이마다
     렌더가 낀다. 10-21 에 바로 이것 때문에, 흐름을 주소로 바로 열면 허브 탭 「지도」가 #/explore → #/home 으로
     튕겼다 — 그때 테스트 341건은 전부 초록이었다.

⚠ 같은 페이지에서 해시만 바꿔 옮겨 다니면 그 튕김이 가려진다(흐름 앱이 나중에 다시 마운트되기 때문). 그래서 진입로
검사는 매번 **새 페이지로 주소를 바로 연 뒤** 누른다(10-21 에 한 번 그렇게 놓쳤다).

## 무엇을 재는가

  P1  #/explore 를 바로 열면(로그인 없이) 레일에 Platform·Page·Posting·Program 넷이 PPPP 순서로 **보인다**
  P2  네 버튼이 각자 자기 화면을 연다 — 「상권 정체성」 · 「지도 데이터 레이어」 · 「입점 계산」 · 「오프라인 캠페인」이 **보인다**
  P3  흐름의 「지도」 진입로 — 허브 탭(데스크톱 상단 · 휴대폰 하단) · 상권 소개 「지도에서 자세히」 · 빈 자리 목록 「지도」
      — 을 누르고 2.5초 뒤에도 #/explore 에 머물며 레일 넷이 보인다
  P4  지도 탐색이 흐름에서 고른 상권으로 열린다(설계서 5판 §10 C2) — Platform · Page 의 상권 선택 값
  P5  랜딩의 PPPP 네 질문(#how)이 접히지 않고 보인다
  (기록만) 콘솔 에러 · API 5xx — 지도 키(.env)가 없는 로컬에서는 지도 칸이 「지도를 불러오지 못했습니다」로 선다.
  그건 이 규칙과 무관하다(지도 SDK 는 레일·패널을 가리지 않는다).

## 실행 — 백엔드·프론트를 먼저 띄운다(/verify 「띄우기」)

    # 터미널 1  cd apps\\backend ; py -3.11 -m uvicorn app.main:app --port 8000
    # 터미널 2  cd apps\\frontend ; npm run dev
    set PYTHONIOENCODING=utf-8
    py -3.11 scripts/pppp_screens_check.py                         # 첫 gold 상권으로
    py -3.11 scripts/pppp_screens_check.py --district bulgwang --screens

종료코드 0 = 전부 통과, 1 = 하나라도 실패. 결과는 `reports/pppp_screens/result.json`(+ `--screens` 면 PNG) — git 밖이다.
흐름 · App.tsx · 랜딩 · 레일을 건드린 변경은 /verify 에서 이 검사를 돌린다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW_KEY = "placeos.flow.v1"
TRACKS = ["Platform", "Page", "Posting", "Program"]
# 레일 버튼 → 그 화면이 섰다는 표지(역할 · 접근성 이름). Page(MapShell)만 TrackMapFrame 패널이 아니라 레이어 묶음이다
PANELS = [("Platform", "complementary", "상권 정체성"), ("Page", "group", "지도 데이터 레이어"),
          ("Posting", "complementary", "입점 계산"), ("Program", "complementary", "오프라인 캠페인")]
SETTLE_MS = 2500


def wait_http(url: str, timeout: int = 180) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if r.status < 500:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit(f"응답 없음: {url} — 백엔드·프론트를 먼저 띄운다(이 파일 머리말 「실행」)")


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, cid: str, ok: bool, detail) -> None:
        self.checks.append({"id": cid, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {cid}  {json.dumps(detail, ensure_ascii=False)}", flush=True)

    @property
    def failed(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


def rail(page) -> list[list]:
    """레일 트랙 버튼 — [라벨, 보이는가]"""
    btns = page.locator("nav button[data-track]")
    return [[b.inner_text().strip(), b.is_visible()] for b in btns.all()]


def rail_ok(state: list[list]) -> bool:
    return [name for name, _ in state] == TRACKS and all(vis for _, vis in state)


def settled(page) -> dict:
    """누른 뒤 SETTLE_MS 기다려도 #/explore 에 머물며 레일 넷이 보이는가 — 10-21 #/explore → #/home 되감기를 잡은 자리"""
    page.wait_for_timeout(SETTLE_MS)
    return {"hash": page.evaluate("() => location.hash"), "rail": rail(page)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="http://localhost:5173", help="프론트(Vite) 주소 — /api 는 그 프록시를 탄다")
    ap.add_argument("--district", default=None, help="흐름에서 고른 상권 id(기본: 첫 gold 상권)")
    ap.add_argument("--out", default=str(ROOT / "reports" / "pppp_screens"))
    ap.add_argument("--screens", action="store_true", help="화면마다 PNG 를 남긴다")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from playwright.sync_api import sync_playwright  # 설치 확인을 실행 시점으로 미룬다

    base = args.base.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wait_http(base + "/")
    wait_http(base + "/api/v1/commercial-districts")
    gold = [d for d in get_json(base + "/api/v1/commercial-districts") if d.get("vacancy_source") == "gold"]
    if not gold:
        raise SystemExit("gold 상권이 없다 — 백엔드가 Gold 산출물을 읽는지부터 본다")
    target = next((d for d in gold if d["id"] == args.district), None) if args.district else gold[0]
    if target is None:
        raise SystemExit(f"--district {args.district} 는 gold 상권이 아니다")
    industries = get_json(base + "/api/v1/ai/industries").get("industries", [])
    industry = next((i for i in industries if i.get("model_label")), industries[0] if industries else None)
    flow = {"v": 1, "goal": "start", "industryKey": industry["key"] if industry else None, "districtId": target["id"]}
    seed = f"localStorage.setItem('{FLOW_KEY}', {json.dumps(json.dumps(flow))})"

    rep = Report()
    errors: list[str] = []
    bad_api: list[str] = []

    def watch(page, tag: str):
        page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"[{tag}] console.error: {m.text}") if m.type == "error" else None)
        page.on("response", lambda r: bad_api.append(f"[{tag}] {r.status} {r.url}") if "/api/" in r.url and r.status >= 500 else None)
        return page

    def shot(page, name: str) -> None:
        if args.screens:
            page.screenshot(path=str(out / f"{name}.png"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        desk = dict(viewport={"width": 1440, "height": 900}, locale="ko-KR")
        clean = browser.new_context(**desk)                      # 흐름 답 없음 — 랜딩 · 로그인 없이 바로 연 지도 탐색
        flowctx = browser.new_context(**desk)                    # 흐름 답(상권·업종)을 심은 데스크톱
        flowctx.add_init_script(seed)
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR", is_mobile=True, has_touch=True)
        mobile.add_init_script(seed)

        # P1 · P2 — 로그인 없이 #/explore 를 바로 연다
        pg = watch(clean.new_page(), "explore")
        pg.goto(base + "/#/explore")
        pg.locator("nav button[data-track]").first.wait_for(timeout=60000)
        state = rail(pg)
        rep.add("P1 레일 네 트랙 · PPPP 순서 · 보임", rail_ok(state), state)
        for name, role, label in PANELS:
            pg.get_by_role("button", name=name, exact=True).click()
            try:
                pg.get_by_role(role, name=label).first.wait_for(state="visible", timeout=60000)
                ok = True
            except Exception:
                ok = False
            current = pg.get_by_role("button", name=name, exact=True).get_attribute("aria-current")
            rep.add(f"P2 {name} → 「{label}」", ok and current == "page", {"visible": ok, "aria-current": current})
            shot(pg, f"p2-{name.lower()}")
        pg.close()

        # P3 — 흐름의 진입로. 매번 새 페이지로 주소를 바로 연다(같은 페이지에서 옮기면 튕김이 가려진다)
        def entry(ctx, cid: str, start_hash: str, press) -> None:
            page = watch(ctx.new_page(), cid)
            page.goto(base + "/" + start_hash)
            try:
                press(page)
                st = settled(page)
                rep.add(cid, st["hash"] == "#/explore" and rail_ok(st["rail"]), st)
            except Exception as e:  # 버튼을 못 찾는 것도 실패다
                rep.add(cid, False, {"error": str(e).splitlines()[0][:200]})
            shot(page, cid.split()[0].lower())
            page.close()

        def hub_desktop(page):
            tab = page.locator(".fl-tabs-top").get_by_role("link", name="지도", exact=True)
            tab.wait_for(state="visible", timeout=60000)
            page.wait_for_timeout(800)
            tab.click()

        def hub_mobile(page):
            tab = page.locator(".fl-tabbar").get_by_role("link", name="지도", exact=True)
            tab.wait_for(state="visible", timeout=60000)
            page.wait_for_timeout(800)
            tab.tap()

        def district_more(page):
            btn = page.get_by_role("button", name="지도에서 자세히", exact=True)
            btn.wait_for(state="visible", timeout=60000)
            btn.click()

        def spaces_map(page):
            page.locator("h1.fl-title").filter(has_text="빈 자리").first.wait_for(timeout=60000)
            btn = page.get_by_role("button", name="지도", exact=True)
            btn.wait_for(state="visible", timeout=60000)
            btn.click()

        entry(flowctx, "P3a 허브 탭 「지도」(데스크톱 · #/home 바로 열기)", "#/home", hub_desktop)
        entry(mobile, "P3b 허브 탭 「지도」(휴대폰 · #/home 바로 열기)", "#/home", hub_mobile)
        entry(flowctx, f"P3c 상권 소개 「지도에서 자세히」(#/district/{target['id']})", f"#/district/{target['id']}", district_more)
        entry(flowctx, "P3d 빈 자리 목록 「지도」(#/spaces)", "#/spaces", spaces_map)

        # P4 — 흐름의 상권으로 열리는가(C2)
        pg = watch(flowctx.new_page(), "c2")
        pg.goto(base + "/#/explore")
        pg.get_by_role("complementary", name="상권 정체성").wait_for(timeout=60000)
        pg.wait_for_timeout(2000)
        sel = pg.locator("aside[aria-label='상권 정체성'] select").first
        platform_value = sel.input_value() if sel.count() else None
        pg.get_by_role("button", name="Page", exact=True).click()
        pg.get_by_role("group", name="지도 데이터 레이어").wait_for(timeout=60000)
        pg.wait_for_timeout(2000)
        hub = pg.locator("select.hub-select").first
        page_value = hub.input_value() if hub.count() else None
        rep.add("P4 흐름 상권으로 연다(Platform · Page)", platform_value == target["id"] and page_value == target["id"],
                {"expected": target["id"], "platform": platform_value, "page": page_value})
        pg.close()

        # P5 — 랜딩의 네 질문
        pg = watch(clean.new_page(), "landing")
        pg.goto(base + "/")
        pg.locator("#how").wait_for(timeout=60000)
        steps = pg.locator("#how li[data-track]")
        tracks = [steps.nth(i).get_attribute("data-track") for i in range(steps.count())]
        visible = [steps.nth(i).is_visible() for i in range(steps.count())]
        closed = pg.evaluate("() => [...document.querySelectorAll('#how li[data-track]')].filter(li => li.closest('details:not([open])')).length")
        rep.add("P5 랜딩 네 질문이 펼쳐져 보임", tracks == ["platform", "page", "posting", "program"] and all(visible) and closed == 0,
                {"tracks": tracks, "visible": visible, "in_closed_details": closed})
        if args.screens:
            pg.locator("#how").screenshot(path=str(out / "p5-landing-how.png"))
        pg.close()
        browser.close()

    result = {
        "district": target["id"], "industry": industry["key"] if industry else None,
        "passed": len(rep.checks) - len(rep.failed), "failed": len(rep.failed),
        "checks": rep.checks, "console_errors": errors, "api_5xx": bad_api,
    }
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{result['passed']} 통과 · {result['failed']} 실패 · 콘솔 에러 {len(errors)} · API 5xx {len(bad_api)} → {out / 'result.json'}")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
