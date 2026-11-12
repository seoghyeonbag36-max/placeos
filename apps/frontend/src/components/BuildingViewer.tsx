import { useEffect, useState } from "react";
import { placeFloors, approxFloors, stackBasis, type FloorKind, type ViewerBuilding } from "./buildingFloors";
// 건물 상세 — 2D 층 근거와 공실 이력. 확인되지 않은 이력은 채우지 않는다.
import HistoryTimeline from "@/components/twin/HistoryTimeline";
import { getBuildingHistory, type BuildingHistory } from "@/lib/api";
import { historySummary } from "@/lib/founderChecks";
import { kakaoMapUrl } from "@/lib/externalMap";
import { dateText, lastClosed, type HistoryItem } from "@/lib/twinGeometry";
import "./BuildingViewer.css";

const OCCUPIED = "#22B07D";  // 영업(녹색)
const UNCERTAIN = "#F2B441"; // 층 미상 점포가 앉을 수 있는 층
const NON_COM = "#C7D0DB";   // 비상업 층 — 공실률 분모 밖
/** 2D 층 스택 — 위가 꼭대기 층이다(건물과 같은 방향으로 읽히도록 역순으로 그린다). */
export function FloorStack({ b }: { b: ViewerBuilding }) {
  const kinds = placeFloors(b) ?? approxFloors(b);
  const colorOf = (k: FloorKind) =>
    k === "occupied" ? OCCUPIED
      : k === "uncertain" ? UNCERTAIN
        : k === "noncom" ? NON_COM
          : b.statusColor;
  const labelOf = (k: FloorKind) =>
    k === "occupied" ? "영업" : k === "uncertain" ? "층 미상" : k === "noncom" ? "비상업" : "공실";

  return (
    <div className="fstack">
      {kinds.map((_, i) => {
        // 배열은 1층부터인데 화면은 꼭대기부터 그린다 — 건물과 같은 방향으로 읽히도록.
        const floorNo = kinds.length - i;
        const kind = kinds[floorNo - 1];
        return (
          <div key={floorNo} className={"fstack-row " + kind}>
            <span className="fstack-no">{floorNo}F</span>
            <span className="fstack-bar" style={{ background: colorOf(kind) }} />
            <span className="fstack-lb">{labelOf(kind)}</span>
          </div>
        );
      })}
    </div>
  );
}

const ABSENT = "확인 자료 없음";

/** 지번 인허가 이력. 공실 기간은 이 자료로 답할 수 없어 비워 둔다 — 폐업일 다음 날부터 비었다는 근거가 없다. */
function VacancyHistory({ buildingId }: { buildingId?: string | null }) {
  const [state, setState] = useState<{ id: string; data: BuildingHistory | null } | null>(null);
  useEffect(() => {
    if (!buildingId) return;
    let live = true;
    getBuildingHistory(buildingId)
      .then((data) => { if (live) setState({ id: buildingId, data }); })
      .catch(() => { if (live) setState({ id: buildingId, data: null }); });
    return () => { live = false; };
  }, [buildingId]);
  const loading = !!buildingId && state?.id !== buildingId;
  const data = state && state.id === buildingId ? state.data : null;
  const items: HistoryItem[] = (data?.history ?? []).map((r) => ({
    start: r.start_date, end: r.end_date, industry: r.industry_type ?? null, name: r.business_name ?? null,
  })).sort((a, c) => (c.start ?? "").localeCompare(a.start ?? ""));
  const closed = lastClosed(items);
  // 이 자리 영업 이력 요약(2026-11-12 사용자 요청 · N4) — 닫은 곳만 센 값이라 생존율이 아니다
  const sum = historySummary(data?.history ?? []);
  return (
    <section aria-label="공실 이력">
      <h3>공실 이력</h3>
      {!loading && sum.total > 0 && <p className="bv-history-sum" role="note">
        이 지번에서 가게 <b>{sum.total}곳</b>이 거쳐 갔어요
        {sum.medianYears != null && <> · 2000년 이후 닫은 곳의 영업기간 중앙 <b>{sum.medianYears}년</b> · 3년 안에 닫은 곳 {sum.within3y}곳</>}.
        <small> 인허가 업종만(소매 · 사무 없음) · 닫은 곳만 센 값이라 생존율이 아니에요{data?.history_source === "localdata_lot" ? " · 같은 지번의 다른 건물 이력이 섞여 있어요" : ""}.</small>
      </p>}
      <dl><dt>직전 업종 (지번 단위 · 층 불명)</dt><dd>{loading ? "불러오는 중…" : closed?.industry ?? ABSENT}</dd>
        <dt>폐업일</dt><dd>{loading ? "불러오는 중…" : dateText(closed?.end) ?? ABSENT}</dd>
        <dt>공실 기간</dt><dd>{ABSENT}</dd></dl>
      {items.length > 0
        ? <HistoryTimeline items={items} lotBuildings={data?.lot_buildings} />
        : !loading && <p>이 공실에 귀속된 영업·폐업 이력이 아직 제공되지 않습니다.</p>}
    </section>
  );
}

/** 층 근거와 확인 가능한 이력을 함께 표시한다. */
export default function BuildingViewer({ b }: { b: ViewerBuilding }) {
  const measured = stackBasis(b) === "measured";
  return (
    <div className="bviewer">
      <div className="bviewer-cols">
        <div className="bviewer-stack">
          <FloorStack b={b} />
        </div>
        <div className="bviewer-street">
          <VacancyHistory buildingId={b.buildingId} />
        </div>
      </div>
      {b.center && (
        <p className="bviewer-links">
          <a href={kakaoMapUrl(b.center, b.name)} target="_blank" rel="noopener noreferrer">
            카카오맵에서 위치 보기<span className="sr-only">(새 창)</span>
          </a>
        </p>
      )}
      <div className="bviewer-legend">
        {measured ? (
          <>
            <b style={{ color: OCCUPIED }}>영업</b> = 점포·인허가·학원 등록으로 확인된 층
            ({b.occFloors?.join("·") || "없음"})
            {b.unknownN ? <> · <b style={{ color: UNCERTAIN }}>층 미상</b> = 층을 모르는 점포 {b.unknownN}곳이 앉을 수 있는 층</> : null}
            {" · "}<b style={{ color: b.statusColor }}>공실</b>
            {" · "}<b style={{ color: NON_COM }}>비상업</b> = 공실률 분모 밖
            {" · "}상업 {b.comFloors?.length}개 층 중 {b.active}개 영업
            {b.floors ? ` · 지상 ${b.floors}층` : ""}
            <br />
            <span className="dim">근거: 건축물대장 층별개요 + 상가정보·인허가·나이스 학원 층 표기 — 층 배치는 실측이다</span>
          </>
        ) : (
          <>
            <b style={{ color: OCCUPIED }}>영업</b>(점유율 환산) · <b style={{ color: b.statusColor }}>공실</b>(추정)
            {" · "}{b.active}/{b.capacity}호{b.floors ? ` · 지상 ${b.floors}층` : ""}
            <br />
            <span className="dim">
              이 건물은 층 근거가 없어 <b>아래부터 채운 근사</b>다 — 실제 공실 층과 다를 수 있다
            </span>
          </>
        )}
      </div>
    </div>
  );
}
