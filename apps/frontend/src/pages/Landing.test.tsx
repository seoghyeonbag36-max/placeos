/**
 * 랜딩 — 거짓 광고 방지 그물 (2026-10-08). pages/Landing.tsx 머리말의 규칙 네 개를 코드로 잠근다.
 *
 * 인스타·광고로 온 사람이 가장 먼저 읽는 글이라, 낡은 숫자나 지키지 못할 약속이 한 줄만 남아도 그날부터 거짓 광고다.
 * 문장을 고치는 것은 막지 않는다 — 막는 것은 **숫자·약속·표현이 슬그머니 늘어나는 것**이다.
 *
 * 잡는 회귀:
 *   - 문장에 거점 수를 직접 적어 두고 lib/landingFacts 와 어긋나는 것(그 상수가 서빙 거점 수와 맞는지는 백엔드 테스트가 본다)
 *   - 정확도·% · 고객 수 · 요금 같은 근거 없는 숫자가 들어오는 것
 *   - 「아직 못 하는 것」 절이 빠지는 것(시범 운영 단계에서 가장 믿을 만한 문장이다)
 *   - 금지 표현(AI 기반 · 혁신적인 · 원스톱 · 올인원 · 차세대 · 최적의 · 완벽한)
 *   - CTA 가 가입·로그인 해시로 가지 않는 것, 처리방침 링크가 빠지는 것
 */
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import Landing from "@/pages/Landing";
import { LANDING_HUBS } from "@/lib/landingFacts";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";

const text = () => document.body.textContent ?? "";

describe("랜딩 — 말하는 것", () => {
  it("첫 화면에서 무엇을 하는 서비스인지와 시작하는 길을 말한다", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { level: 1, name: /어느 건물 몇 층이 비었는지/ })).toBeTruthy();
    for (const a of screen.getAllByRole("link", { name: "시작하기" })) expect(a.getAttribute("href")).toBe("#signup");
    expect(screen.getByRole("link", { name: "로그인" }).getAttribute("href")).toBe("#login");
    expect(screen.getByRole("link", { name: "이미 계정이 있어요" }).getAttribute("href")).toBe("#login");
  });

  it("앱이 시작 카드에서 쓰는 세 가지 목적 문구를 그대로 쓴다(GOALS 가 단일 출처)", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { name: "새로 창업" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "지금 상권에서 업종 바꾸기" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "같은 업종으로 상권 옮기기" })).toBeTruthy();
  });

  it("네 질문이 PPPP 순서(Platform → Page → Posting → Program)로 이어진다", () => {
    render(<Landing />);
    const steps = within(document.getElementById("how")!).getAllByRole("listitem");
    expect(steps.map((li) => li.getAttribute("data-track"))).toEqual(["platform", "page", "posting", "program"]);
  });

  it("「아직 못 하는 것」 절이 있고, 공실 예측을 약속하지 않는다", () => {
    render(<Landing />);
    expect(screen.getByRole("heading", { name: "아직 못 하는 것" })).toBeTruthy();
    expect(text()).toContain("앞날을 맞힌다는 약속은 하지 않습니다");
  });

  it("영업 중인 가게 마케팅이 아니라는 것을 분명히 한다(Program 의 대상 — 2026-09-17)", () => {
    render(<Landing />);
    expect(text()).toContain("이미 영업 중인 가게의 홍보는 다루지 않습니다");
  });
});

describe("랜딩 — 말하지 않는 것", () => {
  it("숫자는 거점 수 하나뿐이다 — 정확도·고객 수·요금 같은 근거 없는 숫자가 없다", () => {
    render(<Landing />);
    // 단계 번호(1~4)와 거점 수 말고는 숫자가 없어야 한다. 새 숫자를 쓰려면 lib/landingFacts 에 출처와 함께 두고 여기 허용한다.
    const digits = (text().match(/\d[\d,.]*/g) ?? []).map((d) => d.replace(/[.,]$/, ""));
    const allowed = new Set([String(LANDING_HUBS), "1", "2", "3", "4"]);
    expect(digits.filter((d) => !allowed.has(d))).toEqual([]);
    expect(text()).toContain(`서울 ${LANDING_HUBS}개 상권`);
  });

  it("퍼센트·정확도·적중률을 쓰지 않는다(LSTM 두 축은 확인 대기, 업종 추천은 기준선 대비 +3.4%p 일 뿐이다)", () => {
    render(<Landing />);
    expect(text()).not.toMatch(/%|정확도|적중|맞힐 확률/);
  });

  it("금지 표현을 쓰지 않는다", () => {
    render(<Landing />);
    for (const word of ["AI 기반", "혁신적인", "원스톱", "올인원", "차세대", "최적의", "완벽한"]) {
      expect(text(), word).not.toContain(word);
    }
  });

  it("요금을 확정해 말하지 않는다 — 시범 운영 중 결제 없음까지만", () => {
    render(<Landing />);
    expect(text()).not.toMatch(/원\/월|월\s*\d|무료 체험|평생 무료/);
    expect(text()).toContain("정해지기 전에는 결제를 요구하지 않습니다");
  });
});

describe("랜딩 — 법·접근성 최소선", () => {
  it("처리방침과 문의 링크가 있다(구글 OAuth 앱 게시 요건)", () => {
    render(<Landing />);
    const policy = screen.getAllByRole("link", { name: "개인정보 처리방침" });
    expect(policy.length).toBeGreaterThanOrEqual(1);
    for (const a of policy) expect(a.getAttribute("href")).toBe(PRIVACY_POLICY_PATH);
    expect(screen.getByRole("link", { name: "문의" }).getAttribute("href")).toMatch(/^mailto:/);
  });

  it("일러스트에 대체 텍스트가 있고, 문서 구조(header·main·footer)가 선다", () => {
    render(<Landing />);
    expect(screen.getByRole("img").getAttribute("alt")).toMatch(/2~3층이 비어 있다/);
    expect(screen.getByRole("banner")).toBeTruthy();
    expect(screen.getByRole("main")).toBeTruthy();
    expect(screen.getByRole("contentinfo")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
