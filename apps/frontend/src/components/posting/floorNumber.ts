/** 지도 탐색 층 이름(「2F」 · 「B1」 · 「1층」 · 「지하1층」) → 직거래 매물의 층 번호(지하는 음수 · services/direct_listings `basement = floor < 0`).
 *  모르면 null — 그때는 층으로 견주지 않고 건물까지만 본다(Proposal 「입점 희망서 제출」 보낼 곳 순서 · 2026-11-26). */
export function floorNumber(label: string | null | undefined): number | null {
  const s = (label ?? "").trim();
  const up = /^(\d{1,3})\s*(?:F|층)$/i.exec(s);
  if (up) return Number(up[1]);
  const down = /^(?:B|지하)\s*(\d{1,2})\s*(?:F|층)?$/i.exec(s);
  return down ? -Number(down[1]) : null;
}
