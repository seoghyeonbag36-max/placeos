import type { SupportItem } from "@/lib/api";

/** Program 리뉴얼(2026-11-07) — 담은 지원 공고·이웃 방문 메모를 이 브라우저에 둔다(행사 연계 계획과 같은 방식).
 *  서버에 저장하지 않으므로 개인정보 처리 범위가 늘지 않는다. 가설 검증의 결과 리포트(PpppReport)가 읽는다.
 *  저장소를 못 쓰는 브라우저(사생활 보호 창 등)에서도 화면은 그대로 돈다 — 실패하면 조용히 비운다. */
export interface SavedSupport {
  id: string; title: string; source_label: string; org?: string | null; end?: string | null;
  deadline_text?: string | null; url?: string | null;
}
export interface NetworkNotes { checked: string[]; memo: string }

const supportKey = (district: string) => `placeos.program.support.${district}`;
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

export const readSavedSupport = (district: string): SavedSupport[] => {
  const v = read<unknown>(supportKey(district), []);
  return Array.isArray(v) ? (v as SavedSupport[]).filter((x) => x && typeof x.id === "string" && typeof x.title === "string") : [];
};

export function toggleSavedSupport(district: string, item: SupportItem): { saved: SavedSupport[]; ok: boolean } {
  const now = readSavedSupport(district);
  const next = now.some((x) => x.id === item.id)
    ? now.filter((x) => x.id !== item.id)
    : [...now, { id: item.id, title: item.title, source_label: item.source_label, org: item.org, end: item.end,
      deadline_text: item.deadline_text, url: item.url }];
  return { saved: next, ok: write(supportKey(district), next) };
}

export const readNetworkNotes = (district: string): NetworkNotes => {
  const v = read<Partial<NetworkNotes> | null>(networkKey(district), null);
  return { checked: Array.isArray(v?.checked) ? v!.checked.filter((x) => typeof x === "string") : [],
    memo: typeof v?.memo === "string" ? v.memo : "" };
};

export const saveNetworkNotes = (district: string, notes: NetworkNotes): boolean => write(networkKey(district), notes);
