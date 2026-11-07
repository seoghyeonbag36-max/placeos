import { useEffect, useState } from "react";
import { getSupportPrograms, type ProgramStage, type SupportItem, type SupportPrograms as Data } from "@/lib/api";
import { readSavedSupport, toggleSavedSupport, type SavedSupport } from "@/lib/programSaved";
import SourceStatusLine from "./SourceStatusLine";

const STAGE_OPTIONS: { value: ProgramStage | ""; label: string }[] = [
  { value: "pre_founder", label: "예비창업자" }, { value: "founder", label: "기창업자(업종 바꾸기·이전)" }, { value: "", label: "단계 구분 없이" },
];

function period(it: SupportItem): string {
  if (it.start || it.end) return `${it.start ?? "?"} ~ ${it.end ?? "?"}`;
  return it.deadline_text ?? "신청기한은 원문 확인";
}

/** 지원 프로그램 — 내 단계·업종·지역에 지금 신청할 수 있는 국가·지자체 지원(2026-11-07 리뉴얼).
 *  자격 판정이 아니다: 지역·단계·업종 문구만 맞춘 「조건이 맞을 수 있는 공고」다. 금액은 원문에서만. */
export default function SupportPrograms({ districtId, stage: initialStage, industryLabel }: {
  districtId: string; stage?: ProgramStage; industryLabel?: string;
}) {
  const [stage, setStage] = useState<ProgramStage | "">(initialStage ?? "");
  const reqKey = `${districtId}|${stage}|${industryLabel ?? ""}`;
  const [got, setGot] = useState<{ key: string; data?: Data; error?: true } | null>(null);
  const [saved, setSaved] = useState<SavedSupport[]>(() => readSavedSupport(districtId));
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let live = true;
    getSupportPrograms(districtId, { stage: stage || undefined, industry: industryLabel })
      .then((r) => { if (live) setGot({ key: reqKey, data: r }); })
      .catch(() => { if (live) setGot({ key: reqKey, error: true }); });
    return () => { live = false; };
  }, [reqKey, districtId, stage, industryLabel]);
  const data = got?.key === reqKey ? got.data ?? null : null;
  const error = got?.key === reqKey && !!got.error;

  function toggle(it: SupportItem) {
    const r = toggleSavedSupport(districtId, it);
    setSaved(r.saved);
    setNotice(r.ok ? "이 브라우저에 담았습니다 — 가설 검증의 결과 리포트에 실립니다." : "저장하지 못했습니다(브라우저 저장 공간).");
  }

  return <div className="program-panel">
    <div className="program-panel-head">
      <h3>지원 공고{data ? ` · ${data.region.label}` : ""}</h3>
      <label className="program-inline">단계
        <select value={stage} onChange={(e) => setStage(e.target.value as ProgramStage | "")}>
          {STAGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
    </div>
    {error && <p role="alert">지원 공고를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요 — 원문 포털:
      {" "}<a href="https://www.k-startup.go.kr" target="_blank" rel="noreferrer">K-Startup</a> ·
      {" "}<a href="https://www.bizinfo.go.kr" target="_blank" rel="noreferrer">기업마당</a> ·
      {" "}<a href="https://www.sbiz24.kr" target="_blank" rel="noreferrer">소상공인24</a></p>}
    {!data && !error && <p role="status">지원 공고 확인 중…</p>}
    {data && <>
      <p className="program-note">{data.note}</p>
      <SourceStatusLine sources={data.sources} />
      {data.items.length > 0 && <p className="program-note">순서: 내 시군구 → 시도 → 전국 공고, 같은 시도의 다른 시군구
        공고(대개 그 주민·기업 대상)는 맨 뒤 · 같은 범위에서는 업종 언급 · 마감이 가까운 순{data.total > data.items.length ? ` — ${data.total}건 중 ${data.items.length}건을 보였습니다` : ""}.</p>}
      {data.items.length === 0
        ? <p>지금 조건에 맞는 모집 중 공고가 없습니다. 단계를 바꾸거나 원문 포털에서 확인하세요.</p>
        : <ol className="program-list">
          {data.items.map((it) => {
            const on = saved.some((x) => x.id === it.id);
            return <li key={it.id} className="program-item">
              <p className="program-item-meta">{it.source_label}{it.org ? ` · ${it.org}` : ""}{it.category ? ` · ${it.category}` : ""}</p>
              <h4>{it.url ? <a href={it.url} target="_blank" rel="noreferrer">{it.title}</a> : it.title}</h4>
              <p><b>신청</b> {period(it)}{it.target ? ` · 대상 ${it.target}` : ""}</p>
              {it.summary && <p className="program-summary">{it.summary}</p>}
              <p className="program-chips">{it.matched.map((m) => <span key={m}>{m}</span>)}</p>
              <button type="button" aria-pressed={on} onClick={() => toggle(it)}>{on ? "담음 · 빼기" : "관심 공고로 담기"}</button>
            </li>;
          })}
        </ol>}
    </>}
    {notice && <p role="status">{notice}</p>}
  </div>;
}
