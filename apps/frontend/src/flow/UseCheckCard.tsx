/**
 * R4 자리 상세 — 「이 층에 내 업종이 들어갈 수 있나」 입점 점검 카드(인계 문서 2-E · 2026-11-15).
 *
 * 대장 용도코드 × 필지 용도지역 × 토지이음 행위제한(`GET /buildings/{id}/use-check`)을 다섯 갈래로 보인다.
 * 허가 판정이 아니다 — 「입점 가능」「허가됨」이라 쓰지 않고, 늘 출처·기준일·「관할 구청 확인」을 함께 보인다.
 */
import { getUseCheck, type UseCheckItem } from "@/lib/api";
import { useLoad } from "./data";
import { USE_CHECK_LABEL } from "./useCheckLabels";
import { Details, TextButton, WarnLine } from "./ui";

const ITEM_LABEL: Record<UseCheckItem["status"], string> = { ok: "맞음", check: "확인", blocked: "막힘", missing: "자료 없음" };

export function UseCheckCard({ buildingId, districtId, floor, areaM2, purps, industryKey }: {
  buildingId: string; districtId: string; floor: number; areaM2: number | null; purps: string | null; industryKey: string;
}) {
  const load = useLoad(`use-check:${districtId}:${buildingId}:${floor}:${industryKey}`,
    () => getUseCheck(buildingId, districtId, floor, industryKey, areaM2, purps));
  if (load.status === "loading") return <p className="fl-note" role="status">건축물대장과 토지이음 자료를 맞춰 보는 중…</p>;
  if (load.status === "error") {
    return <p className="fl-note">입점 점검 자료를 불러오지 못했어요. <TextButton onClick={load.retry}>다시 시도</TextButton></p>;
  }
  const r = load.data;
  const open = r.checks.filter((c) => c.status !== "ok");
  const label = USE_CHECK_LABEL[r.regulation_status];
  return (
    <section className="fl-usecheck" aria-label="입점 점검">
      <p className={`fl-usecheck-status is-${r.regulation_status}`}>{label}</p>
      {/* 배지와 같은 이름으로 시작하는 문장은 그 이름을 떼고 보인다(「확인 필요 — …」 두 번 읽히지 않게) */}
      <p className="fl-usecheck-head">{r.headline.startsWith(label) ? r.headline.slice(label.length).replace(/^\s*—\s*/, "") : r.headline}</p>
      {open.length > 0 && (
        <ul className="fl-facts">
          {open.map((c) => <li key={c.item}><b>{c.item}</b> · {ITEM_LABEL[c.status]}: {c.reason}</li>)}
        </ul>
      )}
      <Details summary="점검 항목 전부 · 출처">
        <ul className="fl-facts">
          {r.checks.map((c) => (
            <li key={c.item}>
              <b>{c.item}</b> · {ITEM_LABEL[c.status]}: {c.reason}{" "}
              <span className="fl-muted">({c.source}{c.source_date ? ` · ${c.source_date}` : ""})</span>
            </li>
          ))}
        </ul>
        <p className="fl-note">{r.note}</p>
        <p className="fl-source">
          {r.sources.map((s, i) => (
            <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a></span>
          ))}
        </p>
      </Details>
      <WarnLine>허가 판정이 아니에요. 영업신고·용도변경이 되는지는 관할 구청(건축과·위생과)에서 정해져요.</WarnLine>
    </section>
  );
}
