/**
 * ② 빈 자리(PAGE) — 화면설계서 5판 §5-2: Q5 월세 상한 · R3 빈 자리 목록 · R4 자리 상세.
 *
 * 자리 하나 = (건물, 층). 세 응답을 같은 id 로 묶는다:
 *   임대시세 `listings[]`(vfu-… · 추정 월세) ⨝ 층 공실 `units[]`(vfu-… · 직전 업종·층 근거·관측 업종)
 *   본전 계산 가능 = 그 건물의 회수기간 유닛(`"vu-" + building_id`)이 postings 에 있다.
 * 층으로 쪼갠 자리로 회수기간을 내지 않는다(feature-posting §0-Q) — 계산은 건물 단위 유닛으로만.
 */
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { recommendIndustry } from "@/lib/api";
import { kakaoMapUrl } from "@/lib/externalMap";
import { loadNaverMaps } from "@/lib/naverMap";
import { useFlow, useResume, useSaved } from "../context";
import { httpStatus, useFlowData, useLoad } from "../data";
import { floorText, useSpaces, type SpaceItem } from "../spaces";
import { eun } from "../format";
import { go, replace } from "../route";
import { setSpace, type SpaceBrowse } from "../state";
import {
  Badge, BottomCTA, ChoiceList, Details, FlowScreen, LoadError, ResultView, SaveHeart, Sheet,
  SkeletonRows, TextButton, WarnLine,
} from "../ui";
import { hasRanking, useDistrictName, useNeed, useWorkIndustry } from "./common";

const BuildingViewer = lazy(() => import("@/components/BuildingViewer"));

/* ── 층 그림 — 썸네일 자리에 데이터인 그림(§5-2 R3) ──────────────────────── */

const MAX_FLOORS = 8;

export function FloorStack({ item, siblings, big }: { item: SpaceItem; siblings: SpaceItem[]; big?: boolean }) {
  const u = item.unit;
  const total = Math.max(1, u?.bld_floors ?? Math.max(item.floor, 1));
  const vacant = new Map<number, "confirmed" | "probable">();
  for (const s of siblings) if (s.buildingId && s.buildingId === item.buildingId) vacant.set(s.floor, s.certainty);
  vacant.set(item.floor, item.certainty);
  const occ = new Set(u?.occ_floors ?? []);
  const com = new Set(u?.com_floors ?? []);
  const top = Math.min(total, Math.max(MAX_FLOORS, item.floor));
  const bottom = Math.max(1, top - MAX_FLOORS + 1);
  const floors = Array.from({ length: top - bottom + 1 }, (_, i) => top - i);
  const kind = (f: number) => vacant.get(f) === "confirmed" ? "is-vacant" : vacant.get(f) === "probable" ? "is-probable"
    : occ.has(f) ? "is-occupied" : com.has(f) ? "is-unknown" : "is-noncom";
  const vacantList = [...vacant.keys()].filter((f) => f >= 1).sort((a, b) => a - b).map((f) => `${f}층`).join("·");
  const label = `${total}층 건물 · 빈 층 ${vacantList || "없음"}${occ.size ? ` · 영업 중 ${occ.size}개 층` : ""}`;
  return (
    <div className={"fl-stack" + (big ? " is-big" : "")} role="img" aria-label={label}>
      {top < total && <span className="fl-stack-more">+{total - top}층</span>}
      {floors.map((f) => (
        <span key={f} className={`fl-stack-floor ${kind(f)}${f === item.floor ? " is-here" : ""}`}>{big ? `${f}층` : ""}</span>
      ))}
      {item.floor < 1 && <span className="fl-stack-basement">{floorText(item.floor)}</span>}
    </div>
  );
}

export const StackLegend = () => (
  <p className="fl-legend" aria-hidden="true">
    <span><i className="is-vacant" />빈 층</span><span><i className="is-probable" />빈 층 추정</span>
    <span><i className="is-occupied" />영업 중</span><span><i className="is-noncom" />상가 아님·미상</span>
  </p>
);

/* ── Q5 월세 상한 ─────────────────────────────────────────────────────────── */

const CAPS: { value: string; cap: number | null; title: string }[] = [
  { value: "300", cap: 300, title: "300만원까지" },
  { value: "500", cap: 500, title: "500만원까지" },
  { value: "1000", cap: 1000, title: "1,000만원까지" },
  { value: "all", cap: null, title: "아직 몰라요 · 다 볼게요" },
];

export function RentCapChoices({ counts, value, onChoose }: { counts: ((cap: number | null) => number) | null; value: string | null; onChoose: (cap: number | null) => void }) {
  return <ChoiceList label="월세 상한" value={value}
    options={CAPS.map((c) => ({ value: c.value, title: c.title, aside: counts ? `${counts(c.cap)}곳` : undefined }))}
    onChoose={(v) => onChoose(CAPS.find((c) => c.value === v)!.cap)} />;
}

export function RentCap() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const id = state.districtId;
  const ok = useNeed(!!id, "/district-search");
  const rent = useLoad(id ? `rent:${id}` : null, () => data.rent(id!));
  const name = useDistrictName(id);
  const noRent = rent.status === "error" && httpStatus(rent.error) === 404;
  // 임대료 통계가 없는 상권 — 이 질문을 건너뛰고 월세 없이 목록으로(§5-2 Q5)
  useEffect(() => {
    if (!noRent) return;
    update((s) => ({ ...s, rentCap: null, rentCapAnswered: true }));
    replace("/spaces");
  }, [noRent, update]);
  if (!ok || noRent) return null;
  const choose = (cap: number | null) => {
    update((s) => ({ ...s, rentCap: cap, rentCapAnswered: true }));
    if (id) data.prefetch(() => data.floorUnits(id), () => data.postings(id));
    go("/spaces");
  };
  const counts = rent.status === "ready" ? (cap: number | null) => rent.data.listings.filter((l) => cap == null || l.monthly_rent <= cap).length : null;
  const current = state.rentCapAnswered ? (state.rentCap == null ? "all" : String(state.rentCap)) : null;
  return (
    <FlowScreen back={id ? `/district/${encodeURIComponent(id)}` : "/districts"} caption={`빈 자리 · ${name ?? "상권"}`}
      title="월세는 얼마까지 생각하세요?" sub="보증금·권리금·관리비는 빼고, 추정 월세로 걸러 드려요.">
      {rent.status === "loading" && <SkeletonRows n={4} />}
      {rent.status === "error" && !noRent && <LoadError what="월세 자료" error={rent.error} onRetry={rent.retry} />}
      {rent.status === "ready" && <RentCapChoices counts={counts} value={current} onChoose={choose} />}
    </FlowScreen>
  );
}

/* ── R3 빈 자리 목록 ─────────────────────────────────────────────────────── */

type SortKey = "rent" | "area" | "floor";
const PAGE = 24;

export function Spaces() {
  const { state, update, savedSpaces, toggleSaveSpace } = useFlowSaved();
  const id = state.districtId;
  const ok = useNeed(!!id, "/district-search");
  const spaces = useSpaces(id);
  const name = useDistrictName(id);
  const { first, confirmed, calcOnly, sort, shown } = state.spaceBrowse;
  const browse = (patch: Partial<SpaceBrowse>) => update((s) => ({ ...s, spaceBrowse: { ...s.spaceBrowse, shown: PAGE, ...patch } }));
  const setFirst = (value: boolean) => browse({ first: value });
  const setConfirmed = (value: boolean) => browse({ confirmed: value });
  const setCalcOnly = (value: boolean) => browse({ calcOnly: value });
  const setSort = (value: SortKey) => browse({ sort: value });
  const setShown = (value: number) => browse({ shown: value });
  const [capSheet, setCapSheet] = useState(false);
  const work = useWorkIndustry();
  if (!ok) return null;
  const cap = state.rentCap;
  const back = `/district/${encodeURIComponent(id!)}`;
  const caption = `빈 자리 · ${name ?? "상권"}${work ? ` · ${work.label}` : ""}`;
  if (spaces.status === "loading") return <FlowScreen wide back={back} caption={caption} title="빈 자리를 세고 있어요"><SkeletonRows n={4} label="빈 자리를 불러오는 중" /></FlowScreen>;
  if (spaces.status === "error") return <FlowScreen wide back={back} caption={caption} title="빈 자리를 불러오지 못했어요"><LoadError what="빈 자리" error={spaces.error} onRetry={spaces.retry} /></FlowScreen>;
  const all = spaces.data.items;
  const filtered = all.filter((s) => (cap == null || (s.monthlyRent != null && s.monthlyRent <= cap))
    && (!first || s.floor === 1) && (!confirmed || s.certainty === "confirmed") && (!calcOnly || s.calculable));
  const sorted = [...filtered].sort((a, b) => sort === "area" ? b.areaPy - a.areaPy
    : sort === "floor" ? (a.floor === 1 ? 0 : 1) - (b.floor === 1 ? 0 : 1) || (a.monthlyRent ?? 1e9) - (b.monthlyRent ?? 1e9)
      : (a.monthlyRent ?? 1e9) - (b.monthlyRent ?? 1e9));
  const title = all.length === 0 ? "이 상권은 층 단위 빈 자리 자료가 아직 없어요"
    : `${cap != null ? `월 ${cap.toLocaleString("ko-KR")}만원까지인 ` : ""}빈 자리가 ${filtered.length.toLocaleString("ko-KR")}곳 있어요`;
  const open = (s: SpaceItem) => { update((st) => setSpace(st, s.id, `${s.name} ${floorText(s.floor)}`)); go(`/space/${encodeURIComponent(s.id)}`); };
  return (
    // 「지도」 = PPPP 지도 탐색(#/explore). 흐름 안 지도로 돌리지 않는다(2026-10-21 PPPP 화면 보존 규칙)
    <FlowScreen wide back={back} caption={caption} titleLive title={title}
      right={<button type="button" className="fl-textbtn" onClick={() => go("/explore")}>지도</button>}>
      {all.length > 0 && <>
        <div className="fl-chips" role="group" aria-label="걸러 보기">
          {spaces.data.hasRent && (
            <button type="button" className={"fl-chip" + (cap != null ? " is-on" : "")} aria-haspopup="dialog" onClick={() => setCapSheet(true)}>
              {cap != null ? `${cap.toLocaleString("ko-KR")}만원까지` : "월세 전체"} ▾
            </button>
          )}
          <button type="button" className={"fl-chip" + (first ? " is-on" : "")} aria-pressed={first} onClick={() => setFirst(!first)}>1층</button>
          <button type="button" className={"fl-chip" + (confirmed ? " is-on" : "")} aria-pressed={confirmed} onClick={() => setConfirmed(!confirmed)}>확정만</button>
          <button type="button" className={"fl-chip" + (calcOnly ? " is-on" : "")} aria-pressed={calcOnly} onClick={() => setCalcOnly(!calcOnly)}>본전 계산 가능</button>
        </div>
        <label className="fl-sort">
          <span className="sr-only">정렬</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="rent">월세 낮은 순</option><option value="area">넓은 순</option><option value="floor">1층 먼저</option>
          </select>
        </label>
      </>}
      {all.length > 0 && filtered.length === 0 && (
        <ResultView title="조건에 맞는 빈 자리가 없어요" body="조건을 풀면 더 볼 수 있어요."
          action={{ label: "월세 조건 풀기", onClick: () => { update((s) => ({ ...s, rentCap: null })); setFirst(false); setConfirmed(false); setCalcOnly(false); } }} />
      )}
      {all.length === 0 && (
        <ResultView title="빈 층 목록을 만들 자료가 없어요" body="이 상권은 건축물대장 층 자료가 아직 들어오지 않았어요."
          action={{ label: "다른 상권 고르기", onClick: () => go("/district-search") }} />
      )}
      <ul className="fl-cards" aria-label="빈 자리">
        {sorted.slice(0, shown).map((s) => (
          <li key={s.id} className="fl-card">
            <button type="button" className="fl-card-btn" onClick={() => open(s)}>
              <span className="fl-card-thumb"><FloorStack item={s} siblings={all} /><span className="fl-card-floor">{floorText(s.floor)}</span></span>
              <span className="fl-card-title">{s.name}</span>
              <span className="fl-card-price">{s.monthlyRent != null ? `월 ${s.monthlyRent.toLocaleString("ko-KR")}만원 추정` : "월세 통계 없음"}</span>
              <span className="fl-card-sub">{s.areaPy}평 · 직전 {s.unit?.was || "미상"}</span>
              <span className="fl-card-badges">
                {s.certainty === "confirmed" ? <Badge tone="real">확정</Badge> : <Badge tone="est">추정</Badge>}
                {s.calculable && <Badge tone="primary">본전 계산</Badge>}
              </span>
            </button>
            <SaveHeart saved={savedSpaces.has(s.id)} label={`${s.name} ${floorText(s.floor)} 후보로 저장`} onClick={() => toggleSaveSpace(s, null)} />
          </li>
        ))}
      </ul>
      {sorted.length > shown && <button type="button" className="fl-more" onClick={() => setShown(shown + PAGE)}>더 보기 ({(sorted.length - shown).toLocaleString("ko-KR")}곳 남음)</button>}
      {all.length > 0 && <p className="fl-source">건축물대장·상가정보로 센 빈 층이에요. 실제 매물인지는 현장에서 꼭 확인해요.{spaces.data.quarter ? ` · 월세 R-ONE ${spaces.data.quarter} 기준 추정` : ""}</p>}
      <Sheet open={capSheet} onClose={() => setCapSheet(false)} title="월세는 얼마까지 생각하세요?">
        <RentCapChoices value={cap == null ? "all" : String(cap)}
          counts={(c) => all.filter((s) => c == null || (s.monthlyRent != null && s.monthlyRent <= c)).length}
          onChoose={(c) => { update((s) => ({ ...s, rentCap: c, rentCapAnswered: true })); setCapSheet(false); setShown(PAGE); }} />
      </Sheet>
    </FlowScreen>
  );
}

/* ── R4 자리 상세 ────────────────────────────────────────────────────────── */

/** 네이버 지도 — 이 화면에서만 SDK 를 부른다(F-13). 실패하면 회색 칸 + 카카오맵 링크(길이 끊기지 않게) */
function MiniMap({ lat, lng, name }: { lat: number; lng: number; name: string }) {
  const el = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    loadNaverMaps().then(() => {
      const naver = window.naver;
      if (!alive || !el.current || !naver?.maps) return;
      const at = new naver.maps.LatLng(lat, lng);
      const map = new naver.maps.Map(el.current, { center: at, zoom: 17, scaleControl: false, mapDataControl: false });
      new naver.maps.Marker({ position: at, map });
    }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [lat, lng]);
  return (
    <div className="fl-minimap">
      {failed ? <div className="fl-minimap-fallback"><span>지도를 불러오지 못했어요</span></div> : <div ref={el} className="fl-minimap-canvas" aria-label={`${name} 위치 지도`} role="img" />}
      <a className="fl-link fl-minimap-link" href={kakaoMapUrl({ lat, lng }, name)} target="_blank" rel="noopener noreferrer">카카오맵에서 보기</a>
    </div>
  );
}

export function SpaceDetail({ id }: { id: string }) {
  const { state, update, token, savedSpaces, toggleSaveSpace } = useFlowSaved();
  const did = state.districtId;
  const ok = useNeed(!!did, "/district-search");
  const spaces = useSpaces(did);
  const name = useDistrictName(did);
  const work = useWorkIndustry();
  const [viewer, setViewer] = useState(false);
  const item = spaces.status === "ready" ? spaces.data.items.find((s) => s.id === id) ?? null : null;
  const canRank = hasRanking(work) && !!item;
  const rec = useLoad(canRank && item && did ? `rec:${item.id}` : null,
    () => recommendIndustry({ district_id: did!, lat: item!.lat, lon: item!.lng }));
  const label = item ? `${item.name} ${floorText(item.floor)}` : null;
  useEffect(() => { if (item && label) update((s) => setSpace(s, item.id, label)); }, [item, label, update]);
  useResumeSave(item, () => item && toggleSaveSpace(item, true, null));
  if (!ok) return null;
  const caption = `${name ?? "상권"}${item ? ` · ${floorText(item.floor)} · ${item.areaPy}평(${item.areaM2}㎡)` : ""}`;
  if (spaces.status === "loading") return <FlowScreen back="/spaces" caption={caption} title="자리를 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (spaces.status === "error") return <FlowScreen back="/spaces" caption={caption} title="자리를 불러오지 못했어요"><LoadError what="자리" error={spaces.error} onRetry={spaces.retry} /></FlowScreen>;
  if (!item) {
    return <FlowScreen back="/spaces" title="이 자리를 찾지 못했어요">
      <ResultView title="목록에서 사라진 자리예요" body="자료가 새로 들어오면서 빠졌을 수 있어요." action={{ label: "빈 자리 보기", onClick: () => go("/spaces") }} />
    </FlowScreen>;
  }
  const saved = savedSpaces.has(item.id);
  const custom = state.industryKey === "other" && state.goal !== "pivot";
  const calculable = item.calculable && !custom && !!work;
  const recRank = rec.status === "ready" && work?.model_label
    ? rec.data.recommendations.findIndex((r) => r.industry === work.model_label) : -1;
  const fit = item.unit?.fit;
  return (
    <FlowScreen back="/spaces" caption={caption} title={`${item.name} ${floorText(item.floor)}`}
      right={<SaveHeart saved={saved} onClick={() => toggleSaveSpace(item, !saved, "save-space")} />}
      cta={calculable
        ? <BottomCTA primary={{ label: "몇 달이면 본전인지 보기", onClick: () => go("/premium") }}
            secondary={{ label: saved ? "저장됨" : "저장", onClick: () => toggleSaveSpace(item, !saved, "save-space") }} />
        : <BottomCTA note={custom ? "직접 적은 업종은 본전 시점을 계산하지 않아요." : "본전 시점은 건물 단위 자리만 계산해요."}
            primary={{ label: saved ? "후보에 저장했어요" : "후보로 저장하기", onClick: () => toggleSaveSpace(item, true, "save-space"), disabled: saved }} />}>
      <MiniMap lat={item.lat} lng={item.lng} name={item.name} />
      <dl className="fl-keys">
        <div><dt>월세 추정</dt><dd>{item.monthlyRent != null ? `${item.monthlyRent.toLocaleString("ko-KR")}만원` : "통계 없음"}</dd></div>
        <div><dt>평당</dt><dd>{item.rentPerPyeong != null ? `${item.rentPerPyeong}만원` : "—"}</dd></div>
        <div><dt>빈 자리</dt><dd>{item.certainty === "confirmed" ? "확정" : "추정"}</dd></div>
      </dl>
      <WarnLine>호가가 아닌 추정이에요. 보증금·권리금·관리비는 빠져 있어요.</WarnLine>
      {saved && <div className="fl-actions" role="status">후보에 저장했어요.
        <TextButton onClick={() => go("/spaces")}>다른 자리 보기</TextButton>
        <TextButton onClick={() => go(calculable ? "/premium" : "/budget")}>이 자리 비용 검토</TextButton>
      </div>}
      {!calculable && <div className="fl-actions"><TextButton onClick={() => go("/budget")}>현장 금액으로 예산 점검</TextButton></div>}
      <h2 className="fl-h2">이 건물의 층</h2>
      <div className="fl-stack-row">
        <FloorStack big item={item} siblings={spaces.status === "ready" ? spaces.data.items : []} />
        <div>
          <StackLegend />
          <TextButton onClick={() => setViewer(true)}>거리뷰 · 층별 보기</TextButton>
        </div>
      </div>
      <h2 className="fl-h2">이 자리와 업종</h2>
      <ul className="fl-facts">
        {fit && fit.top.length > 0
          ? <li>같은 조건의 자리에서 영업 중: {fit.top.slice(0, 3).map((t) => `${t.industry} ${Math.round(t.share * 100)}%`).join(" · ")} <span className="fl-muted">(표본 {fit.n.toLocaleString("ko-KR")}곳 · 관측이에요)</span></li>
          : <li>이 자리의 영업 업종 관측 자료가 없어요.</li>}
        {work && (canRank
          ? <li>{rec.status === "loading" ? "추천 순위를 보는 중…" : rec.status === "error" ? "이 자리 근처에는 추천 모델 자료가 없어요."
              : recRank >= 0 ? `${eun(work.label)} 이 자리 추천 ${recRank + 1}위예요.` : `${eun(work.label)} 이 자리 추천 3위 밖이에요.`}</li>
          : <li>{eun(work.label)} 추천 모델이 다루지 않는 업종이라 자리 추천 순위가 없어요.</li>)}
      </ul>
      <Details summary="근거 더 보기">
        <ul className="fl-facts">
          {item.unit?.purps && <li>건축물대장 용도: {item.unit.purps}</li>}
          <li>{item.certainty === "confirmed" ? "이 층이 비었다는 것이 대장·상가정보로 확인됐어요." : "층을 모르는 점포가 다른 층이면 비어 있는 자리예요(추정)."}</li>
          {item.unit && item.unit.bldgs_on_pnu > 1 && <li>한 지번에 건물이 {item.unit.bldgs_on_pnu}동이라 어느 동인지는 몰라요.</li>}
          {fit?.note && <li>{fit.note.replace(/\*\*/g, "")}</li>}
          {spaces.status === "ready" && spaces.data.rentNote && <li>{spaces.data.rentNote}</li>}
        </ul>
      </Details>
      <p className="fl-source">위치 {item.lat.toFixed(5)}, {item.lng.toFixed(5)} · <a href={kakaoMapUrl({ lat: item.lat, lng: item.lng }, item.name)} target="_blank" rel="noopener noreferrer">카카오맵</a></p>
      {!token && <p className="fl-foot">♡ 를 누르면 로그인 뒤 후보로 모아 둘 수 있어요.</p>}
      <Sheet open={viewer} onClose={() => setViewer(false)} title={`${item.name} · 거리뷰와 층`}>
        <Suspense fallback={<SkeletonRows n={3} />}>
          {viewer && <BuildingViewer b={{
            name: item.name, capacity: item.unit?.com_floors.length ?? 1, active: item.unit?.occ_floors.length ?? 0,
            floors: item.unit?.bld_floors, statusColor: "#E03E36", statusLabel: "빈 층 있음", center: { lat: item.lat, lng: item.lng },
            comFloors: item.unit?.com_floors, occFloors: item.unit?.occ_floors, unknownN: item.unit?.unknown_n,
          }} />}
        </Suspense>
      </Sheet>
    </FlowScreen>
  );
}

/* ── 저장 상태를 읽는 훅 — FlowApp 이 들고 있다 ─────────────────────────── */

function useFlowSaved() {
  const flow = useFlow();
  const saved = useSaved();
  return { ...flow, ...saved };
}

/** 소셜 로그인으로 페이지를 떠났다 돌아왔을 때 — R4 의 저장을 이어서 한다 */
function useResumeSave(item: SpaceItem | null, run: () => void) {
  useResume("save-space", !!item, run);
}
