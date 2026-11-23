/** Program 네트워킹 — 이웃 가게·상인 조직과 나눈 이야기 메모를 이 브라우저에 둔다(행사 연계 계획과 같은 방식).
 *  서버에 저장하지 않으므로 개인정보 처리 범위가 늘지 않는다. (종합 리포트(PpppReport)는 2026-11-22 에 지웠다.)
 *  2026-11-22 Program 에서 「지원 프로그램」을 제외하면서 담은 지원 공고(placeos.program.support.*)를 쓰는 길도 걷었다 —
 *  이미 담아 둔 값은 이 브라우저에 남아도 읽는 화면이 없다(→ docs/decision-program-post-opening-2026-11-22.md).
 *  저장소를 못 쓰는 브라우저(사생활 보호 창 등)에서도 화면은 그대로 돈다 — 실패하면 조용히 비운다. */
export interface NetworkNotes { checked: string[]; memo: string }

const networkKey = (district: string) => `placeos.program.network.${district}`;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export const readNetworkNotes = (district: string): NetworkNotes => {
  const v = read<Partial<NetworkNotes> | null>(networkKey(district), null);
  return { checked: Array.isArray(v?.checked) ? v!.checked.filter((x) => typeof x === "string") : [],
    memo: typeof v?.memo === "string" ? v.memo : "" };
};

export const saveNetworkNotes = (district: string, notes: NetworkNotes): boolean => write(networkKey(district), notes);
