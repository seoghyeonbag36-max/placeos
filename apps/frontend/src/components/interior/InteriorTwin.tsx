import { useEffect, useState } from "react";
import { getBuildingTwin, type BuildingTwin } from "@/lib/api";
import type { InteriorStrategy } from "@/lib/interiorLayout";
import { pickFloor } from "@/lib/interiorTwin";
import InteriorTwinView from "./InteriorTwinView";

/** 고른 공실 자리의 트윈을 불러 내부 3D 를 세운다(Posting 「상권 맞춤 인테리어」 · 2026-11-09). */
export default function InteriorTwin({ buildingId, unitId, districtId, floorLabel, keywords, industry, strategy, onSummary }: {
  buildingId?: string | null; unitId?: string | null; districtId?: string | null; floorLabel?: string | null;
  keywords: readonly string[]; industry?: string | null; strategy?: InteriorStrategy | null;
  /** 배치 요약(좌석 · 집기) — 리포트 · 저장에 싣는다 */
  onSummary?: (lines: string[]) => void;
}) {
  const id = buildingId ?? unitId ?? null;
  const [state, setState] = useState<{ key: string; twin: BuildingTwin | null; failed: boolean } | null>(null);
  const key = `${districtId}:${id}`;
  useEffect(() => {
    if (!id || !districtId) return;
    const ctrl = new AbortController();
    getBuildingTwin(id, districtId, ctrl.signal)
      .then((twin) => setState({ key, twin, failed: false }))
      .catch(() => { if (!ctrl.signal.aborted) setState({ key, twin: null, failed: true }); });
    return () => ctrl.abort();
  }, [id, districtId, key]);

  if (!id || !districtId) return <p className="interior3d-note">공실 자리를 먼저 고르면 그 자리의 3D 디지털 트윈으로 내부를 세웁니다.</p>;
  const cur = state?.key === key ? state : null;
  if (!cur) return <p className="interior3d-note" role="status">공실 자리의 3D 디지털 트윈을 불러오는 중…</p>;
  if (!cur.twin || cur.twin.ring.length < 3) {
    return <p className="interior3d-note"><span className="value-absent">자료 없음</span> — 이 자리의 건물 외곽선 · 트윈 자료가 없어 내부를 세우지 못했습니다{cur.failed ? "(조회 실패)" : ""}.</p>;
  }
  const floor = pickFloor(cur.twin, unitId, floorLabel);
  if (!floor) return <p className="interior3d-note"><span className="value-absent">자료 없음</span> — 이 건물의 층 자료가 없습니다.</p>;
  return (
    <>
      <p className="interior3d-where">{cur.twin.name ?? cur.twin.road_addr ?? "건물"} · {floor.label}
        {floor.area_m2 ? ` · 층 바닥 ${floor.area_m2.toLocaleString("ko-KR")}㎡(대장)` : ""}</p>
      <InteriorTwinView twin={cur.twin} floor={floor} keywords={keywords} industry={industry} strategy={strategy} onSummary={onSummary} />
    </>
  );
}
