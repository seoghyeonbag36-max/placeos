import type { ReactNode } from "react";
import type { CompareColumn, FactCell, FactRow, FactSource } from "@/lib/districtCompare";
import "./DistrictCompare.css";

/** 줄 근거 배지 — 흐름 배지(대장 실측 · 추정 · 관측)와 같은 말을 쓴다(설계서 5판 §8) */
const SOURCE_LABEL: Record<FactSource, string> = { model: "모델", obs: "관측", real: "대장 실측", est: "추정" };

/**
 * 상권 2~3곳을 같은 줄로 나란히 — 흐름 「상권 나란히 보기」와 지도 탐색 Platform 「상권 비교」가 같이 쓴다.
 * 값은 lib/districtCompare 가 응답에서 옮겨 적은 그대로다. 이긴 쪽을 칠하지 않는다(종합 점수 없음 — 그 파일 머리말).
 * 폰에서 열 셋이 넘치면 표 안에서만 가로로 넘긴다(첫 열 고정) — 화면 전체가 가로로 밀리지 않는다(F-14).
 */
export default function DistrictCompareTable({ columns, rows, caption, action }: {
  columns: CompareColumn[];
  rows: FactRow[];
  /** 표 제목(화면에는 숨기고 읽어 준다) */
  caption: string;
  /** 열 아래 행동(「빈 자리 보기」 · 「이 상권 보기」) — 없으면 그 줄을 그리지 않는다 */
  action?: (col: CompareColumn) => ReactNode;
}) {
  return (
    <div className="dcmp-scroll" role="region" aria-label={`${caption} — 옆으로 넘겨 보기`} tabIndex={0}>
      <table className={`dcmp is-${columns.length}`}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <td className="dcmp-corner" />
            {columns.map((c) => (
              <th key={c.id} scope="col" className="dcmp-head">
                <span className="dcmp-name">{c.name}</span>
                <span className="dcmp-gu">{c.gu}</span>
                {c.caveat && <span className="dcmp-caveat" title={c.caveat}>▣ 직접 비교 주의</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <th scope="row" className="dcmp-label">
                <span>{r.label}</span>
                {r.source && <span className={`dcmp-src is-${r.source}`}>{SOURCE_LABEL[r.source]}</span>}
              </th>
              {r.cells.map((c, i) => <td key={columns[i]?.id ?? i}><Cell cell={c} /></td>)}
            </tr>
          ))}
          {action && (
            <tr className="dcmp-actions">
              <th scope="row" className="dcmp-label"><span className="sr-only">이동</span></th>
              {columns.map((c) => <td key={c.id}>{action(c)}</td>)}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Cell({ cell }: { cell: FactCell }) {
  if (cell.state === "loading") return <span className="skeleton dcmp-skel" role="status" aria-label="불러오는 중" />;
  if (cell.state !== "ready") return <span className={`dcmp-none${cell.state === "error" ? " is-error" : ""}`}>{cell.text}</span>;
  return <>
    <b className="dcmp-value">{cell.text}</b>
    {cell.sub && <span className="dcmp-sub">{cell.sub}</span>}
  </>;
}
