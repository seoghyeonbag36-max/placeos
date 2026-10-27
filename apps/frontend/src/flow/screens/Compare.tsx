/**
 * 상권 나란히 보기 — 화면설계서 5판 §5-1 R1-c(2026-10-24). 상권 2~3곳의 사실을 같은 줄로 놓는다.
 *
 * 들어오는 곳: R1 「상권 나란히 비교하기」에서 고른 상권 · 홈 「상권 나란히 보기」(보는 상권 + 저장한 자리의 상권).
 * 그전에는 비교가 건물끼리(지도 탐색 Page 「후보 비교」) · 한 상권 안의 자리끼리(Platform 「자리 비교」)뿐이었고,
 * 상권끼리는 R2 를 하나씩 열어 머리로 견줘야 했다.
 * 비교가 일인 화면이라 후보를 한 화면에 나란히 둔다(§3-4 반례). 종합 점수 · 이긴 쪽 표시는 없다(lib/districtCompare 머리말).
 */
import { useMemo, useState } from "react";
import DistrictCompareTable from "@/components/DistrictCompare";
import { compareColumns, compareIds, compareRows, fitRulerNames, useDistrictCompare, type CompareColumn } from "@/lib/districtCompare";
import { useFlow } from "../context";
import { useFlowData } from "../data";
import { eun, ro } from "../format";
import { go } from "../route";
import { setDistrict, type FlowState } from "../state";
import { CloseButton, Details, FlowScreen, LoadError, ResultView, Sheet, SkeletonRows, WarnLine } from "../ui";
import { hasRanking, useDistricts, useWorkIndustry } from "./common";

/** 상권을 바꾸면 비워지는 답이 있는가 — setDistrict 가 자리·권리금·가격대·금액(예산 빼고)을 비운다(state.ts §2-3) */
function losesAnswers(s: FlowState, to: string): boolean {
  if (s.districtId === to) return false;
  const c = s.costs;
  return !!s.spaceId || !!s.premium || !!s.tier
    || [c.deposit, c.rent, c.maintenance, c.premium, c.fitout, c.equipment, c.otherMonthly].some((v) => v != null);
}

export function Compare({ param }: { param: string }) {
  const { state, update } = useFlow();
  const data = useFlowData();
  const ds = useDistricts();
  const work = useWorkIndustry();
  const ids = useMemo(() => compareIds(param.split(",")), [param]);
  const cols = ds.status === "ready" ? compareColumns(ids, ds.data) : [];
  const colIds = cols.map((c) => c.id);
  const ranked = hasRanking(work) ? work : null;
  const cmp = useDistrictCompare(colIds, ranked?.key ?? null, data);
  const [switchTo, setSwitchTo] = useState<CompareColumn | null>(null);
  const caption = `상권 비교${work ? ` · ${work.label}` : ""}`;

  if (ds.status === "loading") {
    return <FlowScreen wide back="/home" right={<CloseButton />} caption={caption} title="상권을 나란히 놓고 있어요">
      <SkeletonRows n={6} label="상권 비교를 불러오는 중" /></FlowScreen>;
  }
  if (ds.status === "error") {
    return <FlowScreen wide back="/home" right={<CloseButton />} caption={caption} title="상권 목록을 불러오지 못했어요">
      <LoadError what="상권 목록" error={ds.error} onRetry={ds.retry} /></FlowScreen>;
  }
  if (cols.length < 2) {
    return (
      <FlowScreen wide back="/home" right={<CloseButton />} caption={caption} title="비교할 상권이 두 곳 이상 필요해요">
        <ResultView title="지금 서비스하는 상권을 두 곳 이상 골라 주세요"
          body={cols.length === 1 ? `${cols[0].name} 말고 한 곳을 더 골라야 나란히 볼 수 있어요.` : "주소의 상권을 찾지 못했어요."}
          action={{ label: "상권 고르기", onClick: () => go(state.goal && state.goal !== "pivot" && state.industryKey ? "/districts" : "/district-search") }} />
      </FlowScreen>
    );
  }

  const rows = compareRows(colIds, cmp.loads, ranked ? { key: ranked.key, label: ranked.label } : null, cmp.fit);
  const rulerNames = fitRulerNames(cmp.fit, colIds);
  const quarter = colIds.map((id) => cmp.loads[id].rent).find((r) => r.status === "ready" && r.data.quarter);
  const openSpaces = (id: string) => {
    update((s) => setDistrict(s, id));
    data.prefetch(() => data.rent(id), () => data.floorUnits(id), () => data.postings(id));
    go("/spaces");
  };
  const pick = (col: CompareColumn) => (losesAnswers(state, col.id) ? setSwitchTo(col) : openSpaces(col.id));
  return (
    <FlowScreen wide back="/home" right={<CloseButton />} caption={caption} title={`상권 ${cols.length}곳을 나란히 놓았어요`}
      sub="어느 상권이 낫다고 점수를 매기지 않아요. 줄마다 근거를 붙였어요.">
      <DistrictCompareTable columns={cols} rows={rows} caption={`상권 ${cols.length}곳 나란히 보기`}
        action={(col) => (
          <button type="button" className="fl-btn fl-btn-weak fl-compare-go" aria-label={`${col.name} 빈 자리 보기`} onClick={() => pick(col)}>
            빈 자리 보기
          </button>
        )} />
      {work && !ranked && <p className="fl-note">{eun(work.label)} 추천 모델이 다루지 않는 업종이라 입지 점수는 나란히 놓지 않았어요.</p>}
      {/* 입지 점수 순위는 잣대(모델) 묶음마다 따로다(2026-10-27) — 묶음이 섞이면 점수를 견주지 말라고 밝힌다 */}
      {ranked && rulerNames && <WarnLine>입지 점수는 {rulerNames.join(" · ")} 묶음을 서로 다른 모델로 매겼어요 — 묶음이 다른 상권끼리는 점수를 견주지 마세요.</WarnLine>}
      {cols.filter((c) => c.caveat).map((c) => <WarnLine key={c.id}>{c.name}: {c.caveat}</WarnLine>)}
      {/* 서울시 상권분석(유형·붐비는 때의 재료)은 서울 상권에만 선다 */}
      <p className="fl-source">카카오 플레이스{cols.some((c) => (c.city ?? "seoul") === "seoul") ? " · 서울시 상권분석" : ""}{quarter?.status === "ready" ? ` · R-ONE ${quarter.data.quarter}` : " · R-ONE"} · 건축물대장{ranked ? " · 업종 추천 모델" : ""}</p>
      <Details summary="어떻게 셌나요?">
        <ul className="fl-facts">
          {ranked && <li>입지 점수는 비슷한 자리에 {ranked.label} 가게가 이미 얼마나 모여 있는지를 추천 모델이 배운 값이에요(×100). 매출이나 생존율이 아니에요.</li>}
          <li>상권 유형 · 무엇이 모여 있나 · 언제 붐비나는 상권 소개와 같은 값이에요.</li>
          <li>빈 층은 건축물대장·상가정보로 센 수예요. 실제 매물인지는 현장에서 꼭 확인해요.</li>
          <li>1층 월세는 R-ONE 표본 평균으로 낸 추정이에요. 호가가 아니고 보증금·권리금·관리비는 빠져 있어요.</li>
          <li>본전 계산 가능한 빈 자리는 건물 단위로 본전 시점을 낼 수 있는 빈 자리 수예요.</li>
          <li>모두 더한 종합 점수는 없어요 — 무엇을 더 무겁게 볼지는 직접 정해요.</li>
        </ul>
      </Details>
      <Sheet open={switchTo !== null} onClose={() => setSwitchTo(null)} title={switchTo ? `${ro(switchTo.name)} 바꿀까요?` : ""}>
        <p>상권을 바꾸면 고른 자리{state.spaceLabel ? `(${state.spaceLabel})` : ""}와 입력한 금액이 지워져요. 저장한 것과 예산은 남아요.</p>
        <button type="button" className="fl-btn fl-btn-strong" onClick={() => { const to = switchTo; setSwitchTo(null); if (to) openSpaces(to.id); }}>
          바꾸고 빈 자리 보기
        </button>
      </Sheet>
    </FlowScreen>
  );
}
