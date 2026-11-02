/**
 * Page 레이어 패널 — 유동 24시간 곡선 · 임대 분기 추이 · 밀도 셀 정보, 건물 상세의 소요시간.
 * 전부 **그 레이어(건물)를 켠 뒤 마운트**되므로 MapShell 첫 렌더 fetch 는 늘지 않는다.
 */
import { useEffect, useState } from "react";
import EvidenceBadge from "@/components/EvidenceBadge";
import { getHourlyProfile, getRentHistory, getTravelTimes, type DensityHeatmap, type HourlyProfile, type RentHistory, type TravelTimes, type TrdarCell } from "@/lib/api";
import { kakaoMapUrl, kakaoRouteUrl } from "@/lib/externalMap";
import { loadJourney } from "@/lib/journeyState";
import "./PageLayerPanels.css";

const nf = (v: number) => v.toLocaleString("ko-KR");
type Daytype = "weekday" | "weekend";

/** 유동 24시간 — 막대 길이가 값이다(0 기준). 지금 고른 시각을 강조한다. */
export function HourlyPanel({ districtId, daytype, hour }: { districtId: string; daytype: Daytype; hour: number }) {
  const [state, setState] = useState<{ key: string; data: HourlyProfile | null } | null>(null);
  const key = `${districtId}:${daytype}`;
  useEffect(() => {
    const ctrl = new AbortController();
    getHourlyProfile(districtId, daytype, ctrl.signal)
      .then((data) => { if (!ctrl.signal.aborted) setState({ key, data }); })
      .catch(() => { if (!ctrl.signal.aborted) setState({ key, data: null }); });
    return () => ctrl.abort();
  }, [districtId, daytype, key]);
  const current = state?.key === key ? state : null;
  if (!current) return <div className="plp" role="status">24시간 곡선 불러오는 중…</div>;
  const d = current.data;
  if (!d) {
    return (
      <div className="plp">
        <div className="plp-head"><strong>24시간 유동</strong></div>
        <p className="plp-note"><span className="value-absent">서울만 제공</span> — 시간대별 생활인구는 서울시 자료뿐이라 이 상권에는 없습니다.</p>
      </div>
    );
  }
  const max = Math.max(...d.hours.map((h) => h.value ?? 0), 1);
  const W = 288, H = 72, bw = W / 24;
  return (
    <div className="plp" aria-label="24시간 유동 곡선">
      <div className="plp-head">
        <strong>24시간 유동 · {daytype === "weekend" ? "주말" : "평일"}</strong>
        <EvidenceBadge kind="통계" />
      </div>
      <svg viewBox={`0 0 ${W} ${H + 14}`} className="plp-chart" role="img"
        aria-label={`정점 ${d.peak.hour}시. 값은 집계구 합계이고 상권 안 인원수가 아닙니다.`}>
        {d.hours.map((h) => {
          const v = h.value ?? 0;
          const bh = (v / max) * H;
          return <rect key={h.hour} x={h.hour * bw + 1} y={H - bh} width={bw - 2} height={bh} rx={1.5}
            className={h.hour === hour ? "plp-bar is-now" : h.hour === d.peak.hour ? "plp-bar is-peak" : "plp-bar"}><title>{`${h.hour}시 · ${nf(Math.round(v))}${h.share != null ? ` · ${(h.share * 100).toFixed(1)}%` : ""}`}</title></rect>;
        })}
        {[0, 6, 12, 18, 23].map((h) => <text key={h} x={h * bw + bw / 2} y={H + 11} className="plp-axis">{h}</text>)}
      </svg>
      <p className="plp-note">
        정점 <b className="num">{d.peak.hour}시</b> · 서울시 생활인구({d.source.includes("jipgyegu") ? "집계구" : "행정동"})
        {d.sample_days ? ` · 표본 ${nf(d.sample_days)}일` : ""}{d.as_of ? ` · 기준 ${d.as_of}` : ""}
        <br />값은 상권 안 인원수가 아니라 구획 합계입니다. 다른 상권과 견주지 마세요.
      </p>
      <table className="sr-only">
        <caption>시간대별 값</caption>
        <tbody>{d.hours.map((h) => <tr key={h.hour}><th scope="row">{h.hour}시</th><td>{h.value ?? "자료 없음"}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function Spark({ quarters, values, label, unit }: { quarters: string[]; values: (number | null)[]; label: string; unit: string }) {
  const pts = values.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v !== null);
  if (pts.length < 2) return <p className="plp-note">{label} <span className="value-absent">자료 없음</span></p>;
  const lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
  const W = 288, H = 44;
  const x = (i: number) => (i / Math.max(quarters.length - 1, 1)) * (W - 8) + 4;
  const y = (v: number) => (hi === lo ? H / 2 : H - 4 - ((v - lo) / (hi - lo)) * (H - 8));
  const last = pts[pts.length - 1];
  return (
    <div className="plp-spark">
      <div className="plp-spark-head"><span>{label}</span><b className="num">{nf(last.v)}{unit}</b></div>
      <svg viewBox={`0 0 ${W} ${H}`} className="plp-chart" role="img" aria-label={`${label} 최저 ${lo} 최고 ${hi} 최근 ${last.v}${unit}`}>
        <polyline className="plp-line" points={pts.map((p) => `${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ")} />
        <circle className="plp-dot" cx={x(last.i)} cy={y(last.v)} r={2.5} />
      </svg>
      <div className="plp-spark-foot num"><span>{quarters[0].slice(0, 4)}.{quarters[0].slice(4)}Q</span><span>최저 {nf(lo)} · 최고 {nf(hi)}</span><span>{quarters[quarters.length - 1].slice(0, 4)}.{quarters[quarters.length - 1].slice(4)}Q</span></div>
    </div>
  );
}

/** 임대 분기 추이. 1층 기준 R-ONE 값이고 층 계수는 추정이다. */
export function RentTrendPanel({ districtId }: { districtId: string }) {
  const [state, setState] = useState<{ id: string; data: RentHistory | null } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getRentHistory(districtId, ctrl.signal)
      .then((data) => { if (!ctrl.signal.aborted) setState({ id: districtId, data }); })
      .catch(() => { if (!ctrl.signal.aborted) setState({ id: districtId, data: null }); });
    return () => ctrl.abort();
  }, [districtId]);
  const current = state?.id === districtId ? state : null;
  if (!current) return <div className="plp" role="status">분기 추이 불러오는 중…</div>;
  const d = current.data;
  if (!d) return <div className="plp"><p className="plp-note">분기 추이 <span className="value-absent">자료 없음</span> — 이 상권은 R-ONE 시계열이 없습니다.</p></div>;
  return (
    <div className="plp" aria-label="임대 분기 추이">
      <div className="plp-head"><strong>분기 추이 · {d.quarters.length}분기</strong><EvidenceBadge kind="통계" /></div>
      {d.rent_available
        ? <Spark quarters={d.quarters} values={d.rent_per_pyeong_manwon} label="1층 평당 월 임대" unit="만원" />
        : <p className="plp-note">1층 임대 <span className="value-absent">자료 없음</span> — 이 상권은 R-ONE 임대 표본이 없습니다.</p>}
      <p className="plp-note">
        {d.source_name ?? "R-ONE"}{d.source === "rone-shared" && d.shared_from ? ` · 인접 상권(${d.shared_from}) 값을 빌렸습니다` : ""}.
        위 층별 금액은 이 값에 <b>층 계수(추정)</b>를 곱한 것입니다. 표본개편 전후로 값이 튈 수 있습니다.
      </p>
      <details className="plp-more">
        <summary>이 상권 공실률 추이(R-ONE)</summary>
        <Spark quarters={d.quarters} values={d.vacancy_mid_pct} label="중대형 공실률" unit="%" />
        <Spark quarters={d.quarters} values={d.vacancy_small_pct} label="소규모 공실률" unit="%" />
      </details>
    </div>
  );
}

/** 밀도 — 단위와, 누른 셀이 어느 집계구(상권)의 값인지. */
export function DensityPanel({ hm, cell }: { hm: DensityHeatmap; cell: TrdarCell | null }) {
  const unit = hm.density_basis === "flpop_mean24_per_1k_m2" ? "명/1,000㎡ · 24시간 평균" : hm.unit;
  return (
    <div className="plp" aria-label="밀도 레이어 정보">
      <div className="plp-head"><strong>{hm.label}</strong><EvidenceBadge kind="통계" /></div>
      <p className="plp-note">단위 <b>{unit}</b> · 범위 <span className="num">{nf(hm.min)}~{nf(hm.max)}</span></p>
      {cell
        ? <p className="plp-cell" role="status">누른 칸 <b className="num">{nf(cell.v)}</b> · {cell.oa ? <>집계구 코드 <b className="num">{cell.oa}</b></> : cell.trdar ? <>상권 {cell.trdar}</> : "구획 정보 없음"}</p>
        : <p className="plp-note">지도의 칸을 누르면 그 값이 어느 구획에서 왔는지 보여 줍니다.</p>}
      <p className="plp-note">상주인구가 아니라 유동인구 기준이고, 셀 값은 그 셀이 속한 구획의 값입니다.</p>
    </div>
  );
}

/** 건물 상세의 소요시간 — 출발지가 있으면 고를 때 한 번 부른다. 시간은 제공사 값만 적는다. */
export function SelectedTravel({ target, name }: { target: { lat: number; lng: number }; name: string }) {
  const [origin] = useState(() => loadJourney().origin ?? null);
  const [times, setTimes] = useState<TravelTimes | null | "error">(null);
  useEffect(() => {
    if (!origin) return;
    const ctrl = new AbortController();
    getTravelTimes({ lat: origin.lat, lng: origin.lng }, target, ctrl.signal)
      .then((t) => { if (!ctrl.signal.aborted) setTimes(t); })
      .catch(() => { if (!ctrl.signal.aborted) setTimes("error"); });
    return () => ctrl.abort();
    // 대상이 바뀌면 key 로 다시 마운트한다 — 좌표 객체 동일성에 묶지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin]);
  const route = origin ? kakaoRouteUrl("traffic", [{ ...origin, name: origin.label }, { ...target, name }]) : null;
  if (!origin) {
    return (
      <p className="plp-note b-travel">
        소요시간은 출발지를 정하면 나옵니다(Platform 「출발지 소요시간」) · <a href={kakaoMapUrl(target, name)} target="_blank" rel="noopener noreferrer">카카오맵에서 위치 보기<span className="sr-only">(새 창)</span></a>
      </p>
    );
  }
  const ok = times && times !== "error" ? times.results.filter((r) => r.status === "ok" && r.duration_seconds != null) : [];
  return (
    <div className="plp-note b-travel">
      <b>{origin.label}</b> 출발{" "}
      {times === null && "조회 중…"}
      {ok.map((r) => (
        <span key={r.mode} className="b-travel-item">{r.mode === "driving" ? "차량" : "대중교통"} <b className="num">{Math.round((r.duration_seconds as number) / 60)}분</b> <EvidenceBadge kind="추정" /></span>
      ))}
      {times && ok.length === 0 && <span className="value-absent">소요시간 자료 없음</span>}
      {route && <> · <a href={route} target="_blank" rel="noopener noreferrer">카카오맵 길찾기<span className="sr-only">(새 창)</span></a></>}
    </div>
  );
}
