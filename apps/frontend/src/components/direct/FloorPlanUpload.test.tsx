/**
 * 건물주의 층 배치도 사진 올리기 (2026-11-22) — 줄인 사진을 보여 주고 올린다 · 이미 올렸으면 보이고 바꾸거나 지운다 ·
 * 사진은 본인이 올린다는 것과 위치·기기 정보를 지운다는 것을 화면에 적는다. 아래 매물은 테스트 전용 합성값이다.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "@/lib/api";
import type { DirectOwnerListing } from "@/lib/api";
import * as image from "@/lib/floorPlanImage";
import FloorPlanUpload from "./FloorPlanUpload";

const base = {
  id: "L1", title: "합성 주소 2층", status: "published", status_label: "게시 중", missing: [], promoted_until: null,
  verification: { status: "verified", relation: "owner", registry_masked: "****2345", reviewer_note: "", created_at: "2026-11-22T00:00:00+00:00" },
} as unknown as DirectOwnerListing;
const withPlan = { ...base, floor_plan: { url: "/api/v1/direct/listings/L1/floor-plan?v=1", width: 800, height: 600, size_bytes: 120_000, updated_at: "2026-11-22T01:00:00+00:00", notice: "n" } } as DirectOwnerListing;
const PREPARED: image.PreparedFloorPlan = { mime: "image/jpeg", data: "QUJD", width: 1200, height: 900, previewUrl: "blob:preview", bytes: 300_000 };

beforeEach(() => {
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:made"), revokeObjectURL: vi.fn() }));
  vi.spyOn(api, "fetchMyFloorPlanUrl").mockResolvedValue("blob:mine");
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("사진을 고르면 줄인 미리보기를 보이고, 누르면 서버로 올린다", async () => {
  vi.spyOn(image, "prepareFloorPlan").mockResolvedValue(PREPARED);
  const put = vi.spyOn(api, "putDirectFloorPlan").mockResolvedValue(withPlan.floor_plan!);
  const done = vi.fn();
  render(<FloorPlanUpload listing={base} token="tok" onChanged={done} />);
  expect(screen.getByText(/촬영 위치·기기 정보는 지워요/)).toBeTruthy();
  expect(document.body.textContent).toContain("개략 배치도 대신 이 사진이 보여요");        // <b>대신</b> 이 글자를 나눠도 한 문장으로 읽힌다
  fireEvent.change(screen.getByLabelText(/배치도 사진 고르기/), { target: { files: [new File(["x"], "a.jpg", { type: "image/jpeg" })] } });
  expect(await screen.findByAltText("올릴 배치도 사진 미리보기")).toBeTruthy();
  expect(screen.getByText(/줄인 사진 · 1200×900px · 300KB/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "이 사진으로 올리기" }));
  await waitFor(() => expect(put).toHaveBeenCalledWith("tok", "L1", { mime: "image/jpeg", data: "QUJD" }));
  await waitFor(() => expect(done).toHaveBeenCalledWith("배치도 사진을 올렸어요"));
});

it("읽을 수 없는 사진은 이유를 보이고 올리지 않는다", async () => {
  vi.spyOn(image, "prepareFloorPlan").mockRejectedValue(new Error("이 사진을 읽지 못했어요. JPEG 또는 PNG 사진으로 다시 골라 주세요."));
  const put = vi.spyOn(api, "putDirectFloorPlan");
  render(<FloorPlanUpload listing={base} token="tok" onChanged={() => {}} />);
  fireEvent.change(screen.getByLabelText(/배치도 사진 고르기/), { target: { files: [new File(["x"], "a.heic", { type: "image/heic" })] } });
  expect((await screen.findByRole("alert")).textContent).toContain("읽지 못했어요");
  expect(screen.queryByRole("button", { name: /이 사진으로/ })).toBeNull();
  expect(put).not.toHaveBeenCalled();
});

it("이미 올렸으면 내 사진을 보이고 바꾸거나 지울 수 있다", async () => {
  const del = vi.spyOn(api, "deleteDirectFloorPlan").mockResolvedValue(undefined);
  const done = vi.fn();
  render(<FloorPlanUpload listing={withPlan} token="tok" onChanged={done} />);
  expect((await screen.findByAltText(/배치도\(내가 올린 사진\)/)).getAttribute("src")).toBe("blob:mine");
  // 버전(v)이 붙은 서버 주소로 받는다 — 바꿔 올린 직후 옛 사진이 보이지 않게(11-22 리뷰 반영)
  expect(api.fetchMyFloorPlanUrl).toHaveBeenCalledWith("tok", "/api/v1/direct/listings/L1/floor-plan?v=1");
  expect(screen.getByText(/올린 사진 · 800×600px · 120KB · 2026-11-22/)).toBeTruthy();
  expect(screen.getByText(/지금 게시 중이라 올리면 바로 보여요/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "사진 지우기" }));
  await waitFor(() => expect(del).toHaveBeenCalledWith("tok", "L1"));
  await waitFor(() => expect(done).toHaveBeenCalledWith("배치도 사진을 지웠어요"));
});

it("서버가 준비 중(503)이면 그렇게 알린다", async () => {
  vi.spyOn(image, "prepareFloorPlan").mockResolvedValue(PREPARED);
  vi.spyOn(api, "putDirectFloorPlan").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  render(<FloorPlanUpload listing={base} token="tok" onChanged={() => {}} />);
  fireEvent.change(screen.getByLabelText(/배치도 사진 고르기/), { target: { files: [new File(["x"], "a.jpg", { type: "image/jpeg" })] } });
  fireEvent.click(await screen.findByRole("button", { name: "이 사진으로 올리기" }));
  expect((await screen.findByRole("alert")).textContent).toContain("준비하고 있어요");
});

it("소유자 확인 전에는 게시 뒤부터 보인다고 알린다", () => {
  render(<FloorPlanUpload listing={{ ...base, status: "pending", verification: null } as DirectOwnerListing} token="tok" onChanged={() => {}} />);
  expect(screen.getByText(/소유자 확인을 거쳐 게시된 뒤부터 다른 이용자에게 보여요/)).toBeTruthy();
});
