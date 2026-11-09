import { useEffect, useState } from "react";
import { getBuildingEnergy, type BuildingEnergy } from "@/lib/api";
import EvidenceBadge from "@/components/EvidenceBadge";
import { monthSpan, ymLabel } from "@/lib/twinEnergy";

const fmt = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
/** 차트 좌표(viewBox) — 너비는 화면에 맞춰 늘어난다 */
const W = 320, H = 120, PAD_L = 4, PAD_R = 4, PAD_T = 18, PAD_B = 18;

/**
 * 월별 가스 사용량(2026-11-09 사용자 요청) — 트윈 건물 지번의 건축HUB 건물에너지정보를 따로 불러 막대로 보인다.
 * 트윈 창은 이 조회를 기다리지 않는다. 값이 없는 달은 막대를 그리지 않는다(0 이 아니라 「자료 없음」).
 * 지번 합계 · 가스는 난방 계절을 탄다 — 공실 판정에 쓰지 않는 표시용이다.
 */
export default function EnergySection({ buildingId }: { buildingId: string }) {
  const [state, setState] = useState<{ id: string; data: BuildingEnergy | null; failed: boolean } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getBuildingEnergy(buildingId, "gas", ctrl.signal)
      .then((data) => setState({ id: buildingId, data, failed: false }))
      .catch(() => { if (!ctrl.signal.aborted) setState({ id: buildingId, data: null, failed: true }); });
    return () => ctrl.abort();
  }, [buildingId]);

  const cur = state?.id === buildingId ? state : null;
  if (!cur) return <p className="twin3d-note" role="status">월별 가스 사용량을 불러오는 중…</p>;
  const e = cur.data;
  if (!e || cur.failed) return <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 가스 사용량 조회가 안 됐습니다.</p>;
  if (e.status !== "ok") return <EnergyWhy e={e} />;
  if (e.months.length === 0) {
    return (
      <p className="twin3d-note"><span className="value-absent">자료 없음</span> — {e.window ? `${ymLabel(e.window[0])}~${ymLabel(e.window[1])} ` : ""}이 지번의 가스 사용량
        기록이 없습니다. 단독주택 · 200세대 미만 공동주택은 원천에 없고, 기록이 없다는 것이 「가스를 안 썼다」는 뜻은 아닙니다.</p>
    );
  }

  const span = monthSpan(e.window ?? [e.months[0].ym, e.months[e.months.length - 1].ym]);
  const byYm = new Map(e.months.map((m) => [m.ym, m]));
  const max = Math.max(...e.months.map((m) => m.qty), 0) || 1;
  const slot = (W - PAD_L - PAD_R) / span.length;
  const bw = Math.min(24, Math.max(2, slot - 2));          // 막대 사이 2px 틈 · 굵기 24px 상한
  const ph = H - PAD_T - PAD_B;
  const last = e.months[e.months.length - 1];
  const unit = e.unit ? ` ${e.unit}` : "";
  const multi = e.months.some((m) => m.n > 1);
  const shown = hover ? byYm.get(hover) : null;
  const bar = (x: number, h: number) => {
    const r = Math.min(4, bw / 2, h);                       // 위쪽 끝만 4px 둥글게 · 바닥은 각지게
    const y = PAD_T + ph - h, b = PAD_T + ph;
    return `M${x} ${b}V${y + r}Q${x} ${y} ${x + r} ${y}H${x + bw - r}Q${x + bw} ${y} ${x + bw} ${y + r}V${b}Z`;
  };
  return (
    <div className="twin3d-energy">
      <p className="twin3d-energy-head">
        최근 달 <b>{ymLabel(last.ym)}</b> <b className="num">{fmt(last.qty)}{unit}</b> <EvidenceBadge kind="실측" />
        <small> {e.months.length}개월 기록 · 최대 {fmt(max)}{unit}{e.unit ? "" : " · 단위는 원천 명세 확인 필요"}</small>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="twin3d-energy-chart" role="img"
        aria-label={`월별 가스 사용량 막대 — ${ymLabel(span[0])}부터 ${ymLabel(span[span.length - 1])}까지, 기록 ${e.months.length}개월, 최근 ${ymLabel(last.ym)} ${fmt(last.qty)}${unit}`}
        onMouseLeave={() => setHover(null)}>
        <line x1={PAD_L} x2={W - PAD_R} y1={PAD_T + ph + 0.5} y2={PAD_T + ph + 0.5} className="twin3d-energy-axis" />
        <text x={PAD_L} y={11} className="twin3d-energy-tick">{fmt(max)}{unit}</text>
        <line x1={PAD_L} x2={W - PAD_R} y1={PAD_T + 0.5} y2={PAD_T + 0.5} className="twin3d-energy-grid" />
        {span.map((ym, i) => {
          const m = byYm.get(ym);
          const x = PAD_L + i * slot + (slot - bw) / 2;
          const h = m ? Math.max(m.qty > 0 ? 1.5 : 0, (m.qty / max) * ph) : 0;
          return (
            <g key={ym}>
              {m && h > 0 && <path d={bar(x, h)} className={`twin3d-energy-bar${hover === ym ? " is-hover" : ""}`} />}
              {!m && <line x1={x + bw / 2} x2={x + bw / 2} y1={PAD_T + ph - 3} y2={PAD_T + ph} className="twin3d-energy-gap" />}
              <rect x={PAD_L + i * slot} y={0} width={slot} height={H} fill="transparent" onMouseEnter={() => setHover(ym)}>
                <title>{`${ymLabel(ym)} · ${m ? `${fmt(m.qty)}${unit}${m.n > 1 ? ` (같은 지번 ${m.n}건 합)` : ""}` : "자료 없음"}`}</title>
              </rect>
            </g>
          );
        })}
        <text x={PAD_L} y={H - 4} className="twin3d-energy-tick">{ymLabel(span[0])}</text>
        <text x={W - PAD_R} y={H - 4} className="twin3d-energy-tick" textAnchor="end">{ymLabel(span[span.length - 1])}</text>
      </svg>
      <p className="twin3d-note" aria-live="polite">{shown
        ? <>{ymLabel(shown.ym)} · <b className="num">{fmt(shown.qty)}{unit}</b>{shown.n > 1 ? ` · 같은 지번 ${shown.n}건 합` : ""}</>
        : hover ? <>{ymLabel(hover)} · 자료 없음</> : "막대에 올리면 그 달 값을 보입니다. 바닥의 짧은 눈금은 기록이 없는 달입니다."}</p>
      <details className="twin3d-energy-table">
        <summary>표로 보기</summary>
        <table>
          <thead><tr><th scope="col">월</th><th scope="col">가스 사용량{unit}</th></tr></thead>
          <tbody>{[...span].reverse().map((ym) => {
            const m = byYm.get(ym);
            return <tr key={ym}><td>{ymLabel(ym)}</td><td className="num">{m ? `${fmt(m.qty)}${m.n > 1 ? ` (${m.n}건 합)` : ""}` : <span className="value-absent">자료 없음</span>}</td></tr>;
          })}</tbody>
        </table>
      </details>
      <p className="twin3d-note">
        {e.source} · 지번 합계{multi ? "(같은 지번 건물 · 계량기 여럿이면 합)" : ""} — 집합건물은 호실을 가를 수 없습니다.
        가스는 난방 계절을 타서 여름에 적은 것은 공실 신호가 아닙니다. 공실 판정에는 쓰지 않았습니다.
      </p>
    </div>
  );
}

function EnergyWhy({ e }: { e: BuildingEnergy }) {
  if (e.status === "refused") {
    return (
      <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 건물에너지정보 원천이 조회를 거절했습니다({e.error ?? "사유 미상"}).
        서버 공공데이터 키에 <a href={e.apply_url} target="_blank" rel="noopener noreferrer">건축HUB 건물에너지정보 서비스 활용신청 ↗<span className="sr-only">(새 창)</span></a>이
        승인되면 재배포 없이 여기에 월별 값이 나옵니다.</p>
    );
  }
  if (e.status === "no_key") return <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 서버에 공공데이터 키가 없어 조회하지 못했습니다.</p>;
  if (e.status === "no_pnu") return <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 이 건물 지번(산 지번 등)으로는 조회하지 않습니다.</p>;
  return <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 조회가 잠시 안 됩니다. 창을 다시 열면 다시 묻습니다.</p>;
}
