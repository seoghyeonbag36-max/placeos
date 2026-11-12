import NearbyCompetition from "@/components/NearbyCompetition";
import InteriorPlanner from "@/components/InteriorPlanner";
import { useReportCapture } from "@/lib/ppppReportContext";
import { useEffect, useMemo, useRef, useState } from "react";
import type { BuildingSelection, ProgramHandoff } from "@/lib/workspaceState";
import DistrictPicker, { CaveatNote } from "@/components/DistrictPicker";
import AreaBepPlanner from "@/components/AreaBepPlanner";
import TransitAccessPanel from "@/components/TransitAccessPanel";
import PostingRiskCheck from "@/components/PostingRiskCheck";
import MenuPlanner from "@/components/MenuPlanner";
import PostingDecideExtras from "@/components/PostingDecideExtras";
import {
  BASIS_LABEL, TIER_UNAVAILABLE_LABEL, tierAvailable, getPlatformProfile, getPostings, getBuildingTwin, listDistricts, recommendIndustry, simulateRevenue,
} from "@/lib/api";
import type {
  DistrictSummary, IndustryRec, Posting, SavedResult, SimulateResult, TierScenario,
} from "@/lib/api";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { mapLabelHTML, shortManwon } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import SavedResults, { SaveResultButton } from "@/components/SavedResults";
import Verdict, { type Ground } from "@/components/Verdict";
import { IndustryDetailSelect, IndustryOperatingFields, IndustryEconomicsResult, IndustryCompetitionPanel } from "@/components/IndustryDetailFields";
import { useFitMap, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import "./PostingConsole.css";
import ConsolePages from "@/components/ConsolePages";
import MapSlot from "@/components/MapSlot";
import { useMapLayout } from "@/components/mapLayoutContext";

/**
 * Posting 콘솔 — "이 자리에 들어가면 얼마가 남나"에 답하는 화면.
 *
 * 백엔드 `POST /ai/simulate-revenue`(services/posting)는 2026-07-18 부터 있었지만
 * **이걸 부르는 화면이 없었다** — `simulateRevenue()` 는 api.ts 에 정의만 되어 있고
 * 호출부가 0건이었다. ProgramStudio 가 `/marketing/generate` 에 표면을 준 것과 같은
 * 자리다(2026-08-29).
 *
 * 이 화면이 여는 것 둘:
 *   ① **권리금(prem) 입력 계약** — 공개 통계가 없고 임대인·기존 임차인과의 협상값이라
 *      그 자리에 들어갈 기업만 안다. 입력란이 없어 지금까지 늘 `absent`(0 전제)로만
 *      계산돼 왔다. 계약은 입력란이 있어야 성립한다.
 *   ② **외부 AI 창업 코파일럿 어댑터** — `POSTING_COPILOT_URL` 이 채워지면 같은 화면이
 *      코파일럿 결과를 그린다. `source`/`source_note` 가 어느 쪽이 돌았는지 밝힌다.
 *
 * 화면 원칙:
 *   · 비용 기준(`basis`)과 입력 출처(`inputs_source`)를 결과 옆에 같이 싣는다 —
 *     실측 임대료와 시드 프록시가 같은 숫자처럼 보이면 안 된다.
 *   · `viable === false` 는 "모른다"가 아니라 "회수가 안 된다"다. 셋 다 안 되면
 *     `unviable_note` 를 그대로 보여주고 추천을 만들지 않는다.
 */

const DEFAULT_DISTRICT = "garosugil";

const TIER_LABEL: Record<string, { name: string; sub: string }> = {
  premium: { name: "고급화", sub: "객단가 높이고 회전 낮게" },
  value: { name: "가성비", sub: "객단가 낮추고 회전 높게" },
  factory: { name: "기능중심", sub: "면적·인력 최소로" },
};

const won = (v: number) => `${Math.round(v).toLocaleString()}만원`;
/** 입력칸 문자열 → 0 이상 숫자. 비었거나 숫자가 아니면 undefined */
const numOrUndef = (v: string): number | undefined => {
  if (v.trim() === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
};
/** 권리금·전략·업종을 바꾼 뒤 이 시간만큼 입력이 멈추면 다시 계산한다(2026-11-07 「계산 결과가 바로 나오게」). */
const AUTO_RUN_MS = 600;
/** 2026-11-07 에 빠진 탭(「검증 리포트」 · 「계산 결과」). 그 탭을 연 채 저장된 초안은 입력 탭으로 연다. */
// 「program」은 2026-11-10 「비용 비교 및 결정」 안으로 합쳐 없어진 쪽이다
const RETIRED_PAGES = new Set(["report", "result", "program"]);

interface PostingConsoleProps {
  onReportChange?: (handoff: ProgramHandoff | undefined) => void;
  guided?: boolean;
  drafts?: Map<string, PostingDraft>;
  draftKey?: string;
  selection?: BuildingSelection & { requestId: number };
  /** 네 트랙이 공유하는 상권(App). 주면 제어 모드 — 상권을 바꾸면 `onDistrictChange` 로 올린다.
   *  안 주면 종전대로 화면이 스스로 상권을 든다(단독 렌더·테스트). */
  districtId?: string;
  onDistrictChange?: (id: string) => void;
  /** Posting → Program 인계(화면설계서 2판). 주면 결과 아래 「이 자리로 검증 program 만들기 →」가 뜬다. */
  onMakeProgram?: (handoff: ProgramHandoff) => void;
  /** 「내 사업」 업종의 입력어(화면설계서 3판). 업종칸의 기본값이다 — 상권·자리를 바꾸면 빈칸이 아니라 이 값으로 돌아간다. */
  defaultIndustry?: string;
  defaultDetailKey?: string;
  /** Platform 업종 바꾸기 표 「이 업종으로 입점 계산 →」. 있으면 `defaultIndustry` 보다 앞선다. */
  industryRequest?: { input: string; requestId: number };
}
interface Calculation {
  result: SimulateResult;
  input: { district_id: string; unit_id: string; industry_type?: string; strategy?: string; prem?: number;
    industry_detail_key?: string; operating_inputs?: Record<string, number>; area_py_override?: number;
    /** 계약 월세(만원) · 인테리어 · 설비 견적(만원) — 2026-11-12 입력 계약 */
    rent_override?: number; fitout_override?: number };
}

/** 계정·작업공간 수명을 넘기지 않는 입력 초안. 출처와 서버 계산 결과를 그대로 보관한다. */
export interface PostingDraft {
  unitId: string;
  industry: string;
  detailKey: string;
  operating: Record<string, string>;
  prem: string;
  /** 인테리어 · 설비 견적 · 계약 월세 · 보증금(만원 문자열 · 2026-11-12). 옛 초안에는 없다 */
  fitout?: string; contractRent?: string; deposit?: string;
  strategy: string;
  calculation: Calculation | null;
  previous: Calculation | null;
  page: string;
}

export default function PostingConsole({ selection, districtId, onDistrictChange, onMakeProgram, onReportChange, defaultIndustry, defaultDetailKey, industryRequest, guided, drafts }: PostingConsoleProps = {}) {
  const draftKey = `${districtId ?? DEFAULT_DISTRICT}|${selection ? `${selection.districtId}:${selection.buildingId}:${selection.unitId ?? ""}:${selection.requestId}` : "direct"}|${industryRequest?.requestId ?? 0}|${defaultIndustry ?? ""}|${defaultDetailKey ?? ""}`;
  return <PostingSession key={draftKey} guided={guided} drafts={drafts} draftKey={draftKey}
    selection={selection} districtId={districtId} onDistrictChange={onDistrictChange} onMakeProgram={onMakeProgram} onReportChange={onReportChange}
    defaultIndustry={defaultIndustry} defaultDetailKey={defaultDetailKey} industryRequest={industryRequest} />;
}

function PostingSession({ selection, districtId: sharedDistrict, onDistrictChange, onMakeProgram, onReportChange, defaultIndustry, defaultDetailKey, industryRequest, guided = false, drafts, draftKey = "direct" }: PostingConsoleProps) {
  const [draft] = useState(() => drafts?.get(draftKey));
  // 첫 화면은 「시뮬레이션 결과」(2026-11-10 사용자 요청 — 오른쪽 칸 순서: 시뮬레이션 결과 → 상권 맞춤 인테리어 → 주변 업종 지도 →
  // 찾아오는 길 → 위험 확인 → 메뉴 설정 → 비용 비교 및 결정(그 안에 이 자리로 검증 program 만들기)). 11-09 에는 인테리어가 첫 화면이었다.
  // 자리 · 비용 입력은 늘 그려 둔다(keepMounted) — 지도 탐색에서는 왼쪽 칸에 서 있어 어느 쪽을 보면서도 자리를 바꿀 수 있다
  const [page, setPage] = useState(() => (draft?.page && !RETIRED_PAGES.has(draft.page) ? draft.page : "input"));
  const layout = useMapLayout();
  const restored = useRef(!!draft?.calculation);
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const [ownDistrict, setOwnDistrict] = useState(selection?.districtId ?? sharedDistrict ?? DEFAULT_DISTRICT);
  const controlled = sharedDistrict !== undefined && onDistrictChange !== undefined;
  const districtId = controlled ? sharedDistrict : ownDistrict;
  const setDistrictId = (id: string) => (controlled ? onDistrictChange(id) : setOwnDistrict(id));
  const [units, setUnits] = useState<Posting[]>([]);
  // 자리 목록이 **도착한** 상권. 0곳과 불러오는 중을 가르는 데 쓴다(화면설계서 2판 상태표) —
  // 종전에는 0곳인 상권에서 결론이 영원히 "불러오는 중이다"로 남았다.
  const [unitsFor, setUnitsFor] = useState<string | null>(null);
  const [unitId, setUnitId] = useState<string>(draft?.unitId ?? "");
  // 업종칸의 기본값(화면설계서 3판 Posting 구성요소 2) — Platform 인계 업종 → 「내 사업」 입력어 → 빈칸.
  const baseIndustry = industryRequest?.input ?? defaultIndustry ?? "";
  const baseSource = industryRequest ? "Platform 에서 고른 업종으로 채웠습니다" : defaultIndustry ? "내 사업 기준으로 채웠습니다" : "";
  const [industry, setIndustry] = useState(draft?.industry ?? baseIndustry);
  const [detailKey, setDetailKey] = useState(draft?.detailKey ?? (industryRequest ? "" : defaultDetailKey ?? ""));
  const [operating, setOperating] = useState<Record<string, string>>(draft?.operating ?? {});
  const [prem, setPrem] = useState(draft?.prem ?? "");
  // 받은 견적 · 계약 월세 · 보증금(2026-11-12 사용자 요청 — 회수기간 · 임대차법 판정을 실제 값으로)
  const [fitout, setFitout] = useState(draft?.fitout ?? "");
  const [contractRent, setContractRent] = useState(draft?.contractRent ?? "");
  const [deposit, setDeposit] = useState(draft?.deposit ?? "");
  // 상권 분기 개업률 · 폐업률(서울시 상권분석) — 「위험 확인」을 열 때만 받는다
  const [turnover, setTurnover] = useState<{ districtId: string; open: number | null; close: number | null } | null>(null);
  const [strategy, setStrategy] = useState(draft?.strategy ?? "");
  const [recs, setRecs] = useState<IndustryRec[] | null>(null);

  const [calculation, setCalculation] = useState<Calculation | null>(draft?.calculation ?? null);
  const [previous, setPrevious] = useState<Calculation | null>(draft?.previous ?? null);
  const lastCalculation = useRef<Calculation | null>(draft?.calculation ?? null);
  const requestSerial = useRef(0);
  const programRequest = useRef(0);
  useEffect(() => () => { programRequest.current += 1; }, [districtId, unitId]);
  const [handoffNote, setHandoffNote] = useState("");
  // 저장한 결과 목록을 다시 받게 하는 신호(「결과 저장」 성공 때 올린다)
  const [savedTick, setSavedTick] = useState(0);
  const result = calculation?.result ?? null;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    drafts?.set(draftKey, { unitId, industry, detailKey, operating, prem, fitout, contractRent, deposit, strategy, calculation, previous, page });
  }, [drafts, draftKey, unitId, industry, detailKey, operating, prem, fitout, contractRent, deposit, strategy, calculation, previous, page]);

  const unit = useMemo(() => units.find((u) => u.id === unitId), [units, unitId]);
  const resolved = calculation?.result.resolved_inputs;
  const effectiveUnit = unit && resolved
    ? { ...unit, area: resolved.area_py, rent: resolved.rent_manwon,
      inputs_source: calculation.result.inputs_source ?? unit.inputs_source } : unit;
  const [inventoryScope, setInventoryScope] = useState({ districtId, selection });
  if (inventoryScope.districtId !== districtId || inventoryScope.selection !== selection) {
    setInventoryScope({ districtId, selection });
    setUnits([]); setUnitsFor(null); setUnitId(""); setRecs(null); setErr(null);
    setOperating({}); setCalculation(null); setPrevious(null); setBusy(false);
  }
  const [recommendedUnit, setRecommendedUnit] = useState(unit);
  if (recommendedUnit !== unit) {
    setRecommendedUnit(unit);
    setRecs(null);
  }

  // 화면 머리(결론 1줄 + 근거 3줄). 계산 결과가 바뀔 때만 다시 짠다.
  const head = useMemo(() => postingHeadline({
    districtName: districts.find((d) => d.id === districtId)?.name ?? districtId,
    unit, unitCount: units.length, unitsLoaded: unitsFor === districtId, result, premInput: prem,
  }), [districts, districtId, unit, units.length, unitsFor, result, prem]);

  useEffect(() => {
    let live = true;
    listDistricts()
      .then((all) => {
        if (!live) return;
        setDistricts(all);
        // 지금 상권이 목록에 없으면 첫 거점으로 떨어진다. 제어 모드면 공유 상권을 기준으로 본다.
        if (!selection && all.length && !all.some((d) => d.id === districtId)) setDistrictId(all[0].id);
      })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
    // 목록은 마운트(또는 인계 선택이 바뀔 때) 한 번만 부른다 — 상권 전환마다 다시 부르지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  useEffect(() => () => { requestSerial.current += 1; }, []);

  // 「위험 확인」을 연 상권의 분기 개업률 · 폐업률(서울시 상권분석 · Platform 과 같은 응답) — 다른 쪽을 볼 때는 부르지 않는다
  useEffect(() => {
    if (!guided || page !== "risk" || turnover?.districtId === districtId) return;
    let live = true;
    getPlatformProfile(districtId)
      .then((p) => { if (live) setTurnover({ districtId, open: p.identity?.demand?.open_rate ?? null, close: p.identity?.demand?.close_rate ?? null }); })
      .catch(() => { if (live) setTurnover({ districtId, open: null, close: null }); });
    return () => { live = false; };
  }, [guided, page, districtId, turnover?.districtId]);

  // 입력을 바꾸면 잠시 뒤 스스로 다시 계산한다 — 결과는 입력 바로 아래에 있다(2026-11-07).
  // 타이머는 최신 run 을 ref 로 부른다(닫힌 state 를 읽지 않게). 버튼으로 계산하거나 자리·상권을 바꾸면 대기 중인 자동 계산은 걷는다.
  // 업종 세부 운영 조건(detailKey)은 여러 칸을 다 채워야 계산되므로 자동 계산하지 않고 버튼으로 계산한다.
  const autoTimer = useRef<number | undefined>(undefined);
  const runRef = useRef<(opts?: { quiet?: boolean }) => Promise<void>>(async () => {});
  useEffect(() => { runRef.current = run; });
  useEffect(() => () => window.clearTimeout(autoTimer.current), []);
  function cancelAutoRun() {
    window.clearTimeout(autoTimer.current);
    autoTimer.current = undefined;
  }
  function scheduleRun() {
    cancelAutoRun();
    autoTimer.current = window.setTimeout(() => { autoTimer.current = undefined; void runRef.current({ quiet: true }); }, AUTO_RUN_MS);
  }

  function clearCalculation() {
    cancelAutoRun();
    requestSerial.current += 1;
    setCalculation(null); setPrevious(null); setBusy(false);
    lastCalculation.current = null;
  }

  function chooseDistrict(id: string) {
    clearCalculation(); setUnits([]); setUnitId(""); setRecs(null); setHandoffNote("");
    setIndustry(baseIndustry); setPrem(""); setFitout(""); setContractRent(""); setDeposit(""); setStrategy(""); setDistrictId(id);
    setOperating({}); setDetailKey(industryRequest ? "" : defaultDetailKey ?? "");
  }

  function chooseUnit(id: string) {
    clearCalculation(); setRecs(null); setErr(null);
    setIndustry(baseIndustry); setPrem(""); setFitout(""); setContractRent(""); setDeposit(""); setStrategy(""); setUnitId(id);
    setOperating({}); setDetailKey(industryRequest ? "" : defaultDetailKey ?? "");
    setHandoffNote("");
  }

  // 자리 목록 — 실측 공실 인벤토리(services/vacant_inventory)에서 온다
  useEffect(() => {
    let live = true;
    lastCalculation.current = draft?.calculation ?? null; requestSerial.current += 1;
    getPostings(districtId)
      .then(async (p) => {
        if (selection?.unitId && districtId === selection.districtId) {
          const twin = await getBuildingTwin(selection.buildingId, districtId);
          if (!live) return;
          const floor = twin?.floors.find((f) => f.unit_id === selection.unitId);
          if (floor && floor.area_m2 != null && floor.area_m2 > 0 && floor.rent_est_manwon != null) {
            const selectedFloor: Posting = {
              id: selection.unitId, n: `${selection.buildingName} ${floor.label}`, grp: "층 매물",
              lat: twin!.lat, lng: twin!.lng, area: Math.round(floor.area_m2 / 3.305785 * 10) / 10, rent: floor.rent_est_manwon,
              prem: 0, floor: floor.label, was: "", foot: "", scenarios: {},
              inputs_source: { area: floor.area_source ?? "대장 층별개요", rent: "rone", prem: "absent", foot: "none" },
            };
            p = [selectedFloor, ...p.filter((u) => u.id !== selectedFloor.id)];
          }
        }
        if (!live) return;
        setUnits(p);
        setUnitsFor(districtId);
        if (selection && districtId === selection.districtId) {
          // build_vacant_units.py의 id=f"vu-{p.get('id')}" 계약을 응답 목록에서 검증한다.
          // 이름·좌표로 추측하거나 층 표본을 ROI 유닛으로 바꾸지 않는다.
          const match = p.find((u) => u.id === (selection.unitId ?? `vu-${selection.buildingId}`));
          const restoredUnit = draft && p.find((u) => u.id === draft.unitId);
          setUnitId(restoredUnit?.id ?? match?.id ?? "");
          setHandoffNote(match ? `${selection.buildingName}의 입점 계산 유닛을 확인했습니다.`
            : `${selection.buildingName}과 일치하는 입점 계산 유닛이 없습니다. 계산할 자리를 직접 선택해 주세요.`);
        } else setUnitId(draft && p.some((u) => u.id === draft.unitId) ? draft.unitId : p[0]?.id ?? "");
        if (draft && !p.some((u) => u.id === draft.unitId)) {
          restored.current = false;
          lastCalculation.current = null;
          setCalculation(null); setPrevious(null); setPage("input");
        }
      })
      .catch((e) => { if (live) setErr(String(e)); });
    return () => { live = false; };
  }, [districtId, selection, draft]);

  // 자리를 고르면 그 좌표로 GNN 업종 추천을 물어 온다 — 업종 입력의 출발점이다.
  // (Platform 이 자리마다 답하는 것과 같은 질의다. 여기서는 그 답을 비용 계산에 넘긴다.)
  useEffect(() => {
    if (!unit) return;
    let live = true;
    recommendIndustry({ district_id: districtId, lat: unit.lat, lon: unit.lng })
      .then((r) => { if (live && r.model !== "gnn-stub") setRecs(r.recommendations); })
      .catch(() => { if (live) setRecs(null); });   // 404 = 400m 안에 노드 없음
    return () => { live = false; };
  }, [unit, districtId]);

  // 자리가 정해지면 우선 **입력 없이** 한 번 돌려 빈 화면을 만들지 않는다.
  // 이때 prem 은 보내지 않으므로 결과가 `absent`(0 전제)로 온다 — 그 사실은 화면이 밝힌다.
  useEffect(() => {
    if (!unitId || unitsFor !== districtId) return;
    if (restored.current) { restored.current = false; return; }
    run({ quiet: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitId, unitsFor]);

  async function run(opts: { quiet?: boolean } = {}) {
    if (!unit || !unitId) return;
    cancelAutoRun();
    const serial = ++requestSerial.current;
    setBusy(true);
    if (!opts.quiet) setErr(null);
    try {
      const parsed = prem.trim() === "" ? undefined : Math.max(0, Number(prem));
      const input: Calculation["input"] = {
        district_id: districtId,
        unit_id: unitId,
        industry_type: industry.trim() || undefined,
        strategy: strategy || undefined,
        prem: Number.isFinite(parsed as number) ? (parsed as number) : undefined,
      };
      const quote = numOrUndef(fitout), rentIn = numOrUndef(contractRent);
      if (quote !== undefined) input.fitout_override = Math.round(quote);
      if (rentIn !== undefined && rentIn > 0) input.rent_override = rentIn;
      if (detailKey) {
        input.industry_detail_key = detailKey;
        input.operating_inputs = Object.fromEntries(Object.entries(operating).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, Number(v)]));
        if (Object.values(input.operating_inputs).some((v) => !Number.isFinite(v))) throw new Error("운영 조건에 유효한 숫자를 입력해 주세요.");
        input.prem = undefined; input.strategy = undefined; input.fitout_override = undefined; input.rent_override = undefined;
      }
      const r = await simulateRevenue(input);
      if (serial !== requestSerial.current) return;
      // 서버가 유닛을 찾지 못하면 첫 유닛으로 폴백할 수 있어 응답도 대조한다.
      if (r.district_id !== input.district_id || r.unit_id !== input.unit_id) throw new Error("선택한 자리와 계산 응답이 일치하지 않습니다.");
      const before = lastCalculation.current;
      const sameScope = before && before.input.district_id === input.district_id && before.input.unit_id === input.unit_id
        && !detailKey && before.input.industry_type === input.industry_type && before.input.strategy === input.strategy
        && before.input.prem !== input.prem && before.result.source === r.source && before.result.inputs_quarter === r.inputs_quarter
        && before.input.fitout_override === input.fitout_override && before.input.rent_override === input.rent_override
        && Object.entries(r.scenarios).every(([key, tier]) => before.result.scenarios[key]?.basis === tier.basis);
      setPrevious(sameScope ? before : null);
      const next = { result: r, input };
      lastCalculation.current = next;
      setCalculation(next);
      // 결과는 입력 화면 바로 아래에 그린다 — 다른 탭으로 옮기지 않는다(2026-11-07).
    } catch (e) {
      if (serial !== requestSerial.current) return;
      setErr(String(e));
      setCalculation(null); setPrevious(null); lastCalculation.current = null;
    } finally {
      if (serial === requestSerial.current) setBusy(false);
    }
  }

  // ── 지도 (2026-09-13 「네 트랙 모두 지도 전체화면」) ─────────────────────────
  // 계산할 수 있는 자리를 지도에 **월임대료 칩**으로 건다. 드롭다운 한 줄로만 보이던 자리가
  // "어디에 있고 얼마인지"로 먼저 읽힌다. 칩을 누르면 드롭다운에서 고른 것과 똑같이 동작한다.
  // 금액은 목록의 `unit.rent`(R-ONE × 면적 × 층 계수) 그대로다 — 지도에서 따로 계산하지 않는다.
  const markers = useMemo<MapMarkerItem[]>(() => page === "nearby" ? [] : units.map((u) => ({
    id: u.id, lat: u.lat, lng: u.lng, zIndex: u.id === unitId ? 200 : 70,
    html: mapLabelHTML({
      text: `월 ${shortManwon(u.rent)}`, sub: `${u.area}평`,
      color: colors.track.posting.base, active: u.id === unitId,
    }),
  })), [units, unitId, page]);
  useMapMarkers(markers, chooseUnit);
  const hubCenter = districts.find((d) => d.id === districtId)?.center;
  useFitMap(page === "nearby" ? null : districtId, units, hubCenter ? { lat: hubCenter[0], lng: hubCenter[1] } : null);

  // Posting → Program 인계 값. 업종은 **계산에 쓴 업종**을 먼저, 없으면 자리의 직전 업종.
  // 전략명은 계산했고 회수되는 전략이 있을 때만 — 없는 추천을 지어내지 않는다.
  async function makeProgram() {
    if (!unit || !onMakeProgram || busy || changedInput) return;
    const request = ++programRequest.current;
    const used = calculation?.input.unit_id === unit.id ? calculation : null;
    const entries = used ? Object.entries(used.result.scenarios) : [];
    // 자료 부족 전략(실측 재료 없음 · 2026-10-28 (b))은 숫자가 없어 후보가 아니다
    const viable = entries.flatMap(([k, t]) => (tierAvailable(t) && t.viable ? [[k, t] as const] : []));
    const best = viable.find(([, t]) => t.recommended)
      ?? [...viable].sort((a, b) => a[1].roi_months - b[1].roi_months)[0];
    const buildingId = selection?.districtId === districtId && (unit.id === selection.unitId || unit.id === `vu-${selection.buildingId}`)
      ? selection.buildingId : unit.id.startsWith("vu-") ? unit.id.slice(3) : null;
    let address: string | null = null;
    if (buildingId) {
      setHandoffNote("선택 건물의 주소를 확인하는 중입니다…");
      try { address = (await getBuildingTwin(buildingId, districtId))?.road_addr ?? null; }
      catch { /* 주소를 확인하지 못하면 직접 입력으로 남긴다. */ }
    }
    if (request !== programRequest.current) return;
    onMakeProgram({
      buildingId: buildingId ?? undefined,
      districtId, districtName: districts.find((d) => d.id === districtId)?.name,
      address, inputsSource: effectiveUnit!.inputs_source,
      unitId: unit.id, unitName: unit.n, lat: unit.lat, lng: unit.lng,
      area: effectiveUnit!.area, floor: unit.floor, rent: effectiveUnit!.rent,
      industry: used?.result.industry_type || used?.input.industry_type || unit.was?.trim() || null,
      strategy: best ? (TIER_LABEL[best[0]]?.name ?? best[1].name) : null,
      calculation: used ? { input: used.input, result: used.result } : undefined,
    });
  }

  const changedInput = calculation && (calculation.input.industry_type !== (industry.trim() || undefined)
    || calculation.input.strategy !== (strategy || undefined)
    || calculation.input.prem !== (prem.trim() === "" ? undefined : Number(prem))
    || (!detailKey && calculation.input.fitout_override !== (numOrUndef(fitout) === undefined ? undefined : Math.round(numOrUndef(fitout)!)))
    || (!detailKey && calculation.input.rent_override !== ((numOrUndef(contractRent) ?? 0) > 0 ? numOrUndef(contractRent) : undefined))
    || calculation.input.area_py_override !== undefined);
  const reportHandoff: ProgramHandoff | undefined = effectiveUnit ? {
    buildingId: selection && (effectiveUnit.id === selection.unitId || effectiveUnit.id === `vu-${selection.buildingId}`)
      ? selection.buildingId : effectiveUnit.id.startsWith("vu-") ? effectiveUnit.id.slice(3) : undefined,
    districtId, districtName: districts.find(d => d.id === districtId)?.name,
    unitId: effectiveUnit.id, unitName: effectiveUnit.n, lat: effectiveUnit.lat, lng: effectiveUnit.lng,
    area: effectiveUnit.area, floor: effectiveUnit.floor, rent: effectiveUnit.rent,
    industry: industry.trim() || null, strategy: strategy || null, inputsSource: effectiveUnit.inputs_source,
    calculation: calculation && !changedInput ? { input: calculation.input, result: calculation.result } : undefined,
  } : undefined;
  const reportSnapshot = JSON.stringify(reportHandoff);
  useReportCapture("posting", reportHandoff ?? null);
  useEffect(() => {
    onReportChange?.(reportSnapshot ? JSON.parse(reportSnapshot) as ProgramHandoff : undefined);
  }, [onReportChange, reportSnapshot]);
  const tiers = result ? Object.entries(result.scenarios) : [];


  // 지도 탐색의 칸 배치 안인가(MapHost) — 입력이 왼쪽 칸으로 가면 안내 문구도 그 자리를 가리킨다
  const inSlots = layout !== null;

  return (
    <div className="postconsole"><div className="wrap">
      {err && (
        <div className="err">
          <strong>계산에 실패했습니다.</strong>
          <div className="errdetail">{err.includes("선택한 자리와 계산 응답이 일치하지 않습니다.")
            ? "선택한 자리와 계산 응답이 일치하지 않습니다. 자리를 다시 선택해 주세요."
            : "입력 조건을 확인하고 잠시 후 다시 시도해 주세요."}</div>
        </div>
      )}

      <ConsolePages enabled={guided} label="비용 검토" activeId={page} onChange={setPage} keepMounted={["input"]} pages={[
        { id: "input", label: "시뮬레이션 결과", description: inSlots
          ? "왼쪽에서 자리와 비용 조건을 고르고 「시뮬레이션」을 누르면 세 가격대(고급화 · 가성비 · 기능중심)의 비용과 회수기간이 여기에 나옵니다."
          : "조건을 입력하면 바로 아래에 세 가격대(고급화 · 가성비 · 기능중심)의 비용과 회수기간이 나옵니다.", content: <>
        {/* ── 입력 ── 2026-11-08 칸 배치: 지도 탐색에서는 **왼쪽 칸**에 선다(결과는 오른쪽 칸 · 지도는 가운데).
            다른 탭(주변 업종 · 인테리어 · 찾아오는 길)을 봐도 입력은 왼쪽에 그대로 남는다. 단독 렌더는 예전 자리(MapSlot). */}
        <MapSlot name="left" className="postconsole posting-side" track="posting">
        {/* 「시뮬레이션」을 누르면 결과가 나오는 오른쪽 「시뮬레이션 결과」를 연다(자동 재계산은 쪽을 옮기지 않는다) */}
        <form className="panel" onSubmit={(e) => { e.preventDefault(); setPage("input"); run(); }}>
          <div className="ptitle">1. 자리와 업종 선택</div>
          {handoffNote && <div className="posting-handoff" role="status">{handoffNote}</div>}

          <label className="field">
            <span className="flabel">상권</span>
            <DistrictPicker districts={districts} value={districtId}
              onChange={chooseDistrict} suffix={(d) => d.gu} />
            <CaveatNote district={districts.find((d) => d.id === districtId)} />
          </label>

          <label className="field">
            <span className="flabel">
              자리 <em>실측 {units.length}곳</em>
            </span>
            <select value={unitId} onChange={(e) => chooseUnit(e.target.value)} disabled={!units.length}>
              {!unitId && <option value="">계산할 자리를 선택하세요</option>}
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.n} · {u.area}평 · {u.floor}
                </option>
              ))}
            </select>
            {unit && (
              <span className="fhint">
                임대료 {won(unit.rent)}/월 · 직전 업종 {unit.was || "미상"}
                {unit.foot ? ` · 유동 ${unit.foot}` : ""}
              </span>
            )}
          </label>

          <label className="field">
            <span className="flabel">업종</span>
            <input value={industry} onChange={(e) => { setIndustry(e.target.value); setDetailKey(""); setOperating({}); clearCalculation(); scheduleRun(); }}
              placeholder="예: 카페 (비우면 자리 기본값)" />
            {recs && recs.length > 0 && (
              <span className="chips">
                {recs.map((r) => (
                  <button type="button" key={r.industry}
                    className={"chip" + (industry === r.industry ? " on" : "")}
                    onClick={() => { setIndustry(r.industry); setDetailKey(""); setOperating({}); clearCalculation(); scheduleRun(); }}>
                    {r.industry} {Math.round(r.score * 100)}%
                  </button>
                ))}
                <i className="chipnote">이 자리의 추천 점수 · 성공 확률 아님</i>
              </span>
            )}
            {baseIndustry && industry === baseIndustry && (
              <span className="fhint">{baseSource} — 바꿀 수 있습니다</span>
            )}
          </label>

          {effectiveUnit && <AreaBepPlanner key={`${districtId}:${unit!.id}`} unit={effectiveUnit} operating={operating} industry={industry} />}
          <IndustryDetailSelect value={detailKey} onChange={(key, option) => {
            setDetailKey(key); setOperating({}); clearCalculation();
            if (option) setIndustry(option.label);
          }} />
          {detailKey && <IndustryOperatingFields detailKey={detailKey} values={operating}
            onChange={(key, value) => { setOperating((v) => ({ ...v, [key]: value })); clearCalculation(); }} />}
          {!detailKey && <>
          <div className="ptitle posting-input-step">2. 비용 조건 입력</div>
          <label className="field">
            <span className="flabel">권리금 <em>직접 입력</em></span>
            <input value={prem} inputMode="numeric"
              onChange={(e) => { setPrem(e.target.value.replace(/[^\d]/g, "")); scheduleRun(); }}
              placeholder="만원 — 비우면 0 전제" />
            <span className="fhint">
              협의한 금액을 입력하세요. 비워 두면 <b>0원으로 가정</b>해 계산합니다.
            </span>
          </label>
          {/* 2026-11-12 사용자 요청 — 받은 견적 · 계약 금액으로 회수기간과 임대차법 보호 범위를 본다 */}
          <label className="field">
            <span className="flabel">인테리어 · 설비 견적 <em>받은 견적</em></span>
            <input value={fitout} inputMode="numeric" aria-label="인테리어 · 설비 견적(만원)"
              onChange={(e) => { setFitout(e.target.value.replace(/[^\d]/g, "")); scheduleRun(); }}
              placeholder="만원 — 비우면 업종 평균 계수" />
            <span className="fhint">받은 견적을 넣으면 세 가격대 모두 <b>이 금액(+ 권리금)</b>을 투자비로 회수기간을 다시 계산합니다.</span>
          </label>
          <label className="field">
            <span className="flabel">계약 월세 <em>계약서 금액</em></span>
            <input value={contractRent} inputMode="numeric" aria-label="계약 월세(만원)"
              onChange={(e) => { setContractRent(e.target.value.replace(/[^\d]/g, "")); scheduleRun(); }}
              placeholder={unit ? `만원 — 비우면 시세 추정 ${Math.round(unit.rent).toLocaleString("ko-KR")}만원` : "만원 — 비우면 시세 추정"} />
          </label>
          <label className="field">
            <span className="flabel">보증금 <em>계약서 금액</em></span>
            <input value={deposit} inputMode="numeric" aria-label="보증금(만원)"
              onChange={(e) => setDeposit(e.target.value.replace(/[^\d]/g, ""))}
              placeholder="만원 — 임대차법 판정에만 씀" />
            <span className="fhint">보증금은 회수기간에 넣지 않고, 상가임대차법 보호 범위(환산보증금)를 판정하는 데만 씁니다.</span>
          </label>

          <details className="posting-advanced"><summary>세부 조건 · 전략 선택</summary>
          <label className="field">
            <span className="flabel">전략</span>
            <select value={strategy} onChange={(e) => { setStrategy(e.target.value); scheduleRun(); }}>
              <option value="">세 전략 비교</option>
              <option value="premium">고급화</option>
              <option value="value">가성비</option>
              <option value="factory">기능중심</option>
            </select>
          </label>

          </details>
          </>}

          <Button className="run" type="submit" disabled={busy || !unitId}>
            {busy ? "계산 중…" : "시뮬레이션"}
          </Button>
          {!detailKey && <span className="fhint">권리금·전략·업종을 바꾸면 바로 다시 계산합니다.</span>}
        </form>
        </MapSlot>

        {/* ── 결과 — 「시뮬레이션 결과」(2026-11-10 사용자 요청): 세 가격대(고급화 · 가성비 · 기능중심)의 비용과 회수기간만 둔다.
            결론(Verdict) · 결과 저장은 「비용 비교 및 결정」, 검증 program 버튼은 「비용 비교 및 결정」 맨 아래, 세부 업종 경쟁점은 「주변 업종 지도」로 옮겼다.
            세부 업종을 고르면 세 가격대 대신 그 업종 운영 시나리오가 계산 결과다 — 그래서 그것만은 여기에 남는다. ── */}
        <div className="results">
          <div className="posting-result-heading"><h2>{detailKey ? "업종별 운영 시나리오" : "세 가격대의 비용과 회수기간"}</h2><p>처음 필요한 돈 · 매달 나가는 돈 · 투자 회수까지</p></div>
          {result?.unavailable_reason && <p role="status">{result.unavailable_reason}</p>}
          {result?.economics && <IndustryEconomicsResult result={result.economics} />}
          {!result && !busy && <div className="empty">자리를 고르면 계산한다.</div>}
          {result && !result.economics && result.calculation_status !== "unavailable" && (
            <>
              {calculation && <div className="posting-input-summary">
                계산에 사용한 입력: {calculation.input.industry_type || "자리 기본 업종"} · 권리금 {calculation.input.prem === undefined ? "미입력 · 0 전제" : won(calculation.input.prem)}
                {" · "}투자비 {calculation.input.fitout_override === undefined ? "업종 평균 계수" : `견적 ${won(calculation.input.fitout_override)}`}
                {calculation.input.rent_override !== undefined && <> · 계약 월세 {won(calculation.input.rent_override)}</>} · {TIER_LABEL[calculation.input.strategy ?? ""]?.name ?? "세 전략 비교"}
                {changedInput && <strong role="status">입력이 변경되었습니다. 곧 다시 계산합니다.</strong>}
              </div>}
              <div className="rhead">
                <div className="rtitle">
                  {unit?.n ?? result.unit_id}
                  {result.industry_type && <span className="rind">{result.industry_type}</span>}
                </div>
                <div className="rbadges">
                  {/* 코파일럿이 돌았는지 폴백인지 — 안 붙였다와 붙였는데 실패했다를 섞지 않는다 */}
                  <span className={"badge " + (result.source === "copilot" ? "is-copilot" : "is-fallback")}>
                    {result.source === "copilot" ? "AI 분석" : "기본 계산"}
                  </span>
                  {result.inputs_quarter && <span className="badge is-q">{result.inputs_quarter} 기준</span>}
                </div>
              </div>

              {result.source_note && (
                <div className="note is-warn">
                  AI 분석을 완료하지 못해 기본 계산 결과를 표시합니다.
                </div>
              )}

              {result.inputs_source && (
                <div className="inputs">
                  {(["area", "rent", "prem", "foot"] as const).map((k) => (
                    <span key={k} className={"isrc " + srcClass(result.inputs_source![k])}>
                      {{ area: "면적", rent: "임대료", prem: "권리금", foot: "유동" }[k]}
                      <i>{srcLabel(result.inputs_source![k])}</i>
                    </span>
                  ))}
                  <span className={"isrc " + (result.inputs_source.invest === "user_input" ? "is-proxy" : "is-absent")}>
                    투자비<i>{result.inputs_source.invest === "user_input" ? "견적 입력" : "업종 평균 계수"}</i>
                  </span>
                  {result.inputs_source.floor && (
                    <span className={"isrc " + srcClass(result.inputs_source.floor)}>
                      층<i>{result.inputs_source.floor === "flr_ouln" ? "층별개요 실측" : "1층 가정(상한)"}</i>
                    </span>
                  )}
                </div>
              )}

              {result.unviable_note && <div className="note is-bad">{result.unviable_note}</div>}

              <div className="tiers">
                {tiers.map(([key, s]) => (
                  <TierCard key={key} tierKey={key} s={s} before={previous?.result.scenarios[key]} />
                ))}
              </div>
              {previous && calculation && <p className="posting-comparison-note">직전 계산 대비 · 동일 자리·업종·전략·기준분기 · 권리금 {previous.input.prem === undefined ? "미입력(0 전제)" : won(previous.input.prem)} → {calculation.input.prem === undefined ? "미입력(0 전제)" : won(calculation.input.prem)}. 차이는 두 서버 계산 결과를 비교한 값입니다.</p>}

              <div className="rsrc">
                매출·순익·회수기간은 입력 조건에 따른 추정입니다. 실제 계약 금액과 운영 조건에 따라 달라질 수 있습니다.
              </div>
            </>
          )}
        </div>
        </> },
        { id: "interior", label: "상권 맞춤 인테리어", description: "고른 자리의 3D 디지털 트윈에서 키워드로 가구를 놓고, 테이블 · 의자를 골라 직접 배치하세요.", content:
          guided && <InteriorPlanner key={`${districtId}:${unitId}`} handoff={reportHandoff} district={districtId} industry={industry} /> },
        { id: "nearby", label: "주변 업종 지도", description: "업종을 확인하고 「조회」를 누르면 공실 주변 50~100m의 같은 업종과 체인점을 보여 줍니다.", content:
          page === "nearby" && <>
            {detailKey && <IndustryCompetitionPanel districtId={districtId} detailKey={detailKey} />}
            {unit ? <NearbyCompetition key={`${districtId}:${unit.id}`} districtId={districtId} lat={unit.lat} lng={unit.lng} industry={industry} detailKey={detailKey} /> : <p>먼저 자리를 선택하세요.</p>}
          </> },
        // 「검증 리포트」 탭은 Posting 에서 뺐다(2026-11-07 사용자 요청). 종합 리포트는 지도 탐색의 「검증 리포트」(App.tsx)와 Program 에 그대로 있다.
        // 2026-11-10 사용자 요청 — 공실까지 지하철역 · 버스정류장에서 걸어서 몇 분인지(TMAP 보행 경로) 보인다. 쪽을 열면 바로 조회한다.
        // 쪽 나눔이 없는 단독 렌더(guided 아님)는 모든 쪽이 한꺼번에 그려져 「연 것」이 아니다 — 그때는 종전대로 펼칠 때만 조회한다
        { id: "access", label: "찾아오는 길", description: "검토하는 공실까지 지하철역 · 버스정류장에서 걸어서 얼마나 걸리는지와 주변 교통을 확인하세요.", content:
          unit ? <TransitAccessPanel key={`${districtId}:${unit.id}:${unit.lat}:${unit.lng}`}
            destination={{ lat: unit.lat, lng: unit.lng }} destinationName={unit.n} openOnMount={guided} walkSummary /> : <p>자리를 먼저 선택해 주세요.</p> },
        { id: "risk", label: "위험 확인", description: "이 자리를 떨어뜨릴 이유가 있는지, 계약 전에 더 확인할 것은 무엇인지 시뮬레이션 결과와 입력의 출처로 가릅니다.", content:
          <PostingRiskCheck result={result} strategy={calculation?.input.strategy} industry={calculation?.input.industry_type ?? industry}
            busy={busy} stale={!!changedInput} deposit={numOrUndef(deposit) ?? null} rent={effectiveUnit?.rent ?? null}
            openRate={turnover?.districtId === districtId ? turnover.open : null} closeRate={turnover?.districtId === districtId ? turnover.close : null} /> },
        { id: "menu", label: "메뉴 설정", description: "대표 메뉴의 가격 · 원가로 객단가를 잡고, 하루 몇 개를 팔아야 본전인지 계산합니다.", content:
          <MenuPlanner rent={effectiveUnit?.rent ?? null} rentSource={effectiveUnit?.inputs_source?.rent ?? null} scenarios={result?.scenarios ?? null} /> },
        { id: "decide", label: "비용 비교 및 결정", description: "이 자리의 결론을 보고, 계산을 저장해 다른 자리 · 조건과 나란히 비교한 뒤 정하세요. 정했으면 아래에서 이 자리로 검증 program 을 만듭니다.", content: <div className="pstep">
          <Verdict
            eyebrow="PlaceOS · Posting" conversion="PRICE ▶ POSTING"
            question="어떤 비용과 전략으로 입점할까요?"
            verdict={head.verdict} grounds={head.grounds.slice(0, 3).map(({ label, value }) => ({ label, value }))}
          />
          {/* 2026-11-12 사용자 요청 — 매출이 덜 나오거나 월세가 오를 때(민감도) · 계약 전 확인 체크리스트 */}
          <PostingDecideExtras result={result} unitId={unit?.id ?? null} strategy={calculation?.input.strategy ?? null}
            rent={effectiveUnit?.rent ?? null} deposit={numOrUndef(deposit) ?? null}
            inputs={{ prem: numOrUndef(prem), fitout: numOrUndef(fitout), contractRent: numOrUndef(contractRent) }} stale={!!changedInput} />
          {/* 결과 저장(2026-10-06) — 새로고침하면 사라지던 계산을 본인 계정에 남긴다. 고른 것만 남긴다. 2026-11-10 이 쪽으로 옮겼다 */}
          {result && !result.economics && result.calculation_status !== "unavailable" && <SaveResultButton disabled={busy || !calculation} onSaved={() => setSavedTick((n) => n + 1)}
            build={() => calculation && {
              kind: "posting",
              title: `${districts.find((d) => d.id === calculation.input.district_id)?.name ?? calculation.input.district_id}`
                + ` · ${unit?.n ?? calculation.result.unit_id} · ${calculation.result.industry_type || calculation.input.industry_type || "자리 기본 업종"}`,
              districtId: calculation.input.district_id,
              payload: { input: calculation.input, result: calculation.result, unitName: unit?.n ?? null },
            }} />}
          {result?.economics?.status === "calculated" && calculation && <SaveResultButton disabled={busy} onSaved={() => setSavedTick((n) => n + 1)}
            build={() => ({ kind: "posting", title: `${districts.find((d) => d.id === districtId)?.name ?? districtId} · ${result.economics!.label} 운영 시나리오`,
              districtId, payload: { input: calculation.input, result, unitName: unit?.n ?? null } })} />}
          <SavedResults kind="posting" refreshKey={savedTick} render={(it) => <SavedPostingView item={it} />} />
          {inSlots && <p className="pstep-pointer">후보를 3곳까지 담아 계약 조건 · 답사 체크리스트로 비교하려면 화면 오른쪽 위 「입점 준비」를 쓰세요.</p>}
          {/* 정했으면 바로 검증 program 으로 — 2026-11-10 사용자 요청으로 따로 있던 마지막 쪽을 이 쪽 안으로 합쳤다 */}
          <section className="pstep-program" aria-labelledby="posting-program-title">
          <h3 id="posting-program-title">이 자리로 검증 program 만들기</h3>
          <p className="pstep-lede">정한 자리와 계산을 Program 「가설 검증」으로 넘겨, 작게 먼저 확인할 계획을 세웁니다.</p>
          {unit ? <dl>
            <dt>자리</dt><dd>{unit.n} · {effectiveUnit?.area ?? unit.area}평 · {unit.floor}</dd>
            <dt>업종</dt><dd>{calculation?.result.industry_type || calculation?.input.industry_type || unit.was?.trim() || "자리 기본 업종"}</dd>
            <dt>계산</dt><dd>{calculation ? (result?.economics ? `${result.economics.label} 운영 시나리오` : "세 가격대 비용과 회수기간") : "아직 없음 — 「시뮬레이션」을 먼저 하세요"}</dd>
          </dl> : <p className="pstep-empty">왼쪽에서 자리를 먼저 고르세요.</p>}
          <p className="pstep-lede">{result?.economics?.status === "calculated"
            ? "세부 업종 운영 계산의 하루 손익분기 건수가 가설 검증의 목표선이 됩니다."
            : "세부 업종 운영 계산(단가 · 영업일 · 비용)까지 하면 하루 손익분기 건수가 가설 검증의 목표선으로 함께 넘어갑니다."}</p>
          {changedInput && <p className="pstep-note" role="status">입력이 바뀌어 다시 계산하는 중입니다 — 계산이 끝나면 넘길 수 있습니다.</p>}
          {onMakeProgram ? (
            <Button type="button" variant="ghost" className="posting-to-program" disabled={!unit || busy || !!changedInput}
              onClick={makeProgram}>이 자리로 검증 program 만들기 →</Button>
          ) : <p className="pstep-empty">지도 탐색의 Posting 에서 열면 이 자리로 Program 을 바로 만듭니다.</p>}
          </section>
        </div> },
      ]} />
    </div></div>
  );
}

/** 저장한 Posting 결과 — 읽기 전용(components/SavedResults 머리말). 저장 당시의 입력과 세 가격대를 그대로 그린다. */
function SavedPostingView({ item }: { item: SavedResult }) {
  const saved = item.payload as Partial<Calculation> & { unitName?: string | null };
  const r = saved.result;
  if (r?.economics) return <IndustryEconomicsResult result={r.economics} />;
  if (!r?.scenarios) return <p className="saved-note">이 결과는 다시 그릴 수 없는 형식입니다.</p>;
  // 10-28 이전에 저장한 결과에는 손 계수(rent+fitout)로 계산한 전략이 있다 — 지금 서빙은 그 값을 내지 않는다((b)).
  // 숫자는 저장한 그대로 다시 그리되, 그 사실을 맨 위에 밝힌다(안 밝히면 거둔 값이 실측처럼 다시 읽힌다).
  const legacy = Object.values(r.scenarios).some((s) => s.basis === "rent+fitout");
  return (
    <div className="saved-posting">
      {legacy && (
        <p className="saved-note">
          ⚠ {BASIS_LABEL["rent+fitout"]} — 원가·인건비가 빠진 손 계수로 계산한 결과라 마진이 크고 회수기간이 실제보다 짧게 나온다.
          지금은 실측 재료가 없는 전략을 계산하지 않는다 — 같은 자리를 다시 계산해 볼 것.
        </p>
      )}
      <div className="posting-input-summary">
        계산에 사용한 입력: {saved.input?.industry_type || "자리 기본 업종"} · 권리금 {saved.input?.prem === undefined ? "미입력 · 0 전제" : won(saved.input.prem)}
        {" · "}{TIER_LABEL[saved.input?.strategy ?? ""]?.name ?? "세 전략 비교"}{r.inputs_quarter ? ` · ${r.inputs_quarter} 기준` : ""}
      </div>
      <div className="tiers">
        {Object.entries(r.scenarios).map(([key, s]) => <TierCard key={key} tierKey={key} s={s} />)}
      </div>
    </div>
  );
}

function TierCard({ tierKey, s, before }: { tierKey: string; s: TierScenario; before?: TierScenario }) {
  const meta = TIER_LABEL[tierKey] ?? { name: s.name ?? tierKey, sub: s.sub ?? "" };
  // 실측 재료가 없어 계산하지 않은 전략 — 「모른다」다. 숫자를 지어내지 않고 이유를 싣는다(2026-10-28 (b))
  if (!tierAvailable(s)) {
    return (
      <Card className="tier dead">
        <div className="thd"><span className="tname">{meta.name}</span></div>
        <div className="tsub">{meta.sub}</div>
        <div className="trow big"><span>{TIER_UNAVAILABLE_LABEL}</span></div>
        <div className="tier-difference">{s.unavailable_reason ?? "실측 자료가 없어 계산하지 않았어요."}</div>
      </Card>
    );
  }
  const prev = tierAvailable(before) ? before : undefined;
  return (
    <Card className={"tier" + (s.recommended ? " rec" : "") + (s.viable ? "" : " dead")}>
      <div className="thd">
        <span className="tname">{meta.name}</span>
        {s.recommended && <span className="trec">추천</span>}
      </div>
      <div className="tsub">{meta.sub}</div>

      {/* ⚠ invest_mn 은 **백만원** 단위다(백엔드 services/districts: inv × 100 ÷ net = roi_months). 2026-10-13 까지 이 칸이
          만원으로 찍혀 초기 투자가 100배 작게 보였다 — 화면설계서 5판 §12 U8. #board(PageDashboard)는 「백만」으로 맞게 찍는다 */}
      <div className="trow"><span>초기 투자</span><span>{won(s.invest_mn * 100)}</span></div>
      <div className="trow"><span>월 비용</span><span>{won(s.month_cost)}</span></div>
      <div className="trow"><span>월 매출</span><span>{won(s.month_rev)}</span></div>
      <div className="trow big">
        <span>월 순익</span>
        <span className={s.month_net > 0 ? "pos" : "neg"}>{won(s.month_net)}</span>
      </div>
      <div className="trow">
        <span>회수기간</span>
        {/* "모른다"와 "안 된다"는 다른 정보다 — 순익이 0 이하면 회수기간이 정의되지 않는다 */}
        <span>{s.viable ? `${s.roi_months}개월` : "회수 불가"}</span>
      </div>
      {prev && <div className="tier-difference" aria-label={`${meta.name} 직전 계산과 비교`}>
        <b>직전 계산 대비</b>
        <span>초기 투자 {difference((s.invest_mn - prev.invest_mn) * 100, "만원")}</span>
        <span>월 순익 {difference(s.month_net - prev.month_net, "만원")}</span>
        <span>회수기간 {s.viable && prev.viable
          ? difference(s.roi_months - prev.roi_months, "개월") : `${prev.viable ? `${prev.roi_months}개월` : "회수 불가"} → ${s.viable ? `${s.roi_months}개월` : "회수 불가"}`}</span>
      </div>}
    </Card>
  );
}

function difference(value: number, unit: string): string {
  return `${value > 0 ? "+" : ""}${Number(value.toFixed(2)).toLocaleString()}${unit}`;
}

/** 입력 출처 라벨 — 프록시를 실측으로 오독하지 않게 한다. 모르는 값은 그대로 노출한다. */
/* ───────────────── 결론 1줄 + 근거 3줄 (2026-09-13) ─────────────────
 *
 * 이 화면이 답한 것과 그 답을 세운 값. Platform·Program 의 `headline()` 과 같은 자리다.
 *
 * 상태가 셋이고 **셋을 섞지 않는다**:
 *   ① 아직 자리를 안 골랐다      → 무엇을 고르면 무엇이 나오는지 말한다
 *   ② 골라서 계산했고 회수된다   → 어느 전략이 몇 개월인지 말한다
 *   ③ 계산했는데 셋 다 회수 불가 → **"추천이 없다"가 아니라 "회수가 안 된다"** 고 말한다
 *
 * ⚠ 권리금이 `absent`(입력 없음)면 결론에 그 사실을 싣는다. 0 을 전제로 낸 회수기간을
 *   실측처럼 읽으면 그 숫자가 곧 거짓말이 된다 — 이 화면 주석 §화면 원칙과 같은 규칙이다.
 */
function postingHeadline({ districtName, unit, unitCount, unitsLoaded, result, premInput }: {
  districtName: string;
  unit?: Posting;
  unitCount: number;
  unitsLoaded: boolean;
  result: SimulateResult | null;
  premInput: string;
}): { verdict: React.ReactNode; grounds: Ground[]; sources: React.ReactNode[] } {
  const sources: React.ReactNode[] = [
    "임대료 R-ONE 실측", "면적 건축물대장", "영업비용률 KOSIS", "권리금 기업 입력",
  ];

  // ① 아직 계산 전.
  if (!result) {
    return {
      verdict: unitCount
        ? <>{districtName}에 실측 공실 <b>{unitCount.toLocaleString()}곳</b>이 있다. 자리와 업종을 고르면 세 가격대의 회수기간을 낸다.</>
        : unitsLoaded
          ? <>{districtName}에는 계산할 실측 공실 자리가 없다.</>
          : <>{districtName}의 공실 자리를 불러오는 중이다.</>,
      grounds: [
        { label: "고를 수 있는 자리", value: unitCount ? `${unitCount.toLocaleString()}곳` : unitsLoaded ? "0곳" : "불러오는 중", source: "건축물대장 실측 인벤토리" },
        { label: "비교하는 가격대", value: "고급화 · 가성비 · 기능중심 3전략" },
        { label: "권리금", value: premInput ? `${Number(premInput).toLocaleString()}만원 입력됨` : "미입력 — 0 을 전제로 계산한다", source: "공개 통계 없음 · 기업 입력 계약" },
      ],
      sources,
    };
  }

  // ⚠ 전략 이름은 `TIER_LABEL[key]` 로 읽는다. `scenario.name` 은 백엔드가 원시 키
  //   ("value")를 주기도 해서 그대로 쓰면 화면 나머지(TierCard)와 다른 이름이 뜬다.
  const entries = Object.entries(result.scenarios);
  if (result.economics || result.calculation_status === "unavailable") {
    return {
      verdict: result.economics?.status === "calculated" ? `${result.economics.label} 운영 조건으로 계산했습니다.` : result.unavailable_reason ?? "운영 조건 입력이 필요합니다.",
      grounds: [{ label: "계산 근거", value: result.economics ? "사용자 입력 시나리오" : "업종별 근거 입력 필요", source: "입지 추천·매출 예측과 별도" }],
      sources: ["사용자 입력 운영 조건 · 조건부 계산"],
    };
  }
  const label = (key: string, s: TierScenario) => TIER_LABEL[key]?.name ?? s.name;
  // 자료 부족 전략(실측 재료 없음 · 2026-10-28 (b))은 숫자가 없어 판정에서 뺀다 — 「모른다」지 「안 된다」가 아니다
  const computed = entries.flatMap(([k, t]) => (tierAvailable(t) ? [[k, t] as const] : []));
  const missing = entries.filter(([, t]) => !tierAvailable(t)).map(([k, t]) => label(k, t));
  const viable = computed.filter(([, t]) => t.viable);
  // 추천 전략이 회수 불가일 수는 없지만, 백엔드가 recommended 를 안 준 경우를 대비해
  // **회수되는 것 중 가장 빠른 것**으로 떨어진다. 없는 값을 지어내지 않는다.
  const best = viable.find(([, t]) => t.recommended)
    ?? [...viable].sort((a, b) => a[1].roi_months - b[1].roi_months)[0];
  const where = unit?.n ?? result.unit_id;
  const premAbsent = result.inputs_source?.prem === "absent";
  const basisKey = computed[0]?.[1].basis;
  const basis = basisKey ? (BASIS_LABEL[basisKey] ?? basisKey) : "미상";
  const missingNote = missing.length ? `${missing.join("·")}은 ${TIER_UNAVAILABLE_LABEL}이라 계산하지 않았다` : undefined;

  // ⓪ 계산한 전략이 하나도 없다 — 「모른다」다. ③ 의 「회수되지 않는다」로 떨어지면 계산하지 않은 것을 안 된다고 말한다
  //    (서버는 자료 부족 전략만 고른 요청에 계산 불가로 답하지만, 다른 공급자·저장 결과가 이 모양일 수 있다 — 10-28 리뷰).
  if (!computed.length) {
    const why = entries.find(([, t]) => t.unavailable_reason)?.[1].unavailable_reason;
    return {
      verdict: <><b>{where}</b>는 고른 전략을 계산하지 않았다 — {why ?? "실측 자료가 없다"}.</>,
      grounds: [{ label: "계산한 전략", value: "없음", source: missingNote }],
      sources,
    };
  }

  // ③ 계산한 전략이 모두 회수 불가 — 이것도 답이다. 비워 두면 "계산이 안 됐다"로 읽힌다.
  if (!best) {
    return {
      verdict: <><b>{where}</b>는 {missing.length ? "계산한 전략 모두" : "세 전략 모두"} 회수되지 않는다.{result.unviable_note ? ` ${result.unviable_note}` : ""}</>,
      grounds: [
        { label: "회수되는 전략", value: `없음 (${computed.length}전략 중 0)`, source: missingNote ?? `비용 기준 ${basis}` },
        { label: "월 임대료", value: unit ? won(unit.rent) : "미상", source: "R-ONE 실측" },
        { label: "권리금", value: premAbsent ? "미입력 — 0 전제" : "기업 입력 반영", source: premAbsent ? "이 값을 넣으면 회수기간이 더 늘어난다" : undefined },
      ],
      sources,
    };
  }

  // ② 회수된다.
  const [bestKey, bestTier] = best;
  const bestName = label(bestKey, bestTier);
  return {
    verdict: (
      <>
        <b>{where}</b>는 <b>{bestName}</b> 전략으로 <b>{bestTier.roi_months}개월</b>에 회수가 예상됩니다
        {premAbsent && <> — 단 <b>권리금 0 을 전제</b>로 한 값이다</>}.
      </>
    ),
    grounds: [
      {
        label: "가장 빠른 회수",
        value: `${bestName} · ${bestTier.roi_months}개월 (월 순익 ${won(bestTier.month_net)})`,
        source: `비용 기준 ${basis}`,
      },
      {
        label: "회수되는 전략",
        value: `${computed.length}전략 중 ${viable.length}개`,
        source: [viable.length < computed.length ? `${computed.length - viable.length}개는 월 순익이 0 이하다` : "", missingNote ?? ""]
          .filter(Boolean).join(" · ") || undefined,
      },
      {
        label: "권리금",
        value: premAbsent ? "미입력 — 0 을 전제로 계산" : "기업 입력 반영",
        source: premAbsent ? "공개 통계가 없어 그 자리에 들어갈 기업만 안다" : "입력 계약",
      },
      // 네 줄째부터는 Verdict 가 접는다 — 규칙이 세 줄이지 값이 셋인 것은 아니다.
      {
        label: "계산 경로",
        value: result.source === "copilot" ? "외부 AI 창업 코파일럿" : "내부 3-Tier 폴백",
        source: result.source_note ?? undefined,
      },
    ],
    sources,
  };
}

function srcLabel(v: string | undefined): string {
  return ({
    rone: "실측", flpop: "실측", "flpop+seed": "실측+예시",
    "flpop+jipgyegu": "실측",
    seed: "예시", absent: "전제(0)", contract: "직접 입력", user_input: "사용자 입력", none: "자료 없음(보정 안 함)",
    bldg: "실측", "gold-ledger": "실측", "bldg+split": "실측 면적·분할 추정",
  } as Record<string, string>)[v ?? ""] ?? (v ?? "미상");
}
/** 실측(초록) / 프록시(회색 점선) / 전제(노랑 점선). 모르는 값은 프록시로 눕힌다 —
 *  라벨을 모르는 것을 실측으로 올리면 그게 곧 출처 왜곡이다. */
function srcClass(v: string | undefined): string {
  if (["contract", "rone", "flpop", "flpop+jipgyegu", "bldg", "gold-ledger", "flr_ouln"].includes(v ?? "")) {
    return "is-real";
  }
  if (v === "absent") return "is-absent";
  return "is-proxy";
}
