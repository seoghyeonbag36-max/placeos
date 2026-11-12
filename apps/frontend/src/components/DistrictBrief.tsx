import { useEffect, useState, type ReactNode } from "react";
import { getDistrictIndustries, getHourlyProfile, getRentHistory } from "@/lib/api";
import type { DistrictIndustries, DistrictSummary, HourlyProfile, HubOutline, IndustryFit, PlatformProfile, RentHistory } from "@/lib/api";
import EvidenceBadge, { type Evidence } from "@/components/EvidenceBadge";
import { groupName, groupOf, median } from "@/lib/districtMapModel";
import { VACANCY_LABEL } from "@/lib/vacancyLabels";
import "./DistrictBrief.css";

/** 2026-12 시행 예고 — 그 상권에 해당할 때만 보인다. 방송대길·연무장길이 든 거점은 seongsu 하나다 */
const REGULATED_HUBS = new Set(["seongsu"]);
const SEOUL_ONLY = "서울만 제공";

interface Loaded { id: string; industries: DistrictIndustries | null; rent: RentHistory | null; hourly: HourlyProfile | null }

function Tile({ label, value, evidence, foot }: { label: string; value: ReactNode; evidence: Evidence; foot?: ReactNode }) {
  return <div className="brief-tile">
    <div className="brief-tile-l"><span>{label}</span><EvidenceBadge kind={evidence} /></div>
    <div className="brief-tile-v">{value}</div>
    {foot && <div className="brief-tile-f">{foot}</div>}
  </div>;
}

/** 묶음 중앙값 대비 차이 줄 */
function versus(value: number | null, med: number | null, unit: string, group: string, digits = 1): ReactNode {
  if (value == null || med == null) return `${group} 중앙값과 비교할 값 없음`;
  const d = value - med;
  const mark = Math.abs(d) < 10 ** -digits ? "＝" : d > 0 ? "▲" : "▼";
  const fmt = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: digits });
  return <>{mark} {fmt(Math.abs(d))}{unit} · {group} 중앙값 {fmt(med)}{unit === "p" ? "%" : unit}</>;
}

export default function DistrictBrief({ hub, districts, outline, identity, fitForRent, picked, pickDisabled, onTogglePick, onOpenPage }: {
  hub: DistrictSummary; districts: DistrictSummary[]; outline: HubOutline | undefined;
  identity: PlatformProfile["identity"] | null;
  /** 어느 업종이든 줄마다 1층 임대가 실려 온다 — 묶음 중앙값용 */
  fitForRent: IndustryFit | null;
  picked: boolean; pickDisabled: boolean; onTogglePick: () => void;
  onOpenPage?: () => void;
}) {
  const [data, setData] = useState<Loaded | null>(null);
  const id = hub.id;
  useEffect(() => {
    const ctrl = new AbortController();
    let live = true;
    const quiet = <T,>(p: Promise<T | null>) => p.catch(() => null);
    void Promise.all([
      quiet(getDistrictIndustries(id)), quiet(getRentHistory(id, ctrl.signal)), quiet(getHourlyProfile(id, "weekday", ctrl.signal)),
    ]).then(([industries, rent, hourly]) => { if (live) setData({ id, industries, rent, hourly }); });
    return () => { live = false; ctrl.abort(); };
  }, [id]);
  const here = data?.id === id ? data : null;

  const group = groupOf(hub);
  const gName = groupName(group);
  const seoul = group === "seoul";
  const peers = districts.filter((d) => groupOf(d) === group);
  const peerIds = new Set(peers.map((d) => d.id));
  const rentMed = median((fitForRent?.districts ?? []).filter((r) => peerIds.has(r.district_id)).map((r) => r.rent_1f_per_pyeong));

  const hourly = here?.hourly ?? null;
  const dailyMean = hourly && hourly.hours.every((h) => h.value != null)
    ? hourly.hours.reduce((s, h) => s + (h.value as number), 0) / hourly.hours.length : null;
  const rentSeries = here?.rent?.rent_available ? here.rent.rent_per_pyeong_manwon : [];
  let rentAt = rentSeries.length - 1;
  while (rentAt >= 0 && rentSeries[rentAt] == null) rentAt--;
  const rent = rentAt >= 0 ? rentSeries[rentAt] as number : null;
  const rentQuarter = rentAt >= 0 ? here?.rent?.quarters[rentAt] : undefined;

  const ranked = (here?.industries?.rows ?? []).filter((r) => r.fit_rank != null)
    .sort((a, b) => (a.fit_rank as number) - (b.fit_rank as number));
  const best = ranked.slice(0, 3);
  const careful = ranked.slice(3).slice(-2).reverse();
  const sampleN = here?.industries?.sample_n;

  const demand = identity?.demand ?? {};
  const groups = identity?.categories.groups ?? [];
  const maxShare = Math.max(...(hourly?.hours.map((h) => h.share ?? 0) ?? [0]), 1e-9);
  const maxAge = Math.max(...(demand.ages?.map((a) => a.share) ?? [0]), 1e-9);
  const absent = (why: string) => <span className="value-absent">{why}</span>;
  const seoulOnly = (reason: string) => absent(seoul ? "이 상권 자료 없음" : `${SEOUL_ONLY} — ${reason}`);

  const summary = [
    identity?.archetype ? `${hub.gu}의 「${identity.archetype}」 상권` : `${hub.gu}의 상권`,
    `실측 범위 영업 점포 ${hub.store_count.toLocaleString()}곳`,
    groups.length ? `많은 업종은 ${groups.slice(0, 2).map((g) => g.group).join("·")}` : null,
    hourly ? `평일 생활인구 피크 ${hourly.peak.hour}시` : null,
  ].filter(Boolean).join(" · ");

  return (
    <section className="brief" aria-label="상권 상세">
      <div className="brief-chips">
        {outline?.type_code
          ? <span className="brief-chip is-type">{outline.type_code} {outline.type_name}<small>{outline.type_is_manual ? "사람 분류" : "데이터 분류"}</small></span>
          : <span className="brief-chip">유형 라벨 없음<small>서울만 있음</small></span>}
        {identity?.archetype && <span className="brief-chip">{identity.archetype}<small>업종 규칙</small></span>}
      </div>
      <h2>{hub.name}</h2>
      <p className="brief-sum">{summary}</p>
      {groups.length > 0 && <div className="brief-tags">{groups.slice(0, 4).map((g) => <span key={g.group}>#{g.group}</span>)}</div>}

      {REGULATED_HUBS.has(id) && (
        <div className="brief-reg" role="note" aria-label="입점 규제 확인">
          <b>입점 제한 확인</b>
          <p>성동구 대기업·프랜차이즈 입점 제한: 2026-12 부터 방송대길·연무장길 일대 232필지 포함 — 일반음식점·휴게음식점·제과점 3업종,
            법정 규모 이하 영세 프랜차이즈·주민협의체 동의 시 예외(2026-10 보도 기준). 가맹 창업이면 성동구청에 확인하세요.{" "}
            <a href="https://biz.sbs.co.kr/amp/article/20000338459" target="_blank" rel="noopener noreferrer">출처: SBS Biz (새 창)</a></p>
        </div>
      )}

      <div className="brief-tiles">
        <Tile label="일평균 생활인구" evidence="통계"
          value={dailyMean != null ? <>{Math.round(dailyMean).toLocaleString()}<small>명</small></>
            : hourly ? absent("인원 없음 · 시간 구성비만") : here ? seoulOnly("서울시 생활인구") : absent("불러오는 중")}
          foot={dailyMean != null ? "평일 시각 평균 · 집계구 합이라 상권 안 인원수가 아니어서 묶음 비교를 하지 않습니다" : undefined} />
        <Tile label="영업 점포(실측 범위)" evidence="실측" value={<>{hub.store_count.toLocaleString()}<small>곳</small></>}
          foot={versus(hub.store_count, median(peers.map((d) => d.store_count)), "곳", gName, 0)} />
        <Tile label={VACANCY_LABEL.primary} evidence={hub.vacancy_source === "gold" ? "실측" : "추정"}
          value={hub.vacancy_rate != null ? <>{hub.vacancy_rate.toFixed(1)}<small>%</small></>
            : absent(hub.vacancy_withheld ? "대표값 미제공" : "실측 없음")}
          foot={versus(hub.vacancy_rate, median(peers.map((d) => d.vacancy_rate)), "p", gName)} />
        <Tile label="1층 임대(평당·월)" evidence="통계"
          value={rent != null ? <>{rent}<small>만원</small></> : absent(here ? "이 상권 임대 자료 없음" : "불러오는 중")}
          foot={rent != null ? <>{versus(rent, rentMed, "만원", gName)}{rentQuarter && ` · ${rentQuarter.slice(0, 4)}년 ${rentQuarter.slice(4)}분기`}
            {here?.rent?.source === "rone-shared" && " · 인접 표본 차용"} · 호가 아님</> : undefined} />
      </div>

      <div className="brief-cols">
        <div>
          <h3>이 상권 업종 상위 3 <EvidenceBadge kind="참고 지수" /></h3>
          {best.length ? <ol className="brief-rank">{best.map((r) => <li key={r.key}>
            <b>{r.label}</b><span>{r.same_share != null ? `같은 업종 ${(r.same_share * 100).toFixed(1)}%${sampleN ? ` (${r.same_n}/${sampleN.toLocaleString()})` : ""}` : "관측 없음"}</span>
          </li>)}</ol> : absent(here ? "이 상권 순위 자료 없음" : "불러오는 중")}
        </div>
        <div>
          <h3>신중히 볼 업종 <EvidenceBadge kind="참고 지수" /></h3>
          {careful.length ? <ul className="brief-rank">{careful.map((r) => <li key={r.key}>
            <b>{r.label}</b><span>{r.same_share != null ? `같은 업종 ${(r.same_share * 100).toFixed(1)}%` : "관측 없음"}</span>
          </li>)}</ul> : absent(here ? "견줄 업종이 부족합니다" : "불러오는 중")}
          <p className="brief-note">피해야 한다는 뜻이 아니라, 이 상권에 잘 안 모이는 업종입니다(관측·모델).</p>
        </div>
      </div>
      <p className="brief-note">모델 순위는 6업종만 있고, 이미 모여 있는 정도이지 매출·생존이 아닙니다.</p>

      <h3>시간대 <EvidenceBadge kind="통계" /></h3>
      {hourly ? <>
        <div className="brief-hours" role="img" aria-label={`평일 24시간 생활인구 구성. 가장 많은 시각 ${hourly.peak.hour}시`}>
          {hourly.hours.map((h) => <i key={h.hour} className={h.hour === hourly.peak.hour ? "is-peak" : ""}
            style={{ height: `${((h.share ?? 0) / maxShare) * 100}%` }} title={`${h.hour}시 ${((h.share ?? 0) * 100).toFixed(1)}%`} />)}
        </div>
        <div className="brief-axis" aria-hidden><span>0시</span><span>6</span><span>12</span><span>18</span><span>23시</span></div>
        <p className="brief-note">평일 · {hourly.as_of ? `${hourly.as_of} 기준` : "기준일 미상"}{hourly.note ? ` · ${hourly.note}` : ""}</p>
      </> : <p>{here ? seoulOnly("서울시 생활인구 원천이 서울뿐입니다") : absent("불러오는 중")}</p>}

      <h3>방문 고객 <EvidenceBadge kind="통계" /></h3>
      {demand.ages?.length ? <>
        <div className="brief-ages">{demand.ages.map((a) => <div key={a.band} className="brief-age">
          <span>{a.band}</span><span className="brief-agebar"><i style={{ width: `${(a.share / maxAge) * 100}%` }} /></span><b>{a.share.toFixed(1)}%</b>
        </div>)}</div>
        <p className="brief-note">
          {demand.female_share != null && `여성 ${demand.female_share.toFixed(1)}%`}
          {demand.weekend_flpop != null && ` · 주말 유동 ${demand.weekend_flpop.toFixed(1)}%`} · 서울 상권분석(TRDAR)
        </p>
      </> : <p>{seoulOnly("서울 상권분석(TRDAR) 원천이 서울뿐입니다")}</p>}

      <div className="brief-actions">
        <button type="button" className="dcmp-btn" aria-pressed={picked} disabled={pickDisabled} onClick={onTogglePick}>
          {picked ? "✓ 이 상권 비교에 담음" : "+ 이 상권 비교에 담기"}
        </button>
        {onOpenPage && <button type="button" className="dcmp-btn is-strong" onClick={onOpenPage}>이 상권 공실 3D로 보기 → Page</button>}
      </div>
    </section>
  );
}
