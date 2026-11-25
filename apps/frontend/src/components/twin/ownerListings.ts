import { listDirectListings, type DirectListingCard } from "@/lib/api";

/** 같은 건물을 층마다 다시 부르지 않게 짧게 기억한다(60초) — 올린 직후 지도로 와도 오래 낡지 않는다. 실패는 기억하지 않는다. */
const TTL_MS = 60_000;
const cache = new Map<string, { at: number; items: Promise<DirectListingCard[]> }>();

/** 이 건물에 건물주가 직접 올린(소유자 확인 · 게시 중) 매물 — 조회가 실패해도 빈 목록이다(Page 의 개략 배치도는 그대로 선다). */
export function ownerListingsOf(buildingId: string): Promise<DirectListingCard[]> {
  const hit = cache.get(buildingId);
  if (hit && Date.now() - hit.at < TTL_MS) return hit.items;
  const items = listDirectListings({ building_id: buildingId }).then((r) => r.items)
    .catch(() => { cache.delete(buildingId); return [] as DirectListingCard[]; });
  cache.set(buildingId, { at: Date.now(), items });
  return items;
}
