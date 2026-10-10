// 건물 상세 — 2D 층 근거와 공실 이력. 확인되지 않은 이력은 채우지 않는다.
import { kakaoMapUrl } from "@/lib/externalMap";
import "./BuildingViewer.css";

export interface ViewerBuilding {
  name: string;
  capacity: number;    // 상가 수용 **호** 수(분모). 층 근거가 있으면 상업 **층** 수
  active: number;      // 영업 **호** 수(분자)
  floors?: number;     // 건축물대장 지상 **층** 수 — 스택의 실제 높이
  statusColor: string; // 공실 상태색
  statusLabel?: string;
  center?: { lat: number; lng: number };   // 건물 위치
  // ── 층 실배치 근거 (gold page_building_master.geojson, 층 근거가 있는 건물만) ──
  comFloors?: number[];
  occFloors?: number[];
  unknownN?: number;
}

const OCCUPIED = "#22B07D";  // 영업(녹색)
const UNCERTAIN = "#F2B441"; // 층 미상 점포가 앉을 수 있는 층
const NON_COM = "#C7D0DB";   // 비상업 층 — 공실률 분모 밖
const MAX_STACK = 20;        // 렌더 상한 (실측 p99 = 20층, 최대 37층)

type FloorKind = "occupied" | "uncertain" | "vacant" | "noncom";

/** 층 번호 → 상태. 층 근거가 없으면 null 을 돌려 근사 렌더로 폴백시킨다.
 *  규칙은 파이프라인(build_page_master._aggregate)과 **같아야** 한다 — 갈라지면
 *  스택의 녹색 층 수와 카드의 공실률이 서로 안 맞는다. */
export function placeFloors(b: ViewerBuilding): FloorKind[] | null {
  const com = b.comFloors;
  if (!com || com.length === 0) return null;

  const occ = new Set(b.occFloors ?? []);
  const comSet = new Set(com);
  const top = Math.max(b.floors || 0, ...com);
  const stack = Math.max(1, Math.min(top, MAX_STACK));

  // 층 미상 점포는 빈 상업층에 낮은 층부터 앉힌다 — 파이프라인과 같은 규칙.
  const uncertain = new Set<number>();
  let spare = b.unknownN ?? 0;
  for (const f of com) {
    if (spare <= 0) break;
    if (!occ.has(f)) { uncertain.add(f); spare -= 1; }
  }

  return Array.from({ length: stack }, (_, i) => {
    const floorNo = i + 1;
    if (!comSet.has(floorNo)) return "noncom";
    if (occ.has(floorNo)) return "occupied";
    if (uncertain.has(floorNo)) return "uncertain";
    return "vacant";
  });
}

/** 층 근거가 없는 건물 — 근사. 점유율만큼 아래부터 채운다. */
function approxFloors(b: ViewerBuilding): FloorKind[] {
  const stack = Math.max(1, Math.min(b.floors || b.capacity, MAX_STACK));
  const ratio = b.capacity > 0 ? Math.min(b.active / b.capacity, 1) : 0;
  const occ = Math.max(0, Math.min(Math.round(stack * ratio), stack));
  return Array.from({ length: stack }, (_, i) => (i < occ ? "occupied" : "vacant"));
}

/** 스택이 실배치인지 근사인지 — 캡션이 근거를 밝히는 데 쓴다. */
export function stackBasis(b: ViewerBuilding): "measured" | "approx" {
  return b.comFloors && b.comFloors.length > 0 ? "measured" : "approx";
}

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
          <section aria-label="공실 이력">
            <h3>공실 이력</h3>
            <dl><dt>이전 업종</dt><dd>확인 자료 없음</dd>
              <dt>폐업일</dt><dd>확인 자료 없음</dd>
              <dt>공실 기간</dt><dd>확인 자료 없음</dd></dl>
            <p>이 공실에 귀속된 영업·폐업 이력이 아직 제공되지 않습니다.</p>
          </section>
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
            <b style={{ color: OCCUPIED }}>영업</b> = 점포·인허가로 확인된 층
            ({b.occFloors?.join("·") || "없음"})
            {b.unknownN ? <> · <b style={{ color: UNCERTAIN }}>층 미상</b> = 층을 모르는 점포 {b.unknownN}곳이 앉을 수 있는 층</> : null}
            {" · "}<b style={{ color: b.statusColor }}>공실</b>
            {" · "}<b style={{ color: NON_COM }}>비상업</b> = 공실률 분모 밖
            {" · "}상업 {b.comFloors?.length}개 층 중 {b.active}개 영업
            {b.floors ? ` · 지상 ${b.floors}층` : ""}
            <br />
            <span className="dim">근거: 건축물대장 층별개요 + 상가정보 층 표기 — 층 배치는 실측이다</span>
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
