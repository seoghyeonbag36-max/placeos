import { useHourlyProfiles, type HourlyDay, type HourlyProfiles } from "@/lib/useHourlyProfiles";
import "./HourlyComparison.css";

const DAYS: { key: HourlyDay; label: string }[] = [
  { key: "weekday", label: "평일" }, { key: "weekend", label: "주말" },
];

/** 서로 다른 일수의 인원 합계 대신 각 하루 안의 시간별 구성비를 같은 축으로 비교한다. */
export default function HourlyComparison({ districtId }: { districtId: string }) {
  const data = useHourlyProfiles(districtId);
  return <HourlyComparisonView data={data} />;
}

/** 요약 카드도 같은 요청 결과를 사용하도록 조회와 표시를 분리한다. */
export function HourlyComparisonView({ data, outsideSeoul = false }: { data: HourlyProfiles | null; outsideSeoul?: boolean }) {
  const validShare = (v: number | null | undefined): v is number => v != null && Number.isFinite(v) && v >= 0 && v <= 1;
  const max = Math.max(0.01, ...DAYS.flatMap(({ key }) =>
    (data?.[key].profile?.hours ?? []).flatMap(h => validShare(h.share) ? [h.share] : [])));
  const hasShares = DAYS.some(({ key }) => data?.[key].profile?.hours.some(h => validShare(h.share)));
  // 두 그래프에 같은 축을 쓰고, 값 0과 결측을 구분해 결측의 막대는 만들지 않는다.
  return <section className="hourly-comparison" aria-label="평일·주말 24시간 비교">
    <h3>평일·주말 24시간 비교</h3>
    <p className="brief-note">각 날짜 구분의 하루 생활인구 합계에서 각 시각이 차지하는 비중입니다. 두 그래프는 같은 축을 사용합니다.</p>
    {!data ? <p role="status">시간대 자료를 불러오는 중…</p> : <>
      {outsideSeoul && !hasShares && <p className="value-absent">서울만 제공 — 서울시 생활인구 원천을 사용하는 비교입니다.</p>}
      {hasShares && <p className="hourly-scale">공통 세로축 0~{(max * 100).toFixed(1)}%</p>}
      {DAYS.map(({ key, label }) => {
        const { profile, failed } = data[key];
        const shares = profile?.hours.filter(h => validShare(h.share)) ?? [];
        return <section key={key} className={`hourly-day is-${key}`} aria-label={`${label} 생활인구`}>
          <h4>{label}{profile && shares.length > 0 ? ` · 가장 많은 시각 ${profile.peak.hour}시` : ""}</h4>
          {profile && shares.length > 0 ? <>
            <div className="hourly-bars" role="img" aria-label={`${label} 24시간 생활인구 구성비 · 공통 최대 ${(max * 100).toFixed(1)}%`}>
              {Array.from({ length: 24 }, (_, hour) => {
                const share = profile.hours.find(h => h.hour === hour)?.share;
                return <span key={hour} className="hourly-bar-slot" title={`${hour}시 ${validShare(share) ? `${(share * 100).toFixed(1)}%` : "자료 없음"}`}>
                  {validShare(share) ? <i style={{ height: `${share / max * 100}%` }} /> : <span className="hourly-missing">—</span>}
                </span>;
              })}
            </div>
            <div className="brief-axis" aria-hidden="true"><span>0시</span><span>6</span><span>12</span><span>18</span><span>23시</span></div>
            <details><summary>{label} 시간별 수치</summary>
              <table><thead><tr><th>시각</th><th>생활인구 구성비</th></tr></thead><tbody>
                {Array.from({ length: 24 }, (_, hour) => {
                  const share = profile.hours.find(h => h.hour === hour)?.share;
                  return <tr key={hour}><th>{hour}시</th><td>{validShare(share) ? `${(share * 100).toFixed(1)}%` : "자료 없음"}</td></tr>;
                })}
              </tbody></table>
            </details>
            <p className="brief-note">{label} · {profile.as_of ? `${profile.as_of} 기준` : "기준일 미상"}
              {profile.sample_days != null ? ` · 표본 ${profile.sample_days}일` : ""} · {profile.source === "flpop_jipgyegu" ? "집계구 생활인구" : profile.source === "adong_hourly" ? "행정동 생활인구" : profile.source}
              {profile.note ? ` · ${profile.note}` : ""}</p>
          </> : <p className="value-absent">{failed ? `${label} 자료를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.` : `이 상권의 ${label} 시간대 자료가 없습니다.`}</p>}
        </section>;
      })}
      {data.weekday.profile && data.weekend.profile && data.weekday.profile.source !== data.weekend.profile.source &&
        <p className="brief-note">평일과 주말의 집계 범위가 다릅니다. 같은 공간의 증감으로 해석할 수 없습니다.</p>}
      <p className="brief-note">시각별 생활인구의 분포이며 실제 방문 고객 수·매출·구매 전환율이 아닙니다. 과거 자료로 시간대의 모양을 비교하세요.</p>
    </>}
  </section>;
}
