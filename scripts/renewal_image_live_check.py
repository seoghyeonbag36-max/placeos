"""인테리어 UI→인증 API→이미지 공급자 실호출. --run 없이는 호출하지 않으며 최대 두 장을 만든다."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="실제 유료 생성 1회와 참고 이미지 편집 1회에 동의")
    args = ap.parse_args()
    if not args.run:
        ap.error("실호출에는 --run 이 필요합니다")
    out = Path("reports/renewal")
    out.mkdir(parents=True, exist_ok=True)
    base = "http://127.0.0.1:8002/api/v1"
    # 이 검사는 별도의 로컬 SQLite 서버에서만 실행한다. 운영 계정·DB를 사용하지 않는다.
    unique = secrets.token_hex(8)
    signup = httpx.post(base + "/auth/signup", json={"org_name": "이미지 실호출 검증 전용",
        "email": f"renewal-live-{unique}@example.org", "password": secrets.token_urlsafe(32)}, timeout=30)
    if signup.status_code != 201:
        print(json.dumps({"signup_status": signup.status_code, "passed": False}))
        return 1
    token = signup.json()["access_token"]
    report: dict = {"calls": [], "page_errors": [], "reference_source": "첫 번째 AI 생성 이미지를 두 번째 편집의 참고 사진으로 사용"}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--host-resolver-rules=MAP localhost 127.0.0.1"])
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
            context.add_init_script("localStorage.setItem('placeos.business.v1',JSON.stringify({status:'browsing'}));"
                                    + f"sessionStorage.setItem('placeos.session.v1',{json.dumps(token)});")
            page = context.new_page()
            page.on("pageerror", lambda _: report["page_errors"].append("browser page error"))
            page.goto("http://localhost:5173/#/explore?track=program&district=garosugil", timeout=60000)
            section = page.get_by_role("region", name="인테리어 참고안", exact=True)
            section.wait_for(timeout=60000)
            section.get_by_label("상권", exact=True).fill("가로수길 · 실호출 검증용 가상 실내")
            section.get_by_label("디자인할 업종", exact=True).fill("카페")
            section.get_by_label("분위기·색감", exact=True).fill("따뜻한 나무와 밝은 베이지, 미니멀")
            section.get_by_label("보존할 구조·운영 제약", exact=True).fill("검증용 가상 인테리어 콘셉트. 실제 매장·도면 아님. 문과 이동 공간을 분명히 표현.")
            section.get_by_role("checkbox").check()
            for stage in ["generation", "edit"]:
                if stage == "edit":
                    section.get_by_label("현장·디자인 참고 사진", exact=True).set_input_files(str(out / "live-interior-generation.png"))
                    section.get_by_label("분위기·색감", exact=True).fill("참고 이미지의 배치를 유지하고 회색과 초록의 깔끔한 분위기로 변경")
                    section.get_by_alt_text("사용자 제공 참고 사진", exact=True).wait_for()
                with page.expect_response(lambda r: "/ai/interior-preview" in r.url and r.request.method == "POST", timeout=240000) as pending:
                    section.get_by_role("button", name="AI 참고 이미지 생성", exact=True).click()
                response = pending.value
                entry = {"stage": stage, "http_status": response.status}
                report["calls"].append(entry)
                if response.status != 200:
                    report["passed"] = False
                    page.screenshot(path=str(out / "live-interior-error.png"))
                    break
                result = response.json()
                assert result["source"] == "ai_generated"
                raw = base64.b64decode(result["image_data_url"].split(",", 1)[1], validate=True)
                assert raw.startswith(b"\x89PNG\r\n\x1a\n")
                (out / f"live-interior-{stage}.png").write_bytes(raw)
                entry.update({"source": result["source"], "model": result["model"], "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()})
                section.get_by_alt_text("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님", exact=True).wait_for()
                section.locator(".interior-result").screenshot(path=str(out / f"live-interior-{stage}-ui.png"))
            else:
                report["passed"] = not report["page_errors"]
            browser.close()
    finally:
        # 로컬에서 만든 검증 전용 계정은 성공·실패와 무관하게 정리한다.
        deleted = httpx.delete(base + "/auth/me", headers={"Authorization": "Bearer " + token}, timeout=30)
        report["local_test_account_deleted"] = deleted.status_code in [200, 204]
        (out / "interior-image-live.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
