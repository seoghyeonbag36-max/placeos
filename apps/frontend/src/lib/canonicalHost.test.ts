import { describe, expect, it } from "vitest";
import { CANONICAL_ORIGIN, NON_CANONICAL_HOSTS, canonicalRedirect } from "@/lib/canonicalHost";
// 번들 앞 스크립트와 HTML 페이지 — 번들 밖 정적 파일이라 글자로 읽는다
import earlyScript from "../../public/canonical-host.js?raw";
import indexHtml from "../../index.html?raw";

const at = (hostname: string, pathname = "/", search = "", hash = "") => ({ hostname, pathname, search, hash });

/** public/canonical-host.js 를 가짜 location 으로 돌려 옮길 곳을 받는다(안 옮기면 null) */
function runEarly(hostname: string, pathname = "/", search = "", hash = ""): string | null {
  const moved: string[] = [];
  const location = { hostname, pathname, search, hash, replace: (url: string) => { moved.push(url); } };
  new Function("location", earlyScript)(location);
  return moved[0] ?? null;
}

describe("canonicalRedirect — 정식 주소 placeos.co.kr 으로 보내기", () => {
  it("옛 사이트와 firebaseapp.com 주소는 경로·쿼리·해시를 붙여 정식 주소로 보낸다", () => {
    expect(canonicalRedirect(at("spaceos-twin.web.app", "/", "?a=1", "#board"))).toBe("https://placeos.co.kr/?a=1#board");
    expect(canonicalRedirect(at("placeos.firebaseapp.com", "/", "", "#admin"))).toBe("https://placeos.co.kr/#admin");
    expect(canonicalRedirect(at("spaceos-twin.firebaseapp.com"))).toBe("https://placeos.co.kr/");
    expect(canonicalRedirect(at("placeos.web.app", "/privacy.html", "?a=1", "#board"))).toBe("https://placeos.co.kr/privacy.html?a=1#board");
    expect(canonicalRedirect(at("www.placeos.co.kr"))).toBe("https://placeos.co.kr/");
  });

  it("끝에 점이 붙은 이름도 옮긴다 — 정식 주소에 점이 붙은 경우는 점 없는 주소로(2026-11-01 검증)", () => {
    expect(canonicalRedirect(at("placeos.web.app.", "/", "?x=1", "#/home"))).toBe("https://placeos.co.kr/?x=1#/home");
    expect(canonicalRedirect(at("placeos.firebaseapp.com.", "/privacy.html"))).toBe("https://placeos.co.kr/privacy.html");
    expect(canonicalRedirect(at("placeos.co.kr.", "/", "", "#/home"))).toBe("https://placeos.co.kr/#/home");
  });

  it("정식 주소·로컬 개발·Cloud Run 원본 주소는 건드리지 않는다", () => {
    expect(canonicalRedirect(at("placeos.co.kr"))).toBeNull();
    expect(canonicalRedirect(at("localhost"))).toBeNull();
    expect(canonicalRedirect(at("spaceos-798830962560.us-central1.run.app"))).toBeNull();
  });
});

describe("번들 앞 스크립트 public/canonical-host.js — 정적 페이지와 번들 받기 전을 맡는다", () => {
  it("목록과 정식 주소가 번들(canonicalHost.ts)과 같다", () => {
    const list = earlyScript.match(/var HOSTS = \[([^\]]*)\]/)?.[1] ?? "";
    expect([...list.matchAll(/"([^"]+)"/g)].map((m) => m[1]).sort()).toEqual([...NON_CANONICAL_HOSTS].sort());
    expect(earlyScript).toContain(`var CANONICAL = "${CANONICAL_ORIGIN}";`);
    expect(earlyScript).toContain(`var CANONICAL_HOST = "${new URL(CANONICAL_ORIGIN).hostname}";`);
  });

  it("번들과 같은 곳으로 옮긴다 — 목록의 호스트 전부 · 끝 점 · 옮기지 않을 곳", () => {
    const cases: [string, string, string, string][] = [];
    for (const h of NON_CANONICAL_HOSTS) {
      cases.push([h, "/privacy.html", "?a=1", "#board"], [`${h}.`, "/", "", "#/home"]);
    }
    cases.push(["placeos.co.kr.", "/", "?x=1", "#/home"], ["placeos.co.kr", "/", "", ""], ["localhost", "/", "", ""],
      ["spaceos-798830962560.us-central1.run.app", "/", "", ""]);
    for (const [h, p, s, x] of cases) expect(runEarly(h, p, s, x), h).toBe(canonicalRedirect(at(h, p, s, x)));
    expect(runEarly("placeos.web.app")).toBe("https://placeos.co.kr/");
    expect(runEarly("placeos.co.kr")).toBeNull();
  });

  it("HTML 페이지는 모두 이 스크립트를 async 로 싣는다 — index.html · public/*.html(새 정적 페이지가 빠지면 운다)", () => {
    const pages: Record<string, string> = {
      "index.html": indexHtml,
      ...import.meta.glob<string>("../../public/*.html", { query: "?raw", import: "default", eager: true }),
    };
    expect(Object.keys(pages).length).toBeGreaterThanOrEqual(3);
    for (const [name, html] of Object.entries(pages)) {
      expect(html, name).toContain('<script src="/canonical-host.js" async></script>');
    }
  });
});
