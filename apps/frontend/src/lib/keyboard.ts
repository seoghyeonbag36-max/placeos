/**
 * 키보드 공통 규칙 — 화면설계서 2판 §공통 프레임 「키보드」.
 *
 * **입력칸에 포커스가 있으면 Esc 로 아무것도 닫지 않는다.** 검색어를 지우려고 Esc 를 누른
 * 사람의 패널·상세가 눈앞에서 닫히면 쓰던 맥락이 통째로 사라진다. 1판 때는 트랙 패널만 이
 * 규칙을 지키고 Page 는 입력칸에서도 한 겹씩 닫아, 네 화면이 같은 키에 다르게 반응했다.
 */
export function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || typeof el.tagName !== "string") return false;
  return /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable === true;
}

/**
 * 의견창(VisitorFeedback)이 열려 있으면 Esc 는 그 창의 것이다 — 뒤의 지도 패널·건물 상세까지 같이 닫히면
 * 의견을 쓰다 만 사람의 화면이 한꺼번에 사라지고, 접힌 패널이 초점을 가져가 의견창을 연 버튼으로 못 돌아온다.
 * 2026-11-08: 의견창 입구가 지도 패널 바로 옆 레일로 옮겨 와 두 창이 같은 Esc 를 받는 일이 잦아졌다.
 * 열린 창은 DOM 에 있는지로 본다 — `dialog[open]` 을 거르는 기존 규칙과 같은 방식이다.
 */
export function feedbackPanelOpen(): boolean {
  return document.querySelector(".visitor-feedback-panel") !== null;
}
