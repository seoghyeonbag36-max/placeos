import { useEffect, useState } from "react";
import { getDistrictEvents, type MarketingEvent } from "@/lib/api";
import "./RenewalTools.css";

import { readEventLink, type EventLink } from "@/lib/eventLink";
/** 실제 행사 후보와 점주가 작성한 연계 계획을 구분한다. 게시·예약을 실행하지 않는다. */
export default function EventLinkPlanner({ districtId }: { districtId: string }) {
  const [events, setEvents] = useState<MarketingEvent[] | null>(null);
  const [source, setSource] = useState("");
  const [draft, setDraft] = useState<EventLink>(() => readEventLink(districtId) ?? { name: "", when: "", online: "", offline: "", evidence: "" });
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let live = true;
    getDistrictEvents(districtId).then(r => { if (live) {
      setEvents(r.events_source === "seoul-open-data" ? r.events : []);
      setSource(r.events_source === "seoul-open-data" ? "서울 공개 문화행사" : r.events_note ?? "확인된 행사 원천 없음");
    } }).catch(() => { if (live) { setEvents([]); setSource("행사 자료를 불러오지 못했습니다."); } });
    return () => { live = false; };
  }, [districtId]);
  function save() {
    try { localStorage.setItem(`placeos.event-link.${districtId}`, JSON.stringify(draft)); setNotice("연계 계획을 이 브라우저에 저장했습니다. 검증 리포트에 포함됩니다."); }
    catch { setNotice("저장하지 못했습니다. 브라우저 저장 공간을 확인하세요."); }
  }
  return <section className="renewal-tool" aria-label="온·오프라인 행사 연계">
    <h2>온 · 오프라인 행사 연계</h2>
    <p>상권 행사를 고르고 온라인 알림과 매장 방문 혜택을 함께 계획하세요. 일정·참가 조건은 원문 확인이 필요합니다.</p>
    <p>출처: {source || "확인 중…"}</p>
    {events === null ? <p role="status">행사 불러오는 중…</p> : events.length === 0 ? <p>확인된 행사 후보가 없습니다. 직접 확인한 행사를 아래에 작성하세요.</p> : <ul>{events.map(e => <li key={e.id}>
      <strong>{e.n}</strong> · {e.when} · {e.place}
      {e.link && /^https?:\/\//i.test(e.link) && <a href={e.link} target="_blank" rel="noreferrer">행사 원문</a>}
      <button type="button" onClick={() => setDraft({ ...draft, name: e.n, when: e.when, evidence: e.link ?? "" })}>이 행사와 연계</button>
    </li>)}</ul>}
    <form onSubmit={e => { e.preventDefault(); save(); }}>
      {([["name", "행사명"], ["when", "행사 일정"], ["evidence", "출처·확인 메모"], ["online", "온라인 홍보·쿠폰·예약 계획"], ["offline", "오프라인 참여·방문 혜택·측정 방법"]] as const).map(([key, label]) => <label key={key}>{label}<textarea required={key === "name"} maxLength={1500} value={draft[key]} onChange={e => { setNotice(""); setDraft({ ...draft, [key]: e.target.value }); }} /></label>)}
      <button type="submit">행사 연계 계획 저장</button>
    </form>
    {notice && <p role="status">{notice}</p>}
    <p>계획 출처: 사용자 입력 · 참여 합의·게시·예약 및 실행 성과는 미확인</p>
  </section>;
}
