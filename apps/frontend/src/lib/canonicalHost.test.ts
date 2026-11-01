import { describe, expect, it } from "vitest";
import { canonicalRedirect } from "@/lib/canonicalHost";

const at = (hostname: string, pathname = "/", search = "", hash = "") => ({ hostname, pathname, search, hash });

describe("canonicalRedirect — 정식 주소 placeos.co.kr 으로 보내기", () => {
  it("옛 사이트와 firebaseapp.com 주소는 경로·쿼리·해시를 붙여 정식 주소로 보낸다", () => {
    expect(canonicalRedirect(at("spaceos-twin.web.app", "/", "?a=1", "#board"))).toBe("https://placeos.co.kr/?a=1#board");
    expect(canonicalRedirect(at("placeos.firebaseapp.com", "/", "", "#admin"))).toBe("https://placeos.co.kr/#admin");
    expect(canonicalRedirect(at("spaceos-twin.firebaseapp.com"))).toBe("https://placeos.co.kr/");
    expect(canonicalRedirect(at("placeos.web.app", "/privacy.html", "?a=1", "#board"))).toBe("https://placeos.co.kr/privacy.html?a=1#board");
    expect(canonicalRedirect(at("www.placeos.co.kr"))).toBe("https://placeos.co.kr/");
  });

  it("정식 주소·로컬 개발·Cloud Run 원본 주소는 건드리지 않는다", () => {
    expect(canonicalRedirect(at("placeos.co.kr"))).toBeNull();
    expect(canonicalRedirect(at("localhost"))).toBeNull();
    expect(canonicalRedirect(at("spaceos-798830962560.us-central1.run.app"))).toBeNull();
  });
});
