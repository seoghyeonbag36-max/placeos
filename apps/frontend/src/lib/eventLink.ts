export interface EventLink { name: string; when: string; online: string; offline: string; evidence: string }
export function readEventLink(district: string): EventLink | null {
  try {
    const value = JSON.parse(localStorage.getItem(`placeos.event-link.${district}`) ?? "null");
    return value && ["name", "when", "online", "offline", "evidence"].every(k => typeof value[k] === "string") ? value : null;
  } catch { return null; }
}
