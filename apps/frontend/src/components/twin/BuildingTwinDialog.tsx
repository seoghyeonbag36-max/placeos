/**
 * 건물 3D 트윈 대화상자(Case 2). 이 파일은 three 를 import 하지 않는다 — 장면은 `TwinScene` 을 동적으로 불러온다.
 * WebGL 이 안 되면 2D 층 스택으로 내려가고 목록·층 버튼·선택 층 패널은 그대로 산다.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { FloorStack } from "@/components/BuildingViewer";
import EvidenceBadge from "@/components/EvidenceBadge";
import type { ViewerBuilding } from "@/components/buildingFloors";
import { getBuildingTwin, type BuildingTwin, type TwinFloor } from "@/lib/api";
import { kakaoRoadviewUrl } from "@/lib/externalMap";
import { addStop, hasStop, removeStop } from "@/lib/journeyState";
import { ledgerNote } from "@/lib/twinLedger";
import { STORE_STATE_LABEL, storesNote, unitStoreState } from "@/lib/twinStores";
import { areaSummary, isVacantStatus, TWIN_STATUS } from "@/lib/twinGeometry";
import FloorPlan from "./FloorPlan";
import { useReportCapture } from "@/lib/ppppReportContext";
import HistoryTimeline from "./HistoryTimeline";
import RoadCheckSection from "./RoadCheckSection";
import type { TwinMode, TwinSceneHandle } from "./TwinScene";
import type { RoadLayerStats } from "./twinRoads";
import "./BuildingTwinDialog.css";

const MODES: { key: TwinMode; label: string }[] = [
  { key: "exterior", label: "외관" }, { key: "exploded", label: "층 분리" }, { key: "vacant", label: "공실만 강조" },
];
const LEGEND = ["vacant_confirmed", "vacant_probable", "occupied", "uncertain", "noncom", "unknown"] as const;
const PY = 3.305785;
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex="0"]';

const asOf = (t: BuildingTwin) => (t.built_at ? t.built_at.slice(0, 10) : null);
const ymd = (d: string | null) => (d && d.length >= 8 ? `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}` : d);
const manwon = (v: number) => `${v.toLocaleString("ko-KR")}만원`;

export interface BuildingTwinDialogProps {
  buildingId: string; districtId: string; districtName?: string;
  /** WebGL 실패 때 그릴 2D 층 스택 입력 */
  fallback: ViewerBuilding;
  onClose: () => void;
  onReview?: (floor: TwinFloor | null, twin: BuildingTwin) => void;
  /** 거리뷰·층별 화면을 열 수 있으면 넘긴다. 없으면 카카오 로드뷰 링크로 길을 남긴다. */
  onOpenStreet?: () => void;
}

function FloorDetail({ twin, floor, districtId, onReview, onOpenStreet }: { twin: BuildingTwin; floor: TwinFloor } & Pick<BuildingTwinDialogProps, "districtId" | "onReview" | "onOpenStreet">) {
  const stopKey = { buildingId: twin.id ?? "", floorUnitId: floor.unit_id ?? undefined };
  const [, refreshSaved] = useState(0);
  const saved = hasStop(stopKey);
  const meta = TWIN_STATUS[floor.status];
  const vacant = isVacantStatus(floor.status);
  const areas = areaSummary(floor.units);
  const ledgerFloor = twin.ledger_live?.status === "ok" ? twin.ledger_live.floors?.[String(floor.lv)] ?? null : null;
  const unitArea = areas.excl;
  // 상가정보 대조(2026-11-09) — 응답에 stores_live 가 있을 때만 열을 단다(옛 응답 · 대조 전에는 없다)
  const storesLive = twin.stores_live ?? null;
  // 호수가 있는 점포가 하나도 없으면 열을 달지 않는다 — 전부 「—」인 열은 정보가 없다(2026-11-09 프로덕션: 15개 건물 1,803곳 호수 0)
  const storeCol = !!storesLive && storesLive.has_ho && storesLive.n_with_ho > 0;
  const floorStores = floor.stores ?? [];
  const nMatched = (floor.units ?? []).filter((u) => u.store).length;
  const toggleStop = () => {
    if (saved) removeStop(stopKey);
    else addStop({
      buildingId: twin.id ?? "", districtId, name: twin.name ?? twin.id ?? "건물", lat: twin.lat, lng: twin.lng,
      address: twin.road_addr ?? undefined, floorLabel: floor.label, floorUnitId: floor.unit_id ?? undefined,
      area_m2: floor.area_m2 ?? undefined, monthlyRentEst: floor.rent_est_manwon ?? undefined,
      vacClass: floor.status === "vacant_confirmed" ? "confirmed" : floor.status === "vacant_probable" ? "probable"
        : floor.status === "occupied" ? "full" : "unknown",
      addedFrom: "page",
    });
    refreshSaved((version) => version + 1);
  };
  return (
    <div className="twin3d-floor">
      <div className="twin3d-floor-head">
        <span className="twin3d-badge" style={{ background: meta.color }} aria-hidden />
        <h3>{floor.label} · {meta.label}</h3>
      </div>
      <p className="twin3d-note">{meta.rule}</p>
      <p className="twin3d-note">근거: 상가정보 점포 대조 · 현장 미확인{asOf(twin) ? ` · 기준일 ${asOf(twin)}` : ""}</p>
      <dl className="twin3d-dl">
        {/* 전용면적과 층 바닥면적은 따로 적는다(2026-11-08) — 전용면적은 전유부(전유) 값뿐이고 지어내지 않는다 */}
        <dt>전용면적</dt>
        <dd>{unitArea > 0
          ? <><b className="num">{unitArea.toLocaleString("ko-KR")}㎡</b> ({(unitArea / PY).toFixed(1)}평) <EvidenceBadge kind="실측" /><small> 전유부 {floor.units?.length ?? 0}호실 합</small></>
          : floor.excl_est
            ? <><b className="num">약 {floor.excl_est.m2.toLocaleString("ko-KR")}㎡</b> ({(floor.excl_est.m2 / PY).toFixed(1)}평 · {floor.excl_est.low.toLocaleString("ko-KR")}~{floor.excl_est.high.toLocaleString("ko-KR")}㎡) <EvidenceBadge kind="추정" />
                <small> 일반건축물이라 대장에 전용면적이 없어 층 바닥면적 × {(floor.excl_est.ratio * 100).toFixed(1)}%로 추정했습니다. 근거: {floor.excl_est.basis}</small></>
            : <><span className="value-absent">자료 없음</span><small> 전유부가 없는 층(일반건축물)이라 대장에 전용면적이 없습니다</small></>}</dd>
        {areas.contract != null && <>
          <dt>계약면적</dt>
          <dd><b className="num">{areas.contract.toLocaleString("ko-KR")}㎡</b> ({(areas.contract / PY).toFixed(1)}평) <EvidenceBadge kind="계산" />
            <small> 전용 + 공용 {areas.pub.toLocaleString("ko-KR")}㎡ · 전용률 {areas.ratio}%{areas.nPub < areas.n ? ` · ${areas.nPub}/${areas.n}호실 기준` : ""} · 전유공용면적</small></dd>
        </>}
        <dt>층 바닥면적</dt>
        <dd>{floor.area_m2
          ? <><b className="num">{floor.area_m2.toLocaleString("ko-KR")}㎡</b> ({(floor.area_m2 / PY).toFixed(1)}평) <EvidenceBadge kind="실측" /><small> {floor.area_source ?? "대장 층별개요"} · 계단·화장실 등 공용 포함</small></>
          : <span className="value-absent">자료 없음</span>}</dd>
        <dt>용도</dt>
        <dd>{floor.purps ?? <span className="value-absent">자료 없음</span>}</dd>
        {ledgerFloor && ledgerFloor.parts.length > 0 && <>
          <dt>대장 층별 용도</dt>
          <dd>{ledgerFloor.parts.slice(0, 6).map((p, i) => (
            <span key={i}>{i ? " · " : ""}{p.etc ?? p.purps ?? "용도 미상"} <span className="num">{p.area_m2.toLocaleString("ko-KR")}㎡</span></span>
          ))}{ledgerFloor.parts.length > 6 ? ` 외 ${ledgerFloor.parts.length - 6}행` : ""} <EvidenceBadge kind="실측" /><small> 건축물대장 층별개요(실시간)</small></dd>
        </>}
        {(vacant || floor.status === "uncertain") && <>
          <dt>월 임대 추정</dt>
          <dd>{floor.rent_est_manwon != null
            ? <><b className="num">{manwon(floor.rent_est_manwon)}</b> <EvidenceBadge kind="추정" /><small> 층 전체 금액 · 호가 아님</small></>
            : <span className="value-absent">자료 없음</span>}</dd>
          <dt>평당 월</dt>
          <dd>{floor.rent_per_pyeong != null
            ? <><b className="num">{manwon(floor.rent_per_pyeong)}</b> <EvidenceBadge kind="추정" /></>
            : <span className="value-absent">자료 없음</span>}</dd>
        </>}
        {storesLive && <>
          <dt>상가정보 점포</dt>
          <dd>{floorStores.length > 0
            ? <>{floorStores.slice(0, 6).map((s, i) => (
                <span key={i}>{i ? " · " : ""}{s.name}{s.ind ? <small> {s.ind}</small> : null}{s.ho ? <small> {s.ho}</small> : null}</span>
              ))}{floorStores.length > 6 ? ` 외 ${floorStores.length - 6}곳` : ""}<small> {storesLive.status === "ok" ? "상가정보(실시간)" : "상가정보 스냅샷"} · 현장 미확인</small></>
            : <><span className="value-absent">이 층 기록 없음</span><small> 층을 적지 않은 점포는 여기 안 보입니다</small></>}</dd>
        </>}
        <dt>건물 대표 업종</dt>
        <dd>{twin.representative_industry ?? <span className="value-absent">자료 없음</span>}<small> 직전 업종이 아닙니다</small></dd>
      </dl>
      {floor.units && floor.units.length > 0 && (
        <details className="twin3d-units" open={floor.units.length <= 8}>
          <summary>전유부 호실 {floor.units.length}개 <EvidenceBadge kind="실측" />{storeCol && nMatched > 0 ? <> · 상가정보 영업 기록 {nMatched}호</> : null}</summary>
          <p className="twin3d-note">{storeCol
            ? <>호수·면적·용도는 대장입니다. 상가정보 열은 점포를 같은 층 · 같은 호로 맞춘 결과입니다 — 「기록 없음」은 공실 <b>가능성</b>이지 확인된 공실이 아닙니다(현장 미확인). {storesNote(twin)}</>
            : <>호실별 공실은 모릅니다. 대장의 호수·면적·용도입니다.{storesLive ? <> {storesNote(twin)}</> : null}</>}</p>
          <table>
            <thead><tr><th scope="col">호</th><th scope="col">전용</th>{areas.nPub > 0 && <><th scope="col">공용</th><th scope="col">전용률</th></>}<th scope="col">용도</th>{storeCol && <th scope="col">상가정보</th>}</tr></thead>
            <tbody>
              {floor.units.map((u, i) => (
                <tr key={`${u.ho ?? ""}-${i}`}>
                  <td>{u.ho ?? "미상"}</td>
                  <td className="num">{u.area_m2 != null ? `${u.area_m2.toLocaleString("ko-KR")}㎡` : "—"}</td>
                  {areas.nPub > 0 && <>
                    <td className="num">{u.pub_m2 ? `${u.pub_m2.toLocaleString("ko-KR")}㎡` : "—"}</td>
                    <td className="num">{u.pub_m2 && u.area_m2 ? `${Math.round((u.area_m2 / (u.area_m2 + u.pub_m2)) * 100)}%` : "—"}</td>
                  </>}
                  <td>{u.purps ?? "—"}</td>
                  {storeCol && <td className={`twin3d-store is-${unitStoreState(u)}`}>{u.store
                    ? <>{u.store.name}{u.store.ind ? <small> {u.store.ind}</small> : null}</>
                    : unitStoreState(u) === "none" ? "기록 없음" : <span title={STORE_STATE_LABEL.unknown}>—</span>}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      <FloorPlan twin={twin} floor={floor} />
      <section className="twin3d-sec" aria-label="지번 이력">
        <h4>지번 이력 연대표</h4>
        <HistoryTimeline items={twin.history.items} total={twin.history.items_total} lotBuildings={twin.history.lot_buildings} />
      </section>
      <div className="twin3d-cta">
        {onOpenStreet
          ? <button type="button" className="twin3d-btn" onClick={onOpenStreet}>거리뷰 · 층별 보기</button>
          : <a className="twin3d-btn" href={kakaoRoadviewUrl({ lat: twin.lat, lng: twin.lng })} target="_blank" rel="noopener noreferrer">거리뷰 보기(카카오맵)<span className="sr-only">(새 창)</span></a>}
        {onReview && <button type="button" className="twin3d-btn is-strong" onClick={() => onReview(floor, twin)}>이 자리로 입점 계산 → Posting</button>}
        <button type="button" className="twin3d-btn" aria-pressed={saved} onClick={toggleStop}>{saved ? "✓ 답사 목록에 담음" : "답사 목록에 담기"}</button>
      </div>
    </div>
  );
}

/** 3D 화면 위 — 고른 층의 전용면적을 층 바닥면적과 따로 보인다(2026-11-08). */
function FloorAreaBox({ floor }: { floor: TwinFloor }) {
  const a = areaSummary(floor.units);
  const excl = a.excl;
  return (
    <div className="twin3d-area" role="status" aria-label={`${floor.label} 면적`}>
      <b><span className="twin3d-badge" style={{ background: TWIN_STATUS[floor.status].color }} aria-hidden /> {floor.label} · {TWIN_STATUS[floor.status].label}</b>
      <dl>
        <dt>전용면적</dt>
        <dd>{excl > 0
          ? <><b className="num">{excl.toLocaleString("ko-KR")}㎡</b> · {(excl / PY).toFixed(1)}평 <small>전유부 {a.n}호실</small></>
          : floor.excl_est
            ? <><b className="num">약 {floor.excl_est.m2.toLocaleString("ko-KR")}㎡</b> · {(floor.excl_est.m2 / PY).toFixed(1)}평 <small>추정 {floor.excl_est.low.toLocaleString("ko-KR")}~{floor.excl_est.high.toLocaleString("ko-KR")}㎡</small></>
            : <><span className="value-absent">자료 없음</span> <small>전유부 없음</small></>}</dd>
        {a.contract != null && <>
          <dt>계약면적</dt>
          <dd><span className="num">{a.contract.toLocaleString("ko-KR")}㎡</span> <small>전용률 {a.ratio}%</small></dd>
        </>}
        <dt>층 바닥면적</dt>
        <dd>{floor.area_m2 ? <><span className="num">{floor.area_m2.toLocaleString("ko-KR")}㎡</span> <small>공용 포함</small></> : <span className="value-absent">자료 없음</span>}</dd>
      </dl>
    </div>
  );
}

export default function BuildingTwinDialog(props: BuildingTwinDialogProps) {
  return <BuildingTwinContent key={`${props.districtId}:${props.buildingId}`} {...props} />;
}

function BuildingTwinContent({ buildingId, districtId, districtName, fallback, onClose, onReview, onOpenStreet }: BuildingTwinDialogProps) {
  const [twin, setTwin] = useState<BuildingTwin | null | undefined>(undefined);
  const [selectedLv, setSelectedLv] = useState<number | null>(null);
  const [mode, setMode] = useState<TwinMode>("exterior");
  const [neighbors, setNeighbors] = useState(true);
  const [labels, setLabels] = useState(true);
  const [roadsOn, setRoadsOn] = useState(true);
  const [planOn, setPlanOn] = useState(true);
  const [roadStats, setRoadStats] = useState<RoadLayerStats | null>(null);
  const [flat, setFlat] = useState(false);   // WebGL 실패 → 2D
  const [live, setLive] = useState("");
  const hostRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<TwinSceneHandle | null>(null);
  const needleRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getBuildingTwin(buildingId, districtId, ctrl.signal)
      .then((t) => {
        if (ctrl.signal.aborted) return;
        setTwin(t);
        const first = t?.floors.find((f) => f.status === "vacant_confirmed") ?? t?.floors.find((f) => f.status === "vacant_probable")
          ?? t?.floors.find((f) => f.lv === 1) ?? t?.floors[0];
        setSelectedLv(first ? first.lv : null);
      })
      .catch(() => { if (!ctrl.signal.aborted) setTwin(null); });
    return () => ctrl.abort();
  }, [buildingId, districtId]);

  // 대화상자 — 초점을 안에 가두고 닫으면 돌려준다.
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => prev?.focus?.();
  }, []);
  const onTrapTab = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !boxRef.current) return;
    const nodes = [...boxRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((n) => n.offsetParent !== null || n === document.activeElement);
    if (!nodes.length) return;
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };

  const floorByLv = useMemo(() => new Map(twin?.floors.map((f) => [f.lv, f]) ?? []), [twin]);
  const selected = selectedLv !== null ? floorByLv.get(selectedLv) ?? null : null;
  useReportCapture("pageFloor", selected ? {
    districtId, buildingId, label: selected.label, area: selected.area_m2, areaSource: selected.area_source,
    status: TWIN_STATUS[selected.status].label, unitId: selected.unit_id,
  } : null);
  const select = (lv: number, focus = true) => {
    setSelectedLv(lv);
    const f = floorByLv.get(lv);
    if (f) setLive(`${f.label} ${TWIN_STATUS[f.status].label}`);
    handleRef.current?.selectFloor(lv, focus);
  };
  const selectRef = useRef(select);
  const selectedLvRef = useRef(selectedLv);
  const modeRef = useRef(mode);
  const neighborsRef = useRef(neighbors);
  const labelsRef = useRef(labels);
  const roadsOnRef = useRef(roadsOn);
  const planOnRef = useRef(planOn);
  useEffect(() => {
    selectRef.current = select;
    selectedLvRef.current = selectedLv;
    modeRef.current = mode;
    neighborsRef.current = neighbors;
    labelsRef.current = labels;
    roadsOnRef.current = roadsOn;
    planOnRef.current = planOn;
  });

  // 장면 — 응답이 오면 한 번 만들고, 언마운트 때 전부 해제한다. 3D 코드는 여기서만 받는다.
  useEffect(() => {
    if (!twin || flat || !hostRef.current || twin.ring.length < 3) return;
    let alive = true;
    const host = hostRef.current;
    import("./TwinScene").then(({ createTwinScene }) => {
      if (!alive) return;
      try {
        const handle = createTwinScene(host, twin, {
          onSelect: (lv) => selectRef.current(lv, false),
          onEdge: (dir) => setLive(dir > 0 ? "맨 위층입니다" : "맨 아래층입니다"),
          onHover: (hit) => {
            const tip = tipRef.current;
            if (!tip) return;
            if (!hit) { tip.hidden = true; return; }
            tip.hidden = false;
            tip.textContent = `${hit.floor.label} · ${TWIN_STATUS[hit.floor.status].label}${hit.floor.area_m2 ? ` · ${hit.floor.area_m2.toLocaleString("ko-KR")}㎡` : ""}`;
            tip.style.transform = `translate(${hit.x + 12}px, ${hit.y + 12}px)`;
          },
          onAzimuth: (deg) => { if (needleRef.current) needleRef.current.style.transform = `rotate(${deg}deg)`; },
          onContextLost: () => { if (alive) setFlat(true); },
        });
        handleRef.current = handle;
        host.dataset.ready = "1";
        handle.selectFloor(selectedLvRef.current);
        handle.setMode(modeRef.current);
        handle.setNeighbors(neighborsRef.current);
        handle.setLabels(labelsRef.current);
        handle.setRoads(roadsOnRef.current);
        handle.setPlan(planOnRef.current);
        setRoadStats(handle.roadStats);
      } catch {
        setFlat(true);
      }
    }).catch(() => { if (alive) setFlat(true); });
    return () => {
      alive = false;
      handleRef.current?.dispose();
      handleRef.current = null;
      setRoadStats(null);
      delete host.dataset.ready;
    };
  }, [twin, flat]);
  useEffect(() => { handleRef.current?.setMode(mode); }, [mode]);
  useEffect(() => { handleRef.current?.setNeighbors(neighbors); }, [neighbors]);
  useEffect(() => { handleRef.current?.setLabels(labels); }, [labels]);
  useEffect(() => { handleRef.current?.setRoads(roadsOn); }, [roadsOn]);
  useEffect(() => { handleRef.current?.setPlan(planOn); }, [planOn]);

  const onViewKey = (e: React.KeyboardEvent) => {
    if (handleRef.current?.handleKey(e.key)) e.preventDefault();
  };

  const vacantFloors = twin?.floors.filter((f) => isVacantStatus(f.status)) ?? [];
  const hasFloorBasis = !!twin?.floors.some((f) => f.status !== "unknown");
  const title = twin?.name ?? fallback.name;
  return createPortal(
    <div className="twin3d-modal" onClick={onClose}>
      <div className="twin3d-box" role="dialog" aria-modal="true" aria-label={`${title} 3D 트윈`} ref={boxRef}
        onClick={(e) => e.stopPropagation()} onKeyDown={onTrapTab}>
        <header className="twin3d-head">
          <div>
            <h2>{title}</h2>
            <p>{twin?.road_addr ?? ""}{districtName ? ` · ${districtName}` : ""}</p>
          </div>
          <button type="button" ref={closeRef} className="twin3d-close" aria-label="3D 트윈 닫기" onClick={onClose}>✕</button>
        </header>
        {twin === undefined && <div className="twin3d-status" role="status">트윈 자료를 불러오는 중…</div>}
        {twin === null && (
          <div className="twin3d-status" role="status">
            <span className="value-absent">자료 없음</span> — 이 건물의 트윈 자료가 없습니다. 2D 층 근거로 보여 드립니다.
            <div className="twin3d-flat"><FloorStack b={fallback} /></div>
          </div>
        )}
        {twin && (
          <div className="twin3d-grid">
            <aside className="twin3d-left" aria-label="빈 층과 건물 정보">
              <section className="twin3d-sec">
                <h4>빈 층 {vacantFloors.length}개</h4>
                {vacantFloors.length === 0
                  ? <p className="twin3d-note">{twin.vac_class === "unknown" ? "근거가 없어 판정하지 않은 건물입니다. 비었다는 뜻이 아닙니다."
                    : !hasFloorBasis ? "호실·점포 수로는 빈 곳이 있어 보이지만 층 근거가 없어 어느 층인지 판정하지 못했습니다. 집합건물에서 흔합니다."
                      : "매물 목록에 오른 빈 층이 없습니다."}</p>
                  : (
                    <ul className="twin3d-vac">
                      {vacantFloors.map((f) => (
                        <li key={f.lv}>
                          <button type="button" aria-pressed={f.lv === selectedLv} onClick={() => select(f.lv)}>
                            <span className="twin3d-badge" style={{ background: TWIN_STATUS[f.status].color }} aria-hidden />
                            <b>{f.label}</b> <span>{TWIN_STATUS[f.status].label}</span>
                            <small>{f.area_m2 ? `${(f.area_m2 / PY).toFixed(1)}평` : "면적 자료 없음"}{f.rent_est_manwon != null ? ` · 월 ${manwon(f.rent_est_manwon)} 추정` : ""}</small>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
              </section>
              <section className="twin3d-sec">
                <h4>건물 정보</h4>
                <dl className="twin3d-dl">
                  <dt>층수</dt>
                  <dd>지상 {twin.floors_above}층{twin.floors_below ? ` · 지하 ${twin.floors_below}층` : ""} <EvidenceBadge kind="실측" />
                    {twin.floors_conflict && <small> 층수 원천이 서로 달라 큰 값으로 그렸습니다</small>}</dd>
                  <dt>높이</dt>
                  <dd>{twin.height_m != null ? `${twin.height_m}m` : <span className="value-absent">자료 없음</span>} <EvidenceBadge kind={twin.height_source === "vworld" ? "실측" : "추정"} />
                    <small>{twin.height_source === "vworld" ? " V-World" : " 층수 × 3.3m"}</small></dd>
                  <dt>사용승인</dt>
                  <dd>{ymd(twin.approval_date) ?? <span className="value-absent">자료 없음</span>}</dd>
                  <dt>승강기</dt>
                  <dd>{twin.ledger_live?.status === "ok" && twin.ledger_live.elevators
                    ? <>승용 {twin.ledger_live.elevators.passenger} · 비상용 {twin.ledger_live.elevators.emergency}대 <EvidenceBadge kind="실측" /><small> 건축물대장 표제부(실시간){(twin.ledger_live.title?.n_titles ?? 0) > 1 ? " · 같은 지번 주건축물 기준" : ""}</small></>
                    : <><span className="value-absent">자료 없음</span><small> {ledgerNote(twin.ledger_live)}</small></>}</dd>
                  {twin.lot_buildings && twin.lot_buildings > 1 ? <><dt>같은 지번</dt><dd>건물 {twin.lot_buildings}동</dd></> : null}
                </dl>
              </section>
              <RoadCheckSection name={title ?? "건물"} lat={twin.lat} lng={twin.lng} check={twin.road_check} source={twin.roads_source}
                roadCount={twin.roads?.length ?? 0} stats={flat ? null : roadStats} sceneOff={flat}
                roadsOn={roadsOn} onToggle={setRoadsOn} error={twin.roads_error} />
              <section className="twin3d-sec" aria-label="공실률 기준별 표">
                <h4>공실률은 기준마다 다릅니다</h4>
                {twin.range.min === null
                  ? <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 상업층 판정 근거가 없습니다.</p>
                  : <>
                      <p className="twin3d-range num">{twin.range.min === twin.range.max ? `${twin.range.min}%` : `${twin.range.min}% ~ ${twin.range.max}%`} <EvidenceBadge kind="계산" /></p>
                      <table className="twin3d-stats">
                        <thead><tr><th scope="col">기준</th><th scope="col">공실/전체</th><th scope="col">공실률</th></tr></thead>
                        <tbody>
                          {twin.vacancy_stats.map((s) => (
                            <tr key={s.basis} title={s.note}>
                              <th scope="row">{s.label}</th>
                              <td className="num">{s.vacant.toLocaleString("ko-KR")}/{s.total.toLocaleString("ko-KR")}</td>
                              <td className="num">{s.rate_pct != null ? `${s.rate_pct}%` : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="twin3d-note">판정 스냅샷{asOf(twin) ? ` · 기준일 ${asOf(twin)}` : ""}. 현장 라벨이 없어 정확도는 검정하지 못했습니다.</p>
                    </>}
              </section>
            </aside>

            <div className="twin3d-view">
              {!flat
                ? <div className="twin3d-canvas" ref={hostRef} tabIndex={0} onKeyDown={onViewKey} data-testid="twin-canvas"
                    role="application"
                    aria-label={`${title} 3D 장면. 화살표 키로 돌리고 플러스·마이너스로 확대, PageUp·PageDown 으로 층을 옮기고 Home 으로 처음 시점으로 돌아갑니다.`} />
                : (
                  <div className="twin3d-flat" role="status">
                    <p className="twin3d-note">이 기기에서는 3D 를 그릴 수 없어 2D 층 목록으로 보여 드립니다.</p>
                    <FloorStack b={fallback} />
                  </div>
                )}
              {!flat && <div className="twin3d-tip" ref={tipRef} hidden />}
              {!flat && mode === "vacant" && vacantFloors.length === 0 && <div className="twin3d-hint" role="status">빈 층으로 판정된 층이 없습니다{hasFloorBasis ? "" : " — 층 근거가 없습니다"}.</div>}
              {!flat && (
                <div className="twin3d-tools">
                  <div className="twin3d-seg" role="group" aria-label="보기 모드">
                    {MODES.map((m) => <button key={m.key} type="button" aria-pressed={mode === m.key} onClick={() => setMode(m.key)}>{m.label}</button>)}
                  </div>
                  <div className="twin3d-seg" role="group" aria-label="장면 표시">
                    <button type="button" aria-pressed={neighbors} onClick={() => setNeighbors((v) => !v)}>주변 건물</button>
                    <button type="button" aria-pressed={labels} onClick={() => setLabels((v) => !v)}>층 라벨</button>
                    <button type="button" aria-pressed={planOn} onClick={() => setPlanOn((v) => !v)}>개략 배치</button>
                    <button type="button" onClick={() => handleRef.current?.resetView()}>시점 초기화</button>
                  </div>
                </div>
              )}
              <div className="twin3d-elev" role="group" aria-label="층 이동">
                {twin.floors.map((f) => (
                  <button key={f.lv} type="button" aria-pressed={f.lv === selectedLv} aria-label={`${f.label} ${TWIN_STATUS[f.status].label}`} onClick={() => select(f.lv)}>
                    <span className="twin3d-badge" style={{ background: TWIN_STATUS[f.status].color }} aria-hidden />{f.label}
                  </button>
                ))}
              </div>
              {!flat && selected && <FloorAreaBox floor={selected} />}
              {!flat && <div className="twin3d-compass" title="위쪽 바늘이 진북입니다" aria-hidden><span ref={needleRef}><i>N</i></span></div>}
              <div className="twin3d-legend">
                {LEGEND.map((k) => <span key={k} title={TWIN_STATUS[k].rule}><i style={{ background: TWIN_STATUS[k].color }} />{TWIN_STATUS[k].label}</span>)}
                <em>형상: V-World 외곽선 · 층수: 대장 · 창호·내부는 실측 아님</em>
                {!flat && (twin.roads?.length ?? 0) > 0 && <em className="twin3d-osm">도로: © OpenStreetMap 기여자 (ODbL) · 폭은 추정</em>}
              </div>
              <div className="sr-only" aria-live="polite">{live}</div>
            </div>

            <aside className="twin3d-right" aria-label="선택한 층">
              {selected
                ? <FloorDetail twin={twin} floor={selected} districtId={districtId} onReview={onReview} onOpenStreet={onOpenStreet} />
                : <p className="twin3d-note">층을 고르세요.</p>}
              {twin.notes.length > 0 && (
                <details className="twin3d-notes">
                  <summary>이 화면의 한계</summary>
                  <ul>{twin.notes.map((n) => <li key={n}>{n}</li>)}</ul>
                </details>
              )}
            </aside>

            {/* 캔버스 대체 표 — 스크린리더는 층 상태를 여기서 읽는다 */}
            <table className="sr-only">
              <caption>층별 상태</caption>
              <thead><tr><th>층</th><th>상태</th><th>면적</th></tr></thead>
              <tbody>{twin.floors.map((f) => <tr key={f.lv}><td>{f.label}</td><td>{TWIN_STATUS[f.status].label}</td><td>{f.area_m2 != null ? `${f.area_m2}㎡` : "자료 없음"}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
