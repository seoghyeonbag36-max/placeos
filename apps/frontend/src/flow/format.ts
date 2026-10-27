/**
 * 숫자를 **체감 단위 먼저** 말한다(화면설계서 5판 §4-4 · 토스 「30% 할인」보다 「치킨 5000원 할인」).
 * 정밀 값은 화면이 따로 작게 싣는다 — 여기 함수들은 결론 문장에 들어갈 말만 만든다.
 */

/** 만원 → 「9,250만원」 · 「1억 2,500만원」 · 「3억원」. 음수는 부호를 떼고 호출부가 문장으로 말한다 */
export function manwon(value: number): string {
  const v = Math.round(Math.abs(value));
  const eok = Math.floor(v / 10_000);
  const rest = v % 10_000;
  if (eok === 0) return `${rest.toLocaleString("ko-KR")}만원`;
  if (rest === 0) return `${eok.toLocaleString("ko-KR")}억원`;
  return `${eok.toLocaleString("ko-KR")}억 ${rest.toLocaleString("ko-KR")}만원`;
}

/** 원 → 만원(반올림). 서버 예산 점검 계약은 원 단위 정수다 */
export const wonToManwon = (won: number) => Math.round(won / 10_000);
export const manwonToWon = (m: number) => Math.round(m * 10_000);

/** 개월 → 「한 달 안에」 · 「약 3개월」 · 「약 1년」 · 「약 1년 2개월」 */
export function months(m: number): string {
  if (m < 1) return "한 달 안에";
  const total = Math.round(m);
  if (total < 12) return `약 ${total}개월`;
  const y = Math.floor(total / 12);
  const r = total % 12;
  return r === 0 ? `약 ${y}년` : `약 ${y}년 ${r}개월`;
}

/** 「약 n개월이면」처럼 문장에 넣을 때 — 「한 달 안에」는 「이면」을 붙이지 않는다 */
export const monthsClause = (m: number) => (m < 1 ? "한 달 안에" : `${months(m)}이면`);

/** 입력칸 문자열 → 0 이상 정수(만원). 비었거나 숫자가 아니면 null */
export function parseManwon(text: string): number | null {
  const digits = text.replace(/[^\d]/g, "");
  if (!digits) return null;
  const n = Number(digits);
  return Number.isFinite(n) ? n : null;
}

/** 입력칸에 보일 문자열 — 천 단위 쉼표 */
export const showManwon = (n: number | null | undefined) => (n == null ? "" : n.toLocaleString("ko-KR"));

/** 사람 수 → 「8,338명」 · 「18.9만 명」. 만 명부터는 소수 한 자리(일평균 추정치라 그 아래는 뜻이 없다) */
export function people(n: number): string {
  const v = Math.round(n);
  if (v < 10_000) return `${v.toLocaleString("ko-KR")}명`;
  return `${(v / 10_000).toFixed(1)}만 명`;
}

/** 받침으로 가르는 조사 — 「카페는」 「음식점은」 · 「카페로」 「음식점으로」 */
const lastHangul = (w: string) => [...w].reverse().find((ch) => ch >= "가" && ch <= "힣");
const jong = (ch: string) => (ch.charCodeAt(0) - 0xac00) % 28;
export const eun = (w: string) => { const l = lastHangul(w); return `${w}${l && jong(l) ? "은" : "는"}`; };
export const iga = (w: string) => { const l = lastHangul(w); return `${w}${l && jong(l) ? "이" : "가"}`; };
export const ro = (w: string) => { const l = lastHangul(w); const j = l ? jong(l) : 0; return `${w}${!l || j === 0 || j === 8 ? "로" : "으로"}`; };
