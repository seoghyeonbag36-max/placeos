import { placeFloors, approxFloors, stackBasis, type FloorKind, type ViewerBuilding } from "./buildingFloors";
// 건물 상세 — 2D 층 근거와 공실 이력. 확인되지 않은 이력은 채우지 않는다.
import { kakaoMapUrl } from "@/lib/externalMap";
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
