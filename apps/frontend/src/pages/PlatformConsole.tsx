import { useEffect, useId, useMemo, useState, type ReactNode } from "react";
import DistrictPicker, { CaveatNote, MeasuredValue } from "@/components/DistrictPicker";
import PlatformComparison from "@/components/PlatformComparison";
import Verdict, { Fold, type Ground } from "@/components/Verdict";
import {
  getPlatformProfile, getSentiment, getVacancyHeatmap, listDistricts, predictVacancy, recommendIndustry,
} from "@/lib/api";
import type {
  DistrictSummary, IndustryOption, IndustryRecommend, OpeningSite, PlatformProfile, VacancyForecast, Zone,
} from "@/lib/api";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { mapLabelHTML } from "@/design/components/MapMarkerPin";
import IndustryFitCard from "@/components/IndustryFitCard";
import { findIndustry, type BusinessProfile } from "@/lib/businessProfile";
import { lstmPromoted } from "@/lib/forecastSkill";
import { colors } from "@/design/tokens/colors";
import { useMapHost } from "@/components/MapHost";
import { fitInView, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import { boundaryBadge, computeHubBoundary, EMPTY_BOUNDARY, type HubBoundary } from "@/lib/hubBoundary";
import type { BuildingSelection } from "@/lib/workspaceState";
import { VACANCY_LABEL } from "@/lib/vacancyLabels";
import "./PlatformConsole.css";

/**
 * 고객용 상권 분석 — 상권 요약, 공간 후보, 공실 전망과 추천 업종을 보여준다.
 * 내부 파일 경로·모델 검증 지표는 표시하지 않는다. 실측·합성 구분과 추천의 한계는 유지한다.
 * 전망은 기존 신뢰성 게이트를 그대로 사용하며, 통과 전에는 현재 공실률을 참고값으로 표시한다.
 */

const DEFAULT_DISTRICT = "garosugil";
const QUARTERS = [1, 2, 3, 4];
const SITES_PAGE = 9;

/** 업종 군 색 — 순위 순서대로 집는다(군 이름에 색을 고정하면 거점마다 범례가 뒤바뀐다) */
const GROUP_COLORS = [
  "#3A5A98", "#0EA5B7", "#22B07D", "#E0A13E", "#B07AA1",
  "#7C9BC7", "#D9736A", "#6BA368", "#9A8CD0", "#C2A25A",
];
const UNGROUPED_COLOR = "#CBD5E1";

/** 분기 코드(20262) → 사람이 읽는 표기(26년 2분기) */
function quarterLabel(q?: string): string {
  if (!q || q.length < 5) return q ?? "—";
  return `${q.slice(2, 4)}년 ${q.slice(4)}분기`;
}
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const signed = (v: number, digits = 3) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;

/** 값들을 ` · ` 로 잇는다 — 구분자를 한 곳에서만 정한다 */
function joinDot(parts: ReactNode[]): ReactNode {
  return parts.map((p, i) => <span key={i}>{i > 0 ? " · " : null}{p}</span>);
}

/** 공실률(%) 환산 — 예측의 단위가 아니라 delta 를 현재 공실률에 가산한 **근사**다.
 *  백엔드 services/districts._predicted 와 같은 식이라 거점 대시보드 값과 어긋나지 않는다.
 *  대표 공실률이 없는 거점(미측정 · 대표값 미제공)은 기준선이 없어 환산이 성립하지
 *  않는다 — 0 을 기준으로 더하면 없는 기준선을 지어내게 되므로 null 을 낸다. */
function approxVacancyPct(fc: VacancyForecast | null, hub?: DistrictSummary): number | null {
  const base = hub?.vacancy_rate ?? null;
  if (!fc || base === null || !Number.isFinite(base)) return null;
  return Math.max(0, Math.min(100, base + fc.delta));
}

const dirMark = (d: string) => (d === "up" ? "▲" : d === "down" ? "▼" : "—");

export default function PlatformConsole({ districtId: sharedDistrict, onDistrictChange, onOpenInPage,
  business = null, industries = null, onOpenBusiness, onTryIndustry }: {
  /** 네 트랙이 공유하는 상권(App). 주면 제어 모드, 안 주면 화면이 스스로 든다(단독 렌더·테스트). */
  districtId?: string;
  onDistrictChange?: (id: string) => void;
  /** Platform → Page 인계(화면설계서 2판). 주면 자리 카드에 「Page에서 이 건물 보기 →」가 뜬다. */
  onOpenInPage?: (selection: BuildingSelection) => void;
  /** 「내 사업」(화면설계서 3판). 있으면 패널 맨 위에 「내 업종으로 본 상권」을 세운다. */
  business?: BusinessProfile | null;
  industries?: IndustryOption[] | null;
  /** 「내 사업」이 없을 때 한 줄 안내의 「내 사업 설정」. 없으면(단독 렌더) 안내를 그리지 않는다. */
  onOpenBusiness?: () => void;
  /** 업종 바꾸기 표 「이 업종으로 입점 계산 →」 → Posting 업종칸(인계 표 Platform → Posting). */
  onTryIndustry?: (input: string) => void;
} = {}) {
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const [ownDistrict, setOwnDistrict] = useState(sharedDistrict ?? DEFAULT_DISTRICT);
  const controlled = sharedDistrict !== undefined && onDistrictChange !== undefined;
  const districtId = controlled ? sharedDistrict : ownDistrict;
  const setDistrictId = (id: string) => (controlled ? onDistrictChange(id) : setOwnDistrict(id));
  // 자리 비교 후보 — 지도 칩과 목록 체크박스가 **같은 상태**를 본다(그래서 여기로 올렸다).
  // 상권이 바뀌면 비운다: 다른 상권의 자리를 비교 후보로 남기지 않는다.
  const [selectedSiteIds, setSelectedSiteIds] = useState<string[]>([]);
  useEffect(() => { setSelectedSiteIds([]); }, [districtId]);
  const toggleSite = (id: string) => setSelectedSiteIds((ids) => ids.includes(id)
    ? ids.filter((selected) => selected !== id)
    : ids.length < 3 ? [...ids, id] : ids);
  const [quarters, setQuarters] = useState(1);
  const [listErr, setListErr] = useState<string | null>(null);

  const [prof, setProf] = useState<PlatformProfile | null>(null);
  const [profErr, setProfErr] = useState<string | null>(null);
  const [fc, setFc] = useState<VacancyForecast | null>(null);
  const [fcErr, setFcErr] = useState<string | null>(null);
  const [rec, setRec] = useState<IndustryRecommend | null>(null);
  const [recErr, setRecErr] = useState<string | null>(null);
  const [zones, setZones] = useState<Zone[] | null>(null);

  const hub = useMemo(
    () => districts.find((d) => d.id === districtId),
    [districts, districtId],
  );

  useEffect(() => {
    let live = true;
    listDistricts()
      .then((all) => {
        if (!live) return;
        setDistricts(all);
        if (all.length && !all.some((d) => d.id === districtId)) setDistrictId(all[0].id);
      })
      .catch((e) => live && setListErr(String(e)));
    return () => { live = false; };
    // 목록은 마운트 때 한 번만 — 상권 전환마다 다시 부르지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 정체성 + 자리 제안 — 이 화면의 본론
  useEffect(() => {
    let live = true;
    setProf(null); setProfErr(null);
    getPlatformProfile(districtId)
      .then((p) => { if (live) setProf(p); })
      .catch((e) => { if (live) setProfErr(String(e)); });
    return () => { live = false; };
  }, [districtId]);

  // 예측: 분기 선택이 실제 질의를 바꾼다(백엔드가 개월→분기로 환산한다).
  useEffect(() => {
    let live = true;
    setFc(null); setFcErr(null);
    predictVacancy(districtId, quarters * 3)
      .then((r) => { if (live) setFc(r); })
      .catch((e) => { if (live) setFcErr(String(e)); });
    return () => { live = false; };
  }, [districtId, quarters]);

  // 거점 단위 추천(좌표 없이) — 자리 단위는 위 openings 가 자리마다 따로 물어 온다.
  useEffect(() => {
    let live = true;
    setRec(null); setRecErr(null);
    recommendIndustry({ district_id: districtId })
      .then((r) => { if (live) setRec(r); })
      .catch((e) => { if (live) setRecErr(String(e)); });
    return () => { live = false; };
  }, [districtId]);

  useEffect(() => {
    let live = true;
    setZones(null);
    getSentiment(districtId)
      .then((z) => { if (live) setZones(z); })
      .catch(() => { if (live) setZones([]); });
    return () => { live = false; };
  }, [districtId]);

  const head = useMemo(
    () => headline({ hub, districtId, prof, profErr, fc, rec, zones }),
    [hub, districtId, prof, profErr, fc, rec, zones],
  );

  // 창업·옮기기이고 내 업종이 서빙 모델 어휘 안이면 자리를 **내 업종 점수 순**으로 세우고 칩도 그 점수를 말한다
  // (화면설계서 3판 「자리 칩 · 자리 카드 — 내 업종이 있을 때」). 바꾸기·어휘 밖이면 2판 규칙 그대로.
  const myIndustry = findIndustry(industries, business?.industryKey);
  // 서빙 어휘 밖(fit_unavailable_reason)이면 모델 라벨이 있어도 점수가 없다 — 모델 라벨이 없는 업종과 똑같이 둔다.
  const mySite = business?.goal !== "pivot" && myIndustry?.model_label && !myIndustry.fit_unavailable_reason
    ? { label: myIndustry.model_label, input: myIndustry.input } : null;
  const openingsHere = useMemo(() => {
    if (prof?.district_id !== districtId) return null;
    if (!mySite) return prof.openings;
    const score = (site: OpeningSite) => site.recommendations.find((r) => r.industry === mySite.label)?.score ?? -1;
    // 안정 정렬 — 점수가 같으면(둘 다 3위 밖 등) 원래 순서(상권 평균 대비 두드러진 자리부터)를 지킨다.
    const sites = prof.openings.sites.map((site, i) => ({ site, i }))
      .sort((a, b) => score(b.site) - score(a.site) || a.i - b.i).map((x) => x.site);
    return { ...prof.openings, sites };
    // mySite 는 렌더마다 새 객체라 값으로 비교한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prof, districtId, mySite?.label]);
  const sitesHere = openingsHere?.sites ?? null;
  const boundary = usePlatformMap({ districtId, sites: sitesHere, selectedIds: selectedSiteIds, onToggle: toggleSite, mySite });

  return (
    <div className="platconsole"><div className="wrap">
      <IndustryFitCard business={business} industries={industries} districtId={districtId} districts={districts}
        onDistrictChange={setDistrictId} onOpenBusiness={onOpenBusiness} onTryIndustry={onTryIndustry} />
      <Verdict
        eyebrow="PlaceOS · Platform" conversion="PLACE ▶ PLATFORM"
        question="이 상권은 어떤 곳인가요?"
        verdict={head.verdict} grounds={head.grounds.slice(0, 3).map(({ label, value }) => ({ label, value }))}
      />

      {listErr && (
        <div className="err">
          <strong>거점 목록을 불러오지 못했습니다.</strong>
          <div className="errdetail">잠시 후 다시 시도해 주세요.</div>
        </div>
      )}

      <div className="picker">
        <label className="pk">
          <span>상권</span>
          <DistrictPicker districts={districts} value={districtId}
            onChange={setDistrictId} suffix={(d) => d.gu} />
        </label>
        {hub && (
          <div className="chips">
            <span className="chip">{hub.type}</span>
            <span className="chip">
              {VACANCY_LABEL.primary}{" "}
              <MeasuredValue value={hub.vacancy_rate} unit="%"
                absent={hub.vacancy_withheld ? "대표값 미제공" : "실측 없음"} />
              <i className={`src ${hub.vacancy_source === "gold" ? "is-gold" : "is-syn"}`}>
                {hub.vacancy_source === "gold" ? "실측" : "합성"}
              </i>
            </span>
            {hub.building_count != null && (
              <span className="chip">건물 {hub.building_count.toLocaleString()}동</span>
            )}
            {/* 지도에 그린 선이 무엇인지 — 상권 경계가 아니라 **잰 범위**다(hubBoundary). */}
            {boundary && <span className="chip" title="지도에 그린 선은 공실률 분모에 들어간 100m 격자의 외곽선이다. 상권 경계가 아니다.">
              지도 선: {boundaryBadge(boundary)}
            </span>}
          </div>
        )}
      </div>

      {profErr && (
        <div className="err">
          <strong>상권 분석 정보를 제공할 수 없습니다.</strong>
          {/* 404 는 고장이 아니라 **아직 수집하지 않았다**는 뜻이다(경기 거점은 Platform
              트랙이 미착수다). 원시 에러 문자열을 사용자에게 보이면 고장처럼 읽히므로
              404 만 사람 말로 바꾸고, 그 외(5xx·네트워크)는 원문을 남겨 진단을 돕는다. */}
          <div className="errdetail">
            {/404/.test(profErr)
              ? "이 상권의 분석 정보가 아직 준비되지 않았습니다."
              : "잠시 후 다시 시도해 주세요."}
          </div>
        </div>
      )}
      {!profErr && !prof && <div className="loading">상권 정체성 불러오는 중…</div>}

      {prof?.identity && <IdentitySection ident={prof.identity} hub={hub} />}
      {openingsHere && (
        <OpeningsSection key={districtId} openings={openingsHere} districtName={hub?.name ?? districtId} mySite={mySite}
          selectedIds={selectedSiteIds} onToggle={toggleSite} onClear={() => setSelectedSiteIds([])}
          onOpenInPage={onOpenInPage ? (site) => onOpenInPage(siteToBuilding(districtId, site)) : undefined} />
      )}

      {/* 근거 — 위 두 답을 만든 모델의 성능과 한계. 지표가 아니라 **답**이 먼저 오도록 접어 둔다 */}
      <Fold title="공실 전망과 추천 업종"
        summary={modelFoldSummary(fc, rec)}>
        <div className="cols">
          <ForecastCard fc={fc} err={fcErr} quarters={quarters} onQuarters={setQuarters} hub={hub} />
          <RecommendCard rec={rec} err={recErr} />
        </div>
      </Fold>

      <SentimentSection zones={zones} hub={hub} />
    </div></div>
  );
}

/* ───────────────── 지도 (2026-09-13) ───────────────── */

/**
 * Platform 이 지도에 그리는 두 가지 — "이 상권은 어디까지인가" 와 "그 안 어느 자리에 무엇이".
 *
 *   ① **실측 범위 선** — 종전 「거점」 탭(HubExplorer)이 그리던 것을 이어받았다. 뜻은 상권
 *      경계가 아니라 "공실률 분모에 들어간 100m 격자의 외곽선"이다(lib/hubBoundary). 칩이
 *      그 사실을 말한다. 조각은 조각대로 그린다 — 감싸 덮으면 안 잰 곳을 잰 것처럼 보인다.
 *   ② **자리 칩** — 실측 공실 자리마다 **상권 평균 대비 가장 두드러지는 업종**(distinct).
 *      없으면 GNN Top-1, 그것도 없으면 "추천 없음". 칩을 누르면 비교 후보에 넣고 뺀다 —
 *      목록 체크박스와 같은 상태다.
 *
 * 지도가 없으면(단독 렌더·테스트) 경계 요청도 보내지 않는다 — 그릴 곳이 없는 값을 받지 않는다.
 * 경계를 돌려준다(패널 칩이 배지를 쓴다). 지도가 없으면 null.
 */
function usePlatformMap({ districtId, sites, selectedIds, onToggle, mySite }: {
  districtId: string; sites: OpeningSite[] | null;
  selectedIds: string[]; onToggle: (id: string) => void;
  mySite: { label: string; input: string } | null;
}): HubBoundary | null {
  const { map, ready } = useMapHost();
  const [boundary, setBoundary] = useState<{ id: string; b: HubBoundary } | null>(null);

  useEffect(() => {
    if (!ready || !map) return;
    let live = true;
    getVacancyHeatmap(districtId)
      .then((hm) => { if (live) setBoundary({ id: districtId, b: computeHubBoundary(hm.cells) }); })
      .catch(() => { if (live) setBoundary({ id: districtId, b: EMPTY_BOUNDARY }); });
    return () => { live = false; };
  }, [ready, map, districtId]);

  const current = boundary?.id === districtId ? boundary.b : null;

  // 선 그리기 + 카메라. 카메라는 거점 center 가 아니라 경계 bbox 에 맞춘다 — center 는
  // 수집 원점이라 실측 범위와 어긋날 수 있다(HubExplorer 에서 옮겨 온 규칙).
  useEffect(() => {
    const naver = (window as any).naver;
    if (!ready || !map || !naver?.maps || !current) return;
    const polys = current.pieces.map((piece) => {
      const toPath = (ring: Array<[number, number]>) => ring.map(([lat, lng]) => new naver.maps.LatLng(lat, lng));
      const solo = piece.cells <= 1;
      return new naver.maps.Polygon({
        map, paths: [toPath(piece.outer), ...piece.holes.map(toPath)],
        strokeColor: colors.track.platform.base, strokeWeight: solo ? 1 : 2.5,
        strokeOpacity: solo ? 0.7 : 0.95, strokeStyle: "shortdash",
        fillColor: colors.track.platform.base, fillOpacity: solo ? 0 : 0.07,
        clickable: false,
      });
    });
    if (current.bbox) {
      const { south, west, north, east } = current.bbox;
      fitInView(map, naver,
        new naver.maps.LatLngBounds(new naver.maps.LatLng(south, west), new naver.maps.LatLng(north, east)));
    }
    return () => { polys.forEach((p) => p.setMap?.(null)); };
  }, [ready, map, current]);

  const markers = useMemo<MapMarkerItem[]>(() => (sites ?? [])
    .filter((s) => s.lat != null && s.lng != null)
    .map((s) => {
      const on = selectedIds.includes(s.unit_id);
      const sub = s.area_py != null ? `${s.area_py}평` : undefined;
      if (mySite) {
        // 3판 — 내 업종 점수. 그 자리 상위 3에 없으면 점선 "3위 밖"(0% 로 그리지 않는다).
        const mine = s.recommendations.find((r) => r.industry === mySite.label);
        return {
          id: s.unit_id, lat: s.lat as number, lng: s.lng as number, zIndex: on ? 200 : mine ? 90 : 70,
          html: mapLabelHTML({
            text: mine ? `${mySite.input} ${Math.round(mine.score * 100)}%` : `${mySite.input} 3위 밖`,
            sub, color: colors.track.platform.base, active: on, dashed: !mine,
          }),
        };
      }
      const top = s.distinct?.industry ?? s.recommendations[0]?.industry ?? null;
      return {
        id: s.unit_id, lat: s.lat as number, lng: s.lng as number, zIndex: on ? 200 : 70,
        html: mapLabelHTML({
          text: top ?? "추천 없음",
          sub, color: colors.track.platform.base, active: on, dashed: top == null,
        }),
      };
    }), [sites, selectedIds, mySite?.label, mySite?.input]);
  useMapMarkers(markers, onToggle);

  return ready && map ? current : null;
}

/* ───────────────── 결론 1줄 + 근거 3줄 ───────────────── */

/**
 * 이 화면이 답한 것과 그 답을 세운 값.
 *
 * 근거의 순서는 정체성의 정의 그대로다 — 무엇이 모여 있고(①), 누가·언제 오고(②),
 * 밖에서 뭐라고 불리며(③), 어디로 가고 있나(④). 규칙이 세 줄이라 ④는 접힌다.
 * 값이 없으면 지어내지 않고 **없다고 적는다** — 빈 칸은 0 과 구분되지 않는다.
 */
function headline({ hub, districtId, prof, profErr, fc, rec, zones }: {
  hub?: DistrictSummary; districtId: string;
  prof: PlatformProfile | null; profErr: string | null;
  fc: VacancyForecast | null; rec: IndustryRecommend | null; zones: Zone[] | null;
}): { verdict: ReactNode; grounds: Ground[]; sources: ReactNode[] } {
  const name = hub?.name ?? districtId;
  const ident = prof?.identity ?? null;
  const groups = ident?.categories.groups ?? [];
  const total = ident?.categories.total ?? 0;
  const d = ident?.demand ?? {};

  /* ── 결론 한 문장 ── */
  let verdict: ReactNode;
  if (profErr) {
    verdict = <>{name} — <span className="value-absent">Platform 산출물이 없어 유형을 판정하지 않는다.</span></>;
  } else if (!ident) {
    verdict = <>{name} — <span className="value-absent">상권 정체성을 불러오는 중이다.</span></>;
  } else if (!ident.archetype || groups.length === 0) {
    verdict = <>{name} — <span className="value-absent">업종 근거가 없어 유형을 판정하지 않는다.</span></>;
  } else {
    verdict = (
      <>
        {name}은 <b>「{ident.archetype}」</b> 상권입니다.
      </>
    );
  }

  /* ── 근거 ── */
  const grounds: Ground[] = [];

  // ① 무엇이 모여 있나
  grounds.push({
    label: "무엇이 모여 있나",
    value: groups.length
      ? joinDot([
        ...groups.slice(0, 3).map((g) => <><b>{g.group}</b> {pct(g.share)} ({g.n.toLocaleString()}곳)</>),
        <>총 {total.toLocaleString()}곳 / {groups.length}군</>,
      ])
      : <span className="value-absent">업종 라벨 없음</span>,
    source: ident?.archetype_rule,
  });

  // ② 누가 · 언제 오나
  const peak = d.bands?.find((b) => b.band === d.peak_band);
  const gap = d.bands?.find((b) => b.band === d.gap_band);
  const topAge = [...(d.ages ?? [])].sort((a, b) => b.share - a.share)[0];
  const demandParts: ReactNode[] = [];
  if (peak) demandParts.push(<><b>{peak.label}</b> 유동 최다</>);
  if (gap) demandParts.push(<><b>{gap.label}</b> 빈틈</>);
  if (topAge) demandParts.push(<>{topAge.band} {topAge.share.toFixed(1)}%</>);
  if (d.female_share != null) demandParts.push(<>여성 {d.female_share.toFixed(1)}%</>);
  if (d.weekend_flpop != null) demandParts.push(<>주말 유동 {d.weekend_flpop.toFixed(1)}%</>);
  if (d.store_count != null) demandParts.push(<>점포 {Math.round(d.store_count).toLocaleString()}곳</>);
  grounds.push({
    label: "누가 · 언제 오나",
    value: demandParts.length ? joinDot(demandParts) : <span className="value-absent">TRDAR 수요신호 없음</span>,
    source: `서울 상권분석 TRDAR 상권 단위${d.trdar_n ? ` · TRDAR 상권 ${d.trdar_n}개` : ""}`
      + " · 빈틈은 유동 대비 매출이 가장 낮은 구간(0~6시 제외)",
  });

  // ③ 밖에서 뭐라고 불리나
  const words = ident?.keywords.words ?? [];
  const trends = ident?.trends ?? [];
  const repParts: ReactNode[] = words.slice(0, 3).map((w) => <>「{w.word}」 {w.n}회</>);
  if (trends[0]) {
    const t = trends[0];
    repParts.push(
      <>검색 「{t.keyword}」 <b className={`tr-${t.direction}`}>{dirMark(t.direction)} {t.change_pct > 0 ? "+" : ""}{t.change_pct}%</b></>,
    );
  }
  grounds.push({
    label: "밖에서 뭐라고 불리나",
    value: repParts.length ? joinDot(repParts) : <span className="value-absent">블로그 언급 없음</span>,
    source: ident
      ? `네이버 블로그 언급 빈도 — 토큰 ${ident.keywords.scanned}개 중 일반어 ${ident.keywords.dropped}개 표시 제외`
        + `(감성이 아니라 빈도다) · 트렌드 ${trends.length}계열은 네이버 데이터랩 최근 3개월 대 직전 3개월`
      : undefined,
  });

  // ④ 어디로 가고 있나 — 네 줄째라 접힌다. 규칙이 세 줄이지 값이 셋인 것은 아니다.
  if (fc && fc.model !== "lstm-stub") {
    const approx = approxVacancyPct(fc, hub);
    grounds.push({
      label: "어디로 가고 있나",
      value: (
        <>
          공실 프록시 <b>{fc.last_vac_proxy.toFixed(3)}</b> → <b>{fc.forecast_vac_proxy.toFixed(3)}</b>
          {" "}({signed(fc.delta)})
          {approx != null && hub?.vacancy_rate != null && (
            <> · 공실률 환산 {hub.vacancy_rate.toFixed(1)}% → {approx.toFixed(1)}%</>
          )}
          {approx == null && hub?.vacancy_withheld && (
            <> · <span className="value-absent">대표 공실률을 내린 거점이라 % 환산 없음</span></>
          )}
        </>
      ),
      source: `LSTM ${fc.model} · ${quarterLabel(fc.last_quarter)} 관측 → `
        + `${quarterLabel(fc.forecast_quarter ?? fc.horizons[fc.horizon_quarters - 1]?.quarter)} 예측`
        + " · 단위는 vac_proxy 다(%는 delta 를 현재 공실률에 더한 근사)",
    });
  }

  /* ── 출처 — 아래가 전부 접혀도 남는다 ── */
  const sources: ReactNode[] = [];
  if (ident) sources.push(ident.source);
  if (prof?.openings) sources.push(prof.openings.source);
  if (fc && fc.model !== "lstm-stub") {
    sources.push(`LSTM ${fc.model}${fc.trained_at ? ` · 학습 ${fc.trained_at.slice(0, 10)}` : ""}`);
  }
  if (fc?.ground_anchor) {
    const a = fc.ground_anchor;
    sources.push(
      `${VACANCY_LABEL.anchor}${a.anchor_street_pct != null ? ` ${a.anchor_street_pct.toFixed(1)}%` : ""}`
      + ` · ${VACANCY_LABEL.contrast} ${a.estimated_vacancy_pct?.toFixed(1)}%`
      + `${a.buildings_used ? ` (${a.buildings_used.toLocaleString()}동)` : ""} · ${a.source} ${a.as_of}`,
    );
  }
  if (rec && rec.model !== "gnn-stub") {
    sources.push(`GNN ${rec.model}${rec.metrics?.nodes ? ` · 노드 ${rec.metrics.nodes.toLocaleString()}개` : ""}`);
  }
  if (hub) {
    sources.push(`거점 공실 ${hub.vacancy_source === "gold" ? "실측 건물 집계" : "합성 그리드"}`);
  }
  if (zones?.length) sources.push(`행정동 구역 ${zones.length}개 실측`);

  return { verdict, grounds, sources };
}

/** 「모델 근거」가 접힌 채로도 무엇이 들어 있는지 — 두 모델의 대표 수치 한 줄. */
function modelFoldSummary(fc: VacancyForecast | null, rec: IndustryRecommend | null): ReactNode {
  const parts: ReactNode[] = [];
  if (fc && fc.model !== "lstm-stub") parts.push(lstmPromoted(fc.skill) ? "공실률 추정 전망" : "현재 공실률 기준");
  if (rec && rec.model !== "gnn-stub" && rec.recommendations.length) {
    parts.push(<>추천 1위 <b>{rec.recommendations[0].industry}</b> {pct(rec.recommendations[0].score)}</>);
  }
  return parts.length ? joinDot(parts) : "전망과 추천 정보 확인";
}

/* ───────────────── ① 이 상권은 어떤 플랫폼인가 (원자료) ───────────────── */

function IdentitySection({ ident, hub }: { ident: NonNullable<PlatformProfile["identity"]>; hub?: DistrictSummary }) {
  const { categories: cats, keywords, trends, demand } = ident;
  const total = cats.total || 1;
  const ungroupedN = cats.ungrouped.reduce((s, u) => s + u.n, 0);
  const maxKw = keywords.words[0]?.n ?? 1;
  const bands = demand.bands ?? [];
  const maxBand = Math.max(...bands.map((b) => Math.max(b.flpop, b.selng ?? 0)), 1);
  const maxAge = Math.max(...(demand.ages ?? []).map((a) => a.share), 1);

  return (
    <Fold title="상권 특성 자세히 보기"
      summary={<>업종 {cats.total.toLocaleString()}곳 / {cats.groups.length}군 · 시간대 {bands.length}구간
        · 키워드 {keywords.words.length}개 · 트렌드 {trends.length}계열</>}>
      <div className="herotop">
        <div>
          <div className="herolabel">이 상권의 유형</div>
          <div className="heroarch">{ident.archetype ?? "판정할 업종 근거가 없다"}</div>
        </div>
        {hub && (
          <div className="herokpis">
            {demand.store_count != null && (
              <div className="kpi"><div className="l">점포</div><div className="v">{Math.round(demand.store_count).toLocaleString()}<small>곳</small></div></div>
            )}
            {demand.franchise_share != null && (
              <div className="kpi"><div className="l">프랜차이즈</div><div className="v">{demand.franchise_share.toFixed(1)}<small>%</small></div></div>
            )}
            {demand.open_rate != null && demand.close_rate != null && (
              <div className="kpi">
                <div className="l">개업 / 폐업률</div>
                <div className="v">{demand.open_rate.toFixed(1)}<small>/ {demand.close_rate.toFixed(1)}%</small></div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="herogrid">
        {/* 무엇이 모여 있나 */}
        <div className="panel">
          <h3>무엇이 모여 있나<small>업종 구성 {cats.total.toLocaleString()}곳</small></h3>
          <div className="stack">
            {cats.groups.map((g, i) => (
              <i key={g.group} style={{ width: `${(g.n / total) * 100}%`, background: GROUP_COLORS[i % GROUP_COLORS.length] }}
                 title={`${g.group} ${g.n}곳 (${pct(g.share)})`} />
            ))}
            {ungroupedN > 0 && (
              <i style={{ width: `${(ungroupedN / total) * 100}%`, background: UNGROUPED_COLOR }} title={`미분류 ${ungroupedN}곳`} />
            )}
          </div>
          <div className="glegend">
            {cats.groups.map((g, i) => (
              <details key={g.group} className="gitem">
                <summary>
                  <i style={{ background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
                  <b>{g.group}</b>
                  <span>{g.n}곳 · {pct(g.share)}</span>
                </summary>
                {/* 묶음이 근거를 가리지 않게 — 어떤 라벨이 이 군에 들어갔는지 펼쳐 본다 */}
                <div className="gmembers">
                  {g.members.map((m) => <span key={m.label} className="kw">{m.label} {m.n}</span>)}
                </div>
              </details>
            ))}
            {ungroupedN > 0 && (
              <details className="gitem">
                <summary>
                  <i style={{ background: UNGROUPED_COLOR }} />
                  <b>미분류</b>
                  <span>{ungroupedN}곳 · {pct(ungroupedN / total)}</span>
                </summary>
                <div className="gmembers">
                  {cats.ungrouped.map((m) => <span key={m.label} className="kw">{m.label} {m.n}</span>)}
                </div>
                <div className="pnote">
                  업종을 확인할 수 없는 점포입니다.
                </div>
              </details>
            )}
          </div>
        </div>

        {/* 누가·언제 오나 */}
        <div className="panel">
          <h3>누가 · 언제 오나<small>방문 고객과 시간대</small></h3>
          {demand.ages && demand.ages.length > 0 && (
            <div className="ages">
              {demand.ages.map((a) => (
                <div key={a.band} className="agecol">
                  <div className="agebarwrap">
                    <i style={{ height: `${(a.share / maxAge) * 100}%` }} />
                  </div>
                  <div className="agev">{a.share.toFixed(0)}</div>
                  <div className="agel">{a.band}</div>
                </div>
              ))}
            </div>
          )}
          <div className="minirow">
            {demand.female_share != null && <span className="chip">여성 {demand.female_share.toFixed(1)}%</span>}
            {demand.weekend_flpop != null && <span className="chip">주말 유동 {demand.weekend_flpop.toFixed(1)}%</span>}
            {demand.weekend_selng != null && <span className="chip">주말 매출 {demand.weekend_selng.toFixed(1)}%</span>}
          </div>

          {bands.length > 0 && (
            <>
              <div className="bandhd">시간대 · 유동 대비 매출</div>
              {bands.map((b) => (
                <div key={b.band} className={`bandrow${b.band === demand.peak_band ? " peak" : ""}${b.band === demand.gap_band ? " gap" : ""}`}>
                  <span className="bl">{b.label}</span>
                  <span className="bbar">
                    <i className="f" style={{ width: `${(b.flpop / maxBand) * 100}%` }} />
                    <i className="s" style={{ width: `${((b.selng ?? 0) / maxBand) * 100}%` }} />
                  </span>
                  <span className="bv">
                    {b.band === demand.peak_band ? "최다" : b.band === demand.gap_band ? "빈틈" : ""}
                  </span>
                </div>
              ))}
              <div className="pnote">
                위 막대 = 유동인구 비중, 아래 = 매출 비중. <b>빈틈</b>은 유동 대비 매출이 가장
                낮은 구간(0~6시는 가게가 닫혀 있어 제외)이라, 이 상권이 사람은 있는데
                돈이 안 도는 시간이다.
              </div>
            </>
          )}
        </div>

        {/* 밖에서 뭐라고 불리나 */}
        <div className="panel">
          <h3>밖에서 뭐라고 불리나<small>블로그 언급 · 검색 트렌드</small></h3>
          <div className="kwcloud">
            {keywords.words.map((w) => (
              <span key={w.word} className="kwc"
                style={{ fontSize: `${11 + (w.n / maxKw) * 7}px`, opacity: 0.55 + (w.n / maxKw) * 0.45 }}>
                {w.word}<i>{w.n}</i>
              </span>
            ))}
          </div>
          <div className="pnote">
            자주 언급되는 단어입니다. 긍정·부정 평가를 뜻하지 않습니다.
          </div>

          {trends.length > 0 && (
            <div className="trends">
              {trends.map((t) => (
                <div key={t.keyword} className="trend">
                  <div className="trhd">
                    <b>{t.keyword}</b>
                    <span className={`trdir ${t.direction}`}>
                      {t.direction === "up" ? "▲ 상승" : t.direction === "down" ? "▼ 하락" : "— 보합"}
                      {" "}{t.change_pct > 0 ? "+" : ""}{t.change_pct}%
                    </span>
                  </div>
                  <Spark points={t.points.map((p) => p.value)} direction={t.direction} />
                  <div className="trmeta">
                    직전 3개월 {t.prior} → 최근 3개월 {t.recent}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </Fold>
  );
}

/** 검색 트렌드 스파크라인 — 값의 절대 눈금이 아니라 흐름을 보여주는 용도다. */
function Spark({ points, direction }: { points: number[]; direction: string }) {
  if (points.length < 2) return null;
  const w = 100, h = 28;
  const min = Math.min(...points), max = Math.max(...points);
  const span = Math.max(1e-9, max - min);
  const d = points
    .map((v, i) => `${(i / (points.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`)
    .join(" ");
  const color = direction === "up" ? "#E03E36" : direction === "down" ? "#2E6FB7" : "#8A93A0";
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.6"
        strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* ───────────────── ② 어느 자리에 어떤 업소가 ───────────────── */

function OpeningsSection({ openings, districtName, selectedIds, onToggle: toggleSite, onClear, onOpenInPage, mySite }: {
  openings: PlatformProfile["openings"]; districtName: string;
  /** 3판 — 창업·옮기기 · 서빙 어휘(산출물 기준) 안 업종이면 자리가 이 업종 점수 순으로 온다 */
  mySite?: { label: string; input: string } | null;
  onOpenInPage?: (site: OpeningSite) => void;
  /** 비교 후보 — 지도 칩과 공유하므로 상위(PlatformConsole)가 든다 */
  selectedIds: string[]; onToggle: (id: string) => void; onClear: () => void;
}) {
  const [shown, setShown] = useState(SITES_PAGE);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const comparisonId = useId();
  const selectionHintId = useId();
  const sites = openings.sites;
  const selectedSites = selectedIds.flatMap((id) => sites.filter((site) => site.unit_id === id));
  const canCompare = selectedSites.length >= 2;
  // 한 번 고르면 펼친 채로 둔다 — 마지막 후보를 해제했다고 사용자 손 밑에서 접히면 안 된다.
  const [pinnedOpen, setPinnedOpen] = useState(false);
  useEffect(() => { if (selectedIds.length > 0) setPinnedOpen(true); }, [selectedIds.length]);
  // 한 지번에 자리가 여럿이면 이름이 똑같이 찍힌다(신사동 552-19 가 3곳). 좌표가 다른
  // 별개의 자리인데 화면에서는 중복 버그처럼 보이므로, 겹칠 때만 유닛 번호를 붙인다.
  const dupNames = useMemo(() => {
    const seen = new Map<string, number>();
    sites.forEach((s) => seen.set(s.name, (seen.get(s.name) ?? 0) + 1));
    return seen;
  }, [sites]);

  return (
    // 지도 칩으로 후보를 고르면 이 접힌 자리를 편다 — 고른 결과가 접힌 채 안 보이면
    // 칩을 눌러도 아무 일이 안 일어난 것처럼 읽힌다.
    <Fold title="어느 자리에 어떤 업소가 들어오면 좋나" badge="실측 공실" open={pinnedOpen || undefined}
      summary={<>공실 <b>{openings.unit_count}곳</b> · 추천이 붙은 자리 <b>{openings.matched_count}곳</b>
        {" · "}{mySite ? <><b>{mySite.input}</b> 점수 높은 자리부터</> : "상권 평균과 가장 다른 자리부터"}</>}>

      {sites.length === 0 && <div className="loading">이 상권에는 실측 공실 자리가 없다.</div>}

      {sites.length > 0 && (
        <>
          <section className="site-selection" aria-label="현재 비교 후보">
            <div className="site-selection-head">
              <div>
                <h3>{districtName}의 자리 비교</h3>
                <p>같은 상권의 공실 {openings.unit_count}곳 · 추천 매칭 반경 {openings.match_radius_m}m</p>
              </div>
              <span className="site-selection-count" role="status" aria-live="polite">
                비교 후보 {selectedSites.length}/3곳
              </span>
            </div>
            <p id={selectionHintId}>
              {selectedSites.length === 3
                ? "최대 3곳을 선택했습니다. 다른 자리를 고르려면 선택한 후보를 해제하세요."
                : "아래에서 2~3곳을 선택해 면적·층·추천 근거를 나란히 확인하세요."}
            </p>
            {selectedSites.length > 0 && (
              <ul className="site-selection-list">
                {selectedSites.map((site) => (
                  <li key={site.unit_id}>
                    <span>{site.name}<small>{site.unit_id}</small></span>
                    <button type="button" onClick={() => toggleSite(site.unit_id)}
                      aria-label={`${site.name} (${site.unit_id}) 비교에서 제외`}>해제</button>
                  </li>
                ))}
              </ul>
            )}
            <div className="site-selection-actions">
              <Button type="button" disabled={!canCompare} aria-controls={comparisonId}
                aria-expanded={canCompare && comparisonOpen}
                onClick={() => setComparisonOpen((open) => !open)}>
                {canCompare && comparisonOpen ? "비교 접기" : `선택한 ${selectedSites.length}곳 비교`}
              </Button>
              {selectedSites.length > 0 && (
                <Button type="button" variant="ghost" onClick={() => {
                  onClear(); setComparisonOpen(false);
                }}>선택 초기화</Button>
              )}
            </div>
          </section>
          <div id={comparisonId}>
            {canCompare && comparisonOpen && (
              <PlatformComparison sites={selectedSites} districtName={districtName}
                source={openings.source} distinctNote={openings.distinct_note} />
            )}
          </div>
          <fieldset className="site-candidates" aria-describedby={selectionHintId}>
            <legend>비교할 자리 선택</legend>
            <div className="sites">
              {sites.slice(0, shown).map((s) => (
                <SiteCard key={s.unit_id} site={s}
                  seq={(dupNames.get(s.name) ?? 0) > 1 ? s.unit_id.split("-").pop() ?? null : null}
                  selected={selectedIds.includes(s.unit_id)}
                  disabled={selectedIds.length >= 3 && !selectedIds.includes(s.unit_id)}
                  onToggle={() => toggleSite(s.unit_id)}
                  onOpenInPage={onOpenInPage && s.unit_id.startsWith(UNIT_PREFIX) ? () => onOpenInPage(s) : undefined} />
              ))}
            </div>
          </fieldset>
        </>
      )}

      {sites.length > shown && (
        <Button variant="ghost" className="more" onClick={() => setShown((n) => n + SITES_PAGE)}>
          자리 {sites.length - shown}곳 더 보기
        </Button>
      )}

      <div className="sitesrc">
        추천 점수는 입점 성공 확률이 아닙니다. 직전 업종과 추천 업종은 분류 기준이 다릅니다.
      </div>
    </Fold>
  );
}

/** 자리 id 규약 — build_vacant_units.py 가 `vu-{건물 id}` 로 만든다. Posting 인계와 같은 계약이다. */
const UNIT_PREFIX = "vu-";

/** 자리 → Page 건물 선택. 건물 id 는 규약에서 뗀 값만 쓴다(이름·좌표로 추측하지 않는다). */
function siteToBuilding(districtId: string, site: OpeningSite): BuildingSelection {
  return { districtId, buildingId: site.unit_id.slice(UNIT_PREFIX.length), buildingName: site.name };
}

function SiteCard({ site, seq, selected, disabled, onToggle, onOpenInPage }: {
  site: OpeningSite; seq: string | null;
  selected: boolean; disabled: boolean; onToggle: () => void;
  onOpenInPage?: () => void;
}) {
  const max = site.recommendations[0]?.score ?? 1;
  return (
    <Card className={`site${selected ? " is-selected" : ""}`}>
      <label className="site-select">
        <input type="checkbox" checked={selected} disabled={disabled} onChange={onToggle}
          aria-label={`${site.name} (${site.unit_id}) 비교 후보 선택`} />
        <span>{selected ? "비교 후보에 추가됨" : "비교 후보로 선택"}</span>
      </label>
      <div className="sitehd">
        <span className="sname" title={site.name}>
          {site.name}{seq && <em> · 자리 {seq}</em>}
        </span>
        {site.matched_distance_m != null && (
          <span className="sdist" title="공실 자리에서 추천 그래프 노드까지 거리">{site.matched_distance_m}m</span>
        )}
      </div>
      <div className="smeta">
        {site.area_py != null ? `${site.area_py}평` : "면적 미제공"}
        {` · ${site.floor || "층 미제공"}`}
        {site.capacity != null && ` · ${site.capacity}호`}
        {site.vacancy_rate != null ? ` · 공실 ${site.vacancy_rate}%` : " · 공실률 미제공"}
      </div>

      {site.recommendations.length > 0 ? (
        <div className="srecs">
          {site.recommendations.map((r, i) => (
            <div key={r.industry} className={`srec${i === 0 ? " top" : ""}`}>
              <span className="ri">{r.industry}</span>
              <span className="rb"><i style={{ width: `${(r.score / max) * 100}%` }} /></span>
              <span className="rs">{pct(r.score)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="snorec">
          이 자리의 추천 정보가 없습니다.
        </div>
      )}

      {/* 이 자리만의 신호 — 상권 평균을 뺀 값. 없으면 그리지 않는다(0 을 신호처럼 보이게 하지 않는다) */}
      {site.distinct && (
        <div className="sdistinct">
          상권 평균 대비 <b>{site.distinct.industry}</b>
          <span>{site.distinct.delta_pp > 0 ? "+" : ""}{site.distinct.delta_pp}p</span>
        </div>
      )}

      {site.was && <div className="swas">직전 업종 <b>{site.was}</b></div>}
      {onOpenInPage && (
        <button type="button" className="site-open-page" onClick={onOpenInPage}
          aria-label={`${site.name} Page에서 이 건물 보기`}>Page에서 이 건물 보기 →</button>
      )}
    </Card>
  );
}

/* ───────────────── 근거 ①: LSTM 공실 예측 ───────────────── */

function ForecastCard({ fc, err, quarters, onQuarters, hub }: {
  fc: VacancyForecast | null; err: string | null;
  quarters: number; onQuarters: (q: number) => void; hub?: DistrictSummary;
}) {
  const stub = fc?.model === "lstm-stub";
  const promoted = lstmPromoted(fc?.skill ?? null);
  const baseVac = hub?.vacancy_rate ?? null;
  const approxPct = approxVacancyPct(fc, hub);
  return (
    <section className="card">
      <div className="chead"><h2>공실 전망 <span className="badge is-warn">{promoted ? "추정" : "현재값 기준"}</span></h2></div>
      {err && <div className="empty">이 상권의 전망 정보를 제공할 수 없습니다.</div>}
      {!err && !fc && <div className="empty">전망 불러오는 중…</div>}
      {stub && <div className="empty">예시 데이터입니다. 실제 상권 전망으로 사용할 수 없습니다.</div>}
      {fc && !stub && <>
        {promoted && <div className="seg" role="group" aria-label="전망 기간">
          {QUARTERS.map((q) => <button key={q} aria-pressed={quarters === q} className={quarters === q ? "on" : ""} onClick={() => onQuarters(q)}>+{q}분기</button>)}
        </div>}
        <div className="big"><div className="bigval">
          <MeasuredValue value={promoted ? approxPct : baseVac} unit="%" absent={hub?.vacancy_withheld ? "대표값 미제공" : "정보 없음"} />
          <small>{promoted ? quarterLabel(fc.forecast_quarter ?? fc.horizons[fc.horizon_quarters - 1]?.quarter) : "다음 분기 참고값"}</small>
        </div></div>
        <p className="recnote">{promoted
          ? "현재 공실률에 예상 변화를 반영한 근사값입니다."
          : "예측의 신뢰성을 확인 중이므로 현재 공실률을 참고값으로 표시합니다. 미래 변화가 없다는 뜻은 아닙니다."}</p>
      </>}
    </section>
  );
}

function RecommendCard({ rec, err }: { rec: IndustryRecommend | null; err: string | null }) {
  const stub = rec?.model === "gnn-stub";
  const max = rec?.recommendations.length ? rec.recommendations[0].score : 1;
  return (
    <section className="card">
      <div className="chead"><h2>추천 업종 <span className="badge is-model">AI 추천</span></h2></div>
      {err && <div className="empty">이 상권의 추천 정보를 제공할 수 없습니다.</div>}
      {!err && !rec && <div className="empty">추천 불러오는 중…</div>}
      {stub && <div className="empty">예시 데이터입니다. 실제 입점 판단에 사용할 수 없습니다.</div>}
      {rec && !stub && rec.recommendations.length === 0 && <div className="empty">이 상권의 추천 정보가 없습니다.</div>}
      {rec && !stub && rec.recommendations.length > 0 && <>
        <div className="recs">{rec.recommendations.map((r, i) => (
          <div key={r.industry} className={`recrow${i === 0 ? " top" : ""}`}>
            <span className="rank">{i + 1}</span><span className="rind">{r.industry}</span>
            <span className="rbar"><i style={{ width: `${(r.score / max) * 100}%` }} /></span><span className="rsc">{pct(r.score)}</span>
          </div>
        ))}</div>
        <p className="recnote">상권 전체의 추천 점수이며 입점 성공 확률이 아닙니다. 개별 공간의 추천은 자리 목록에서 확인하세요.</p>
      </>}
    </section>
  );
}

/* ───────────────── 감성 (시드) ───────────────── */

/** 구역 공실률 색 — 거점 카드와 같은 눈금을 쓴다(두 화면이 다른 색을 내면 안 된다). */
function zoneVacHex(v: number): string {
  if (v >= 25) return "#D95C4A";
  if (v >= 15) return "#E0A03A";
  return "#22B07D";
}

function SentimentSection({ zones, hub }: { zones: Zone[] | null; hub?: DistrictSummary }) {
  return (
    <Fold title="동네별 공실 현황" badge="행정동 실측"
      summary={zones === null ? "구역 불러오는 중…" : `행정동 ${zones.length}개`}>
      <div className="zonenote">행정동별 점포·건물 수와 공실률을 비교하세요.</div>
      {hub && <CaveatNote district={hub} />}
      {!zones && <div className="empty">구역 불러오는 중…</div>}
      {zones && zones.length === 0 && (
        <div className="empty">이 상권의 동네별 정보가 아직 없습니다.</div>
      )}
      {zones && zones.length === 1 && (
        <div className="zonesum">이 거점은 <b>행정동 하나</b> 안에 있다 — 구역이 거점 전체와 같다.</div>
      )}
      <div className="zones">
        {(zones ?? []).map((z) => (
          <div key={z.id} className="zone">
            <div className="zhead">
              <span className="zname">{z.n}</span>
              <span className="zscore"
                    style={{ color: z.vacancy_rate === null ? undefined : zoneVacHex(z.vacancy_rate) }}>
                {z.vacancy_rate === null ? "—" : `${z.vacancy_rate.toFixed(1)}%`}
              </span>
            </div>
            <div className="zmeta">
              {z.grp} · 점포 {z.stores?.toLocaleString() ?? "—"} · 건물 {z.buildings ?? "—"}동
              {z.capacity !== null && ` · 상업 ${z.capacity.toLocaleString()}호`}
            </div>
            {/* 감성이 들어오면 그때 그린다. 지금은 없다는 사실을 그린다 — 빈 칸으로 두면
                "0 인가 없는 건가"를 화면이 말해 주지 않는다. */}
            <div className="zsent">
              {z.s === null
                ? <span className="value-absent">감성 실측 없음</span>
                : <>감성 {z.s.toFixed(1)}
                    {z.d !== null && <> · {z.d >= 0 ? "▲" : "▼"}{Math.abs(z.d).toFixed(1)}</>}</>}
            </div>
            {z.f.length > 0 && (
              <div className="zkw">
                {z.f.map(([label, delta], i) => <span key={i} className="kw">{label} {delta}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </Fold>
  );
}
