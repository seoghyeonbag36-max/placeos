import { useEffect, useState } from "react";
import { getProgramNetwork, type ProgramNetwork, type ProgramStage } from "@/lib/api";
import { readNetworkNotes, saveNetworkNotes, type NetworkNotes } from "@/lib/programSaved";
import SourceStatusLine from "./SourceStatusLine";

/** 네트워킹 — 이 상권에서 계약 전에 누구에게 묻고, 개업 뒤 누구와 함께할 수 있나(2026-11-07 리뉴얼).
 *
 *  1단계 공식 네트워크(행사·네트워크 공고 · 기업마당 행사정보 · 지원기관 누리집)와 2단계 방문형 이웃 가게
 *  (함께 모이는 업종 + 물어볼 질문)만 보인다. PlaceOS 는 가게 연락처를 모으거나 대신 연락하지 않는다
 *  (정보통신망법 제50조 — 영리 목적 광고성 정보는 수신자의 사전 동의). 사용자끼리 잇는 3단계는 파일럿 뒤(결정 D3). */
export default function NetworkingPanel({ districtId, industryKey, industryLabel, stage }: {
  districtId: string; industryKey?: string; industryLabel?: string; stage?: ProgramStage;
}) {
  const reqKey = `${districtId}|${industryKey ?? ""}|${industryLabel ?? ""}|${stage ?? ""}`;
  const [got, setGot] = useState<{ key: string; data?: ProgramNetwork; error?: true } | null>(null);
  const [notes, setNotes] = useState<NetworkNotes>(() => readNetworkNotes(districtId));
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let live = true;
    getProgramNetwork(districtId, { industry: industryKey, industryLabel, stage })
      .then((r) => { if (live) setGot({ key: reqKey, data: r }); })
      .catch(() => { if (live) setGot({ key: reqKey, error: true }); });
    return () => { live = false; };
  }, [reqKey, districtId, industryKey, industryLabel, stage]);
  const data = got?.key === reqKey ? got.data ?? null : null;
  const error = got?.key === reqKey && !!got.error;

  function update(next: NetworkNotes) {
    setNotes(next);
    setNotice(saveNetworkNotes(districtId, next) ? "" : "저장하지 못했습니다(브라우저 저장 공간).");
  }
  const toggleQuestion = (q: string) =>
    update({ ...notes, checked: notes.checked.includes(q) ? notes.checked.filter((x) => x !== q) : [...notes.checked, q] });

  return <div className="program-panel">
    {error && <p role="alert">네트워킹 자료를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.</p>}
    {!data && !error && <p role="status">네트워킹 자료 확인 중…</p>}
    {data && <>
      <p className="program-note">{data.note}</p>

      <h3>공식 행사·네트워크 · {data.region.label}</h3>
      <SourceStatusLine sources={data.sources} />
      {data.events.length > 0 && <p className="program-note">순서: 이 지역에서 열리는 행사 → 전국 행사 → 같은 시도의 다른 시군구 행사 ·
        같은 범위에서는 업종 언급 · 마감이 가까운 순 · 다른 시도에서 열리는 행사는 뺐어요{data.total_events > data.events.length ? ` — ${data.total_events}건 중 ${data.events.length}건` : ""}.</p>}
      {data.events.length === 0
        ? <p>지금 이 지역에서 열려 있는 창업 행사·네트워크 공고가 없습니다.</p>
        : <ol className="program-list">{data.events.map((e) => <li key={e.id} className="program-item">
          <p className="program-item-meta">{e.source_label}{e.kind ? ` · ${e.kind}` : ""}{e.area ? ` · ${e.area}` : ""}{e.org ? ` · ${e.org}` : ""}</p>
          <h4>{e.url ? <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a> : e.title}</h4>
          <p><b>일정</b> {e.start || e.end ? `${e.start ?? "?"} ~ ${e.end ?? "?"}` : e.period_text ?? "원문 확인"}
            {e.apply_period ? ` · 접수 ${e.apply_period}` : ""}</p>
          {e.summary && <p className="program-summary">{e.summary}</p>}
          <p className="program-chips">{e.matched.map((m) => <span key={m}>{m}</span>)}</p>
        </li>)}</ol>}

      <h3>이웃 가게 — 직접 찾아가 물어보기</h3>
      {data.complements.length > 0
        ? <p>이 도시에서 {industryLabel ?? "내 업종"}과 함께 모이는 업종:{" "}
          {data.complements.map((c) => <span key={c.key ?? c.label} className="program-chip-inline">{c.label}(lift {c.lift})</span>)}</p>
        : null}
      {data.complements_note && <p className="program-note">{data.complements_note}</p>}
      <p className="program-note">이웃 가게의 위치는 Posting 「주변 업종」 지도와 Page 지도에서 볼 수 있어요(공개 상가정보 — 상호·업종·위치만).</p>
      <fieldset className="program-questions">
        <legend>계약 전에 물어볼 것 — 확인한 질문에 표시</legend>
        {data.questions.map((q) => <label key={q}>
          <input type="checkbox" checked={notes.checked.includes(q)} onChange={() => toggleQuestion(q)} /> {q}
        </label>)}
        <label>들은 내용 메모(이 브라우저에만 저장 · 결과 리포트에 실립니다)
          <textarea rows={3} maxLength={1500} value={notes.memo} onChange={(e) => update({ ...notes, memo: e.target.value })}
            placeholder="예: 상인회 월 회비 있음 · 권리금은 층마다 다르다고 함" />
        </label>
      </fieldset>

      <h3>지원기관</h3>
      <ul className="program-directory">{data.directory.map((d) => <li key={d.url}>
        <a href={d.url} target="_blank" rel="noreferrer">{d.name}</a> <small>{d.role}</small>
      </li>)}</ul>
    </>}
    {notice && <p role="status">{notice}</p>}
  </div>;
}
