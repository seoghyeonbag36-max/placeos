import { useEffect, useState } from "react";
import { getBuildingTwin, type BuildingTwin } from "@/lib/api";
import { TWIN_STATUS } from "@/lib/twinGeometry";
import { useReportCapture } from "@/lib/ppppReportContext";
import FloorPlan from "./FloorPlan";
import HistoryTimeline from "./HistoryTimeline";
import "./BuildingTwinDialog.css";

/** Page 상세에서 모달을 열기 전에도 층·호실·배치 근거와 점포 이력을 확인한다. */
export default function FloorExplorer({ districtId, buildingId }: { districtId: string; buildingId: string }) {
  const [open, setOpen] = useState(false);
  return <section><button type="button" className="b-twin" aria-expanded={open} onClick={() => setOpen(!open)}>층·호실 상세 · 개략 배치도 · 점포 이력 {open ? "접기" : "열기"}</button>
    {open && <FloorExplorerContent districtId={districtId} buildingId={buildingId} />}</section>;
}

function FloorExplorerContent({ districtId, buildingId }: { districtId: string; buildingId: string }) {
  const [twin, setTwin] = useState<BuildingTwin | null>();
  const [lv, setLv] = useState<number | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getBuildingTwin(buildingId, districtId, ctrl.signal).then(data => {
      if (!ctrl.signal.aborted) { setTwin(data); setLv(data?.floors[0]?.lv ?? null); }
    }).catch(() => { if (!ctrl.signal.aborted) setTwin(null); });
    return () => ctrl.abort();
  }, [buildingId, districtId]);
  const floor = twin?.floors.find(f => f.lv === lv);
  useReportCapture("pageFloor", floor ? {
    districtId, buildingId, label: floor.label, area: floor.area_m2, areaSource: floor.area_source,
    status: TWIN_STATUS[floor.status].label, unitId: floor.unit_id,
  } : null);
  return <section className="twin3d-floor" aria-label="층·호실 디지털 트윈 상세">
    <h3>층·호실 디지털 트윈 · 개략 배치도</h3>
    {twin === undefined ? <p role="status">층·호실 자료 불러오는 중…</p> : !twin ? <p>층·호실 자료가 없습니다.</p> : <>
      <div className="twin3d-cta" role="group" aria-label="상세 층 선택">{twin.floors.map(f => <button type="button" className="twin3d-btn" key={f.lv} aria-pressed={lv === f.lv} onClick={() => setLv(f.lv)}>{f.label} · {TWIN_STATUS[f.status].label}</button>)}</div>
      {floor && <><p>{floor.label} · {floor.purps ?? "용도 미제공"} · 호실 {floor.units?.length ?? 0}개 확인 · 호실별 공실 여부 미확인</p><FloorPlan key={buildingId} twin={twin} floor={floor} /></>}
      <h4>점포 이력 · 지번 단위</h4>
      <p>출처: {twin.history.source} · 호실 귀속 미확인 · 폐업일이 공실 시작일을 뜻하지 않습니다.</p>
      <HistoryTimeline items={twin.history.items} total={twin.history.items_total} lotBuildings={twin.history.lot_buildings} />
    </>}
  </section>;
}
