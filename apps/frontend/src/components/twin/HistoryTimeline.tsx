import { useState } from "react";
import { dateText, lastClosed, timelineScale, type HistoryItem } from "@/lib/twinGeometry";
import "./HistoryTimeline.css";

const SHOWN = 5;

/** 지번 인허가 이력 연대표 — 지번 단위 · 층 불명. 공통 눈금 위 막대 + 요약 + 펼치기. */
export default function HistoryTimeline({ items, total, lotBuildings, nowYear = new Date().getFullYear() + new Date().getMonth() / 12 }: {
  items: HistoryItem[]; total?: number; lotBuildings?: number | null; nowYear?: number;
}) {
  const [open, setOpen] = useState(false);
  if (!items.length) {
    return <p className="htl-empty"><span className="value-absent">자료 없음</span> — 이 지번의 인허가 이력이 없습니다. 인허가 대상 업종만 기록되므로, 영업한 적이 없다는 뜻은 아닙니다.</p>;
  }
  const scale = timelineScale(items, nowYear);
  const closed = lastClosed(items);
  const rows = open ? scale.rows : scale.rows.slice(0, SHOWN);
  const count = total ?? items.length;
  return (
    <div className="htl">
      <p className="htl-sum">
        업소 <b className="num">{count}</b>곳 기록
        {closed && <> · 최근 폐업 {dateText(closed.end)} <b>{closed.industry ?? "업종 미상"}</b></>}
      </p>
      <p className="htl-note">지번 단위 인허가 이력입니다. 어느 층·호실인지 모르고, 공실 기간을 뜻하지 않습니다
        {lotBuildings && lotBuildings > 1 ? ` · 이 지번에 건물 ${lotBuildings}동이 있어 어느 동인지도 모릅니다` : ""}.</p>
      <ol className="htl-rows">
        {rows.map((r, i) => (
          <li key={`${r.name ?? ""}-${r.start ?? ""}-${i}`}>
            <span className="htl-name"><b>{r.name ?? "상호 미상"}</b> {r.industry ?? ""}</span>
            <span className="htl-date num">{dateText(r.start) ?? "시작 미상"} ~ {r.open ? "폐업 기록 없음" : dateText(r.end)}</span>
            {r.left !== null && r.width !== null && (
              <span className="htl-track" aria-hidden>
                <span className={"htl-bar" + (r.open ? " is-open" : "")} style={{ left: `${r.left * 100}%`, width: `${Math.min(r.width, 1 - r.left) * 100}%` }} />
              </span>
            )}
          </li>
        ))}
      </ol>
      <div className="htl-axis num" aria-hidden><span>{scale.min}</span><span>{Math.floor(scale.max)}</span></div>
      {scale.rows.length > SHOWN && (
        <button type="button" className="htl-more" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? "접기" : `${scale.rows.length - SHOWN}곳 더 보기`}
        </button>
      )}
      {count > items.length && <p className="htl-note">최근 {items.length}곳까지만 보여 줍니다.</p>}
    </div>
  );
}
