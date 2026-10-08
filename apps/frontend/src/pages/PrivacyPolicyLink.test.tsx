/**
 * 개인정보 처리방침 링크 — 2026-10-08. docs/runbook-custom-domain-placeos-kr-2026-10-08.md §5.
 *
 * 구글 OAuth 앱 게시는 「홈페이지에서 처리방침으로 가는 링크」를 요구한다. 그 링크가 조용히 사라지면
 * 콘솔에서 게시 버튼이 다시 막히는데, 그 사실을 코드 쪽에서는 알 길이 없다.
 *
 * 잡는 회귀:
 *   - 첫 화면(Home)에서 처리방침 링크가 빠지는 것
 *   - 가입·로그인 안내문에서 전문으로 가는 링크가 빠지거나 현재 탭을 덮어쓰는 것(작성하던 폼이 날아간다)
 *   - 링크가 상대경로가 아니게 되는 것 — 도메인을 옮길 때마다 깨진다
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/pages/Home";
import PrivacyNote from "@/components/PrivacyNote";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import { installFetchStub } from "@/test/fetchStub";

describe("처리방침 링크", () => {
  it("주소는 도메인에 묶이지 않은 상대경로다", () => {
    expect(PRIVACY_POLICY_PATH).toBe("/privacy.html");
  });

  it("첫 화면에 새 창으로 열리는 처리방침 링크가 있다", () => {
    installFetchStub([]);
    render(<Home />);
    const links = screen.getAllByRole("link", { name: /개인정보 처리방침/ });
    expect(links.length).toBeGreaterThanOrEqual(1);
    for (const a of links) {
      expect(a.getAttribute("href")).toBe(PRIVACY_POLICY_PATH);
      expect(a.getAttribute("target")).toBe("_blank");
      expect(a.getAttribute("rel")).toContain("noopener");
    }
  });

  it("수집 안내문 끝에 전문 링크가 붙는다", () => {
    render(<PrivacyNote />);
    const a = screen.getByRole("link", { name: /처리방침 전문/ });
    expect(a.getAttribute("href")).toBe(PRIVACY_POLICY_PATH);
    expect(a.getAttribute("target")).toBe("_blank");
  });
});
