/** 입점 점검 다섯 갈래의 화면 이름 — 「입점 가능」「허가됨」이라 쓰지 않는다(UseCheckCard.test 가 지킨다). */
import type { UseCheckStatus } from "@/lib/api";

export const USE_CHECK_LABEL: Record<UseCheckStatus, string> = {
  ledger_ok: "대장상 가능",
  needs_check: "확인 필요",
  use_change_needed: "대장상 용도 변경 필요",
  zoning_prohibited: "용도지역상 금지",
  missing_inputs: "자료 부족",
};
