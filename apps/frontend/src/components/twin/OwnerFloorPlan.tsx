/**
 * Page 의 층 배치도 자리 — 건물주가 이 층의 **실제 배치도 사진**을 올렸으면 개략(가상) 배치도 **대신** 그 사진을 보인다(2026-11-22).
 *
 * - 사진은 건물주가 직접 올린 것이고(소유자 확인을 거쳐 게시 중인 매물만 공개 — L3) 실제와 같다는 보증은 아니다 → 화면에 그렇게 적는다.
 * - 개략 배치도로 돌아가는 단추를 둔다 — 사진이 흐리거나 틀려 보일 때 비교할 수 있게. 사진이 없는 층은 개략 배치도 그대로다.
 * - 이 층에 건물주 확인 매물이 있으면(사진이 없어도) 조건 보기·문의·입점 희망서로 잇는 줄을 더한다(Page ▶ Posting).
 * - 매물 조회가 실패(표 준비 중·네트워크)해도 개략 배치도는 그대로 선다 — 이 칸은 **더하는** 것이다.
 */
import { useEffect, useState } from "react";
import type { BuildingTwin, DirectListingCard, TwinFloor } from "@/lib/api";
import { priceLine } from "@/flow/direct";
import FloorPlan from "./FloorPlan";
import { ownerListingsOf } from "./ownerListings";

export default function OwnerFloorPlan({ twin, floor }: { twin: BuildingTwin; floor: TwinFloor }) {
  // 응답을 건물 id 로 묶는다 — 건물이 바뀌면 지난 건물의 매물을 보이지 않는다(효과 안에서 동기로 비우지 않는다)
  const [loaded, setLoaded] = useState<{ id: string; items: DirectListingCard[] } | null>(null);
  const [view, setView] = useState<"real" | "virtual">("real");
  const buildingId = twin.id;
  useEffect(() => {
    if (!buildingId) return;
    let live = true;
    void ownerListingsOf(buildingId).then((items) => { if (live) setLoaded({ id: buildingId, items }); });
    return () => { live = false; };
  }, [buildingId]);
  const items = loaded && loaded.id === buildingId ? loaded.items : [];

  const here = items.filter((l) => l.floor === floor.lv);
  const withPlan = here.find((l) => l.floor_plan);
  const plan = withPlan?.floor_plan ?? null;
  const first = here[0];

  return (
    <>
      {first && (
        <section className="twin3d-owner" aria-label="건물주가 직접 올린 이 층 매물">
          <p><b>건물주가 직접 올린 빈 자리</b>{here.length > 1 ? ` ${here.length}곳` : ""} · 소유자 확인 · {first.title} · {priceLine(first)}</p>
          <p className="twin3d-owner-links">
            <a href={`#/listing/${encodeURIComponent(first.id)}`}>조건 보기 · 문의하기 →</a>
            <a href="#/brief">입점 희망서 쓰기 →</a>
          </p>
        </section>
      )}
      {plan && withPlan && (
        <div className="twin3d-owner-toggle" role="group" aria-label="배치도 보기 방식">
          <button type="button" className="twin3d-btn" aria-pressed={view === "real"} onClick={() => setView("real")}>건물주가 올린 실제 배치도</button>
          <button type="button" className="twin3d-btn" aria-pressed={view === "virtual"} onClick={() => setView("virtual")}>개략(가상) 배치도</button>
        </div>
      )}
      {plan && withPlan && view === "real"
        ? (
          <figure className="twin3d-owner-fig">
            <img src={plan.url} width={plan.width} height={plan.height} loading="lazy" decoding="async"
              alt={`${floor.label} 실제 배치도 — 건물주가 직접 올린 사진`} />
            <figcaption className="twin3d-note">
              {floor.label} 실제 배치도 · 건물주가 직접 올린 사진{plan.updated_at ? ` · ${plan.updated_at.slice(0, 10)} 올림` : ""} · 소유자 확인을 거친 매물.{" "}
              {plan.notice}
            </figcaption>
          </figure>
        )
        : <FloorPlan twin={twin} floor={floor} />}
    </>
  );
}
