// PlaceOS 디자인 토큰 — 색상 (단일 출처)
// 네이버 호환: green은 네이버 연동 맥락에만, brand(teal)는 PlaceOS 고유 기능.
export const colors = {
  naver: { green: "#03C75A", greenPressed: "#02B350", greenSoft: "#E6F8EE" },
  brand: { primary: "#0EA5B7", primaryPressed: "#0B8294", soft: "#E6F7F9" },
  // PPPP 네 트랙 색 (2026-09-06) — 레일·헤더·범례가 "지금 어느 트랙인지"를 색으로 말한다.
  // 색상각 242·272·302·332 도. 그 밖은 이미 임자가 있다 — 공실 축 3~160도, 네이버 147도,
  // brand teal 186도, UI 남색 #3A5A98 220도. 채도는 전부 S46% 로 teal(S86%)의 절반이라
  // 주색을 이기지 않고, 명도는 색맹·흑백 구분을 위해 일부러 어긋냈다.
  // base 넷 모두 bg(#F4F7FB)·surface(#FFFFFF)·자기 soft 위에서 AA 4.5:1 통과.
  // ⚠ 값은 styles/tokens.css · design/tokens/tokens.json 과 같아야 한다.
  track: {
    platform: { base: "#6460C4", pressed: "#4945B9", soft: "#F0F0FB" },
    page:     { base: "#753DA6", pressed: "#61338A", soft: "#F6F0FB" },
    posting:  { base: "#A23C9F", pressed: "#863284", soft: "#FBF0FB" },
    program:  { base: "#7E2F53", pressed: "#622541", soft: "#FBF0F5" },
  },
  // 실측 출처(R-ONE·대장) 색 — 임대시세 금액·출처 배지 (2026-09-13, 화면설계서 2판 §토큰)
  source: { real: { base: "#0F7A55", soft: "#E3F5EE", line: "#B7E3D2" } },
  ink: "#1C2533",
  muted: "#6B7280",
  line: "#E3E9F2",
  surface: "#FFFFFF",
  bg: "#F4F7FB",
  // UI 보조 색 (2026-09-28 · 2차 hex 이관) — styles/tokens.css 의 같은 블록과 1:1.
  // pages/*.css 에 흩어져 있던 값을 그대로 이름만 붙였다(반올림·통합 없음).
  // ⚠ ui.danger 는 semantic.danger(공실 축 빨강 #E03E36)와 다른 계열 — 오류 박스·문구용.
  ui: {
    textSecondary: "#5A6B85",
    textSubtle: "#9AA3AF",
    surfaceSunken: "#F1F4F8",
    surfaceSubtle: "#FAFBFC",
    navy: "#3A5A98",
    onAccent: "#FFFFFF",
    danger: { soft: "#FEF2F2", line: "#FECACA", text: "#B91C1C", ink: "#7F1D1D" },
    warn: { soft: "#FFFBEB", line: "#FDE68A", ink: "#78350F" },
    caution: { soft: "#FDF5E3", line: "#F0DCAE", ink: "#8A5A00" },
    note: { soft: "#FDF8EC", line: "#F3E6C4", ink: "#8A6D3B" },
    // 3차 이관 — inkAlt·lineAlt 는 대시보드 계열의 지역 ink/line(전역 ink·line 과 값이 다르다)
    inkAlt: "#1F2937",
    lineAlt: "#E5E7EB",
    textTertiary: "#8A93A0",
    surfaceMuted: "#F6F7F9",
    blue: "#2E6FB7",
    navyDeep: "#1E3A5F",
  },
  // 공실 히트맵 색계열 (저위험→고위험)
  vacancy: ["#22B07D", "#9CCB3B", "#EFA50F", "#F2682C", "#E03E36"],
  semantic: { success: "#22B07D", warning: "#EFA50F", danger: "#E03E36", info: "#0EA5B7" },
} as const;
export type Colors = typeof colors;
// PPPP 트랙 키 — CLAUDE.md 의 프레임워크 순서와 같다(Platform → Page → Posting → Program).
export type TrackKey = keyof typeof colors.track;
