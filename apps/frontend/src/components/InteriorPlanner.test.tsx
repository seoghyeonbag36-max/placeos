/** 공급자·이미지는 테스트용 합성 응답. 실호출이나 상권 적합성의 증거가 아니다. */
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import InteriorPlanner from "./InteriorPlanner";
import { clearToken, saveToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";

afterEach(() => { cleanup(); clearToken(); });

it("동의 전 생성 호출이 없고 명시한 조건만 인증 요청으로 보낸다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /^\/api\/v1\/ai\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "AI 생성 참고 이미지 · 실측 아님",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  const generate = screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement;
  expect(generate.disabled).toBe(true);
  expect(api.calls).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(generate);
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
  expect(api.matching(/interior-preview$/)[0].body).toMatchObject({ district: "garosugil", industry: "카페", style: "따뜻함", consent: true, references: [] });
  expect(api.matching(/interior-preview$/)[0].body).not.toHaveProperty("area_py");
  expect(api.matching(/interior-preview$/)[0].url).toBe("/api/v1/ai/interior-preview");
});

it("미설정·실패 시 이미지를 만들지 않고 지시문을 보존한다", async () => {
  saveToken("test-only-token");
  installFetchStub([{ match: /\/interior-preview$/, status: 503, body: { detail: "not configured" } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "깔끔함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "AI 참고 이미지 생성" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("생성하지 못했습니다"));
  expect(screen.queryByRole("img")).toBeNull();
  expect((screen.getByLabelText("분위기·색감") as HTMLInputElement).value).toBe("깔끔함");
  expect(screen.getByRole("button", { name: "생성 지시문·비용 결과 저장" })).toBeTruthy();
});
