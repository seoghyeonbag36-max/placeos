import { useEffect, useId, useRef, useState } from "react";
import DistrictCompareTable from "@/components/DistrictCompare";
import { FlowData } from "@/flow/data";
import { eun } from "@/flow/format";
import type { DistrictSummary } from "@/lib/api";
import { compareColumns, compareRows, useDistrictCompare, type CompareIndustry } from "@/lib/districtCompare";

/**
 * 지도 탐색 Platform 의 「상권 비교」(2026-10-24) — 상권을 바꿔 가며 담은 2~3곳을 나란히 본다.
 * 흐름의 「상권 나란히 보기」(R1-c)와 같은 줄·같은 규칙이다(lib/districtCompare). Page 의 「후보 비교」(건물끼리)와 같은 틀
 * (네이티브 <dialog> + showModal — 포커스가 대화상자 안에 갇히고 Esc 로 닫힌다)을 쓴다.
 */
export default function DistrictCompareDialog({ ids, districts, industry, unrankedIndustry, onOpenDistrict, onClose }: {
  ids: string[];
  districts: DistrictSummary[];
  /** 순위를 낼 수 있는 내 업종 — 없으면 입지 점수 줄을 빼고 */
  industry: CompareIndustry | null;
  /** 내 업종이 있지만 추천 모델 밖이면 그 이름(한 줄로 말한다) */
  unrankedIndustry?: string | null;
  onOpenDistrict: (id: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  // 같은 요청을 한 번만 — 흐름과 같은 캐시 규칙(대화상자를 다시 열면 새로 받는다)
  const [loaders] = useState(() => new FlowData());
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previousFocus?.focus(); };
  }, []);
  const cols = compareColumns(ids, districts);
  const colIds = cols.map((c) => c.id);
  const cmp = useDistrictCompare(colIds, industry?.key ?? null, loaders);
  const rows = compareRows(colIds, cmp.loads, industry, cmp.fit);
  return (
    <dialog ref={dialog} className="dcmp-dialog" aria-labelledby={titleId}
      onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <header>
        <div><span className="dcmp-eyebrow">PLATFORM · 상권 비교</span>
          <h2 id={titleId}>상권 {cols.length}곳 나란히</h2></div>
        <button type="button" className="dcmp-btn" onClick={onClose} aria-label="상권 비교 닫기" autoFocus>닫기</button>
      </header>
      <p className="dcmp-note">어느 상권이 낫다고 점수를 매기지 않습니다. 줄마다 근거(모델 · 관측 · 대장 실측 · 추정)를 붙였습니다.</p>
      <DistrictCompareTable columns={cols} rows={rows} caption={`상권 ${cols.length}곳 나란히 보기`}
        action={(col) => (
          <button type="button" className="dcmp-btn dcmp-open" aria-label={`${col.name} 상권 보기`} onClick={() => onOpenDistrict(col.id)}>
            이 상권 보기
          </button>
        )} />
      {unrankedIndustry && <p className="dcmp-note">{eun(unrankedIndustry)} 추천 모델이 다루지 않는 업종이라 입지 점수는 나란히 놓지 않았습니다.</p>}
      {cols.filter((c) => c.caveat).map((c) => <p key={c.id} className="dcmp-note is-caveat">▣ {c.name}: {c.caveat}</p>)}
      <p className="dcmp-note">입지 점수는 비슷한 자리에 그 업종이 이미 모여 있는 정도를 모델이 배운 값입니다 — 매출·생존율이 아닙니다.
        1층 월세는 R-ONE 표본 평균으로 낸 추정이고, 빈 층은 건축물대장·상가정보로 셌습니다. 공실 예측은 검증 중이라 싣지 않았습니다.</p>
    </dialog>
  );
}
