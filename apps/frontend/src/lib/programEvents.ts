import type { MarketingEvent } from "./api";

/** 행사 기간 문자열("YYYY-MM-DD~YYYY-MM-DD")을 가른다. 모양이 다르면 null — 그 행사는 거르지 않는다
 *  (날짜를 모르는 것을 종료로 단정하면 있는 행사를 지운다). */
export function eventRange(when: string | null | undefined): { start: string; end: string } | null {
  const m = /^(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})/.exec(when ?? "");
  if (m) return { start: m[1], end: m[2] };
  const one = /^(\d{4}-\d{2}-\d{2})/.exec(when ?? "");
  return one ? { start: one[1], end: one[1] } : null;
}

/** 종료일이 오늘보다 앞선 행사를 뺀다(화면설계서 PR-01). 끝난 행사를 "연계할 곳"으로 보여주면 거짓 안내가 된다.
 *  `today` 는 로컬 날짜 "YYYY-MM-DD". 남은 것은 시작일 순. */
export function splitEvents(events: MarketingEvent[], today: string): { upcoming: MarketingEvent[]; ended: number } {
  const upcoming: MarketingEvent[] = [];
  let ended = 0;
  for (const e of events) {
    const r = eventRange(e.when);
    if (r && r.end < today) ended += 1; else upcoming.push(e);
  }
  upcoming.sort((a, b) => (eventRange(a.when)?.start ?? "9999").localeCompare(eventRange(b.when)?.start ?? "9999"));
  return { upcoming, ended };
}
