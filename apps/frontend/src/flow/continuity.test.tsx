import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { emptyFlow, setDistrict } from "./state";
import { go } from "./route";
import { FlowScreen } from "./ui";

describe("탐색 상태 연속성", () => {
  it("상권 변경 시 조건 초기화", () => {
    const state = emptyFlow();
    state.districtId = "seongsu";
    state.spaceBrowse = { ...state.spaceBrowse, first: true, shown: 72 };
    state.spaceId = "vfu-B1-1";
    expect(setDistrict(state, "garosugil")).toMatchObject({ spaceId: null, rentCap: null,
      spaceBrowse: { first: false, shown: 24 } });
  });

  it("뒤로 가기 위치 복원 — 이동 전 위치를 저장하고 원래 기록에서 복원한다", async () => {
    window.history.replaceState(null, "", "/#/spaces");
    document.documentElement.scrollTop = 360;
    go("/space/vfu-B1-1");
    window.history.back();
    await waitFor(() => expect(window.location.hash).toBe("#/spaces"));
    expect(window.history.state.flowScroll).toBe(360);
    const height = vi.spyOn(document.documentElement, "scrollHeight", "get").mockReturnValue(2000);
    render(<FlowScreen title="빈 자리" />);
    expect(document.documentElement.scrollTop).toBe(360);
    height.mockRestore();
    window.history.replaceState(null, "", "/");
  });
});
