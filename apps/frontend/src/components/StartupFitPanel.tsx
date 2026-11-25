/**
 * Page 건물 상세 — 빈 층마다 「창업 가능 등급」과 「건물주 등록」(2026-11-25 사용자 요청).
 *
 * 등급은 **허가 판정이 아니다.** 대장 · 토지이음 기재(입점 점검 규칙 · 일반 창업 6업종)와 Proposal 3-Tier 1층 기준 추정으로
 * 가른 1차 분류이고, 층마다 이유를 펼쳐 보인다. 기준선은 서울 같은 가격대 평균 영업이익률(KOSIS)이다.
 * 건물주 등록은 열 때마다(그리고 「다시 확인」을 누를 때마다) 서버가 DB 를 읽는다 — 직거래 표가 없으면 「확인 준비 중」으로
 * 적고 **0 건처럼 그리지 않는다**(모르는 것을 없다고 세지 않는다 · 서버 `owner_status`).
 * 색만으로 등급을 가르지 않는다 — 기호 + 글자를 같이 쓴다.
 */
import { useEffect, useState } from "react";
import { getStartupFit, type StartupFitList, type StartupFitUnit, type StartupGrade, type StartupReason } from "@/lib/api";
import "./StartupFitPanel.css";

const GRADE_UI: Record<StartupGrade, { icon: string; short: string }> = {
  A1: { icon: "✓", short: "창업 여력 있음" },
  A2: { icon: "!", short: "창업 가능 · 여력 얇음" },
  B: { icon: "?", short: "조건부 · 확인 필요" },
  C: { icon: "✕", short: "창업 어려움" },
};
const TONE_LABEL: Record<StartupReason["tone"], string> = { hard: "어려움 사유", soft: "확인할 조건", ok: "열림", info: "참고" };

function timeOf(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

export function GradeBadge({ grade, label }: { grade: StartupGrade; label?: string }) {
  return (
    <span className={`sf-grade sf-g-${grade}`}>
      <i aria-hidden="true">{GRADE_UI[grade].icon}</i>{label || GRADE_UI[grade].short}
    </span>
  );
}

function OwnerCell({ u, status }: { u: StartupFitUnit; status: StartupFitList["owner_status"] }) {
  if (status !== "ready") {
    return <span className="sf-owner is-unknown">건물주 등록 {status === "not_ready" ? "확인 준비 중" : "모름"}</span>;
  }
  if (u.owner.length === 0) return <span className="sf-owner">건물주 등록 없음</span>;
  const first = u.owner[0];
  const rent = first.monthly_rent_manwon != null ? ` · 월 ${first.monthly_rent_manwon.toLocaleString("ko-KR")}만원` : "";
  return (
    <a className="sf-owner is-on" href={`#/listing/${encodeURIComponent(first.id)}`}>
      건물주 등록 {u.owner.length}건{first.unit_label ? ` · ${first.unit_label}` : ""}{rent}
    </a>
  );
}

type Load = { key: string; data: StartupFitList | null; failed: boolean };

export default function StartupFitPanel({ districtId, buildingId }: { districtId: string; buildingId: string }) {
  const key = `${districtId}:${buildingId}`;
  const [load, setLoad] = useState<Load | null>(null);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    let alive = true;
    getStartupFit(districtId, { buildingId })
      .then((data) => { if (alive) setLoad({ key, data, failed: false }); })
      .catch(() => { if (alive) setLoad({ key, data: null, failed: true }); });
    return () => { alive = false; };
  }, [districtId, buildingId, key, nonce]);
  // 다른 건물로 옮기면 앞 건물 결과를 그리지 않는다. 「다시 확인」 동안은 앞 결과를 그대로 둔다(틀이 흔들리지 않게).
  const cur = load?.key === key ? load : null;
  const data = cur?.data ?? null;

  return (
    <div className="b-startup" aria-live="polite">
      <div className="b-rec-h">창업 가능 · 건물주 등록<span className="b-rent-badge sf-live">실시간</span></div>
      {!cur ? <div className="b-rec-note">빈 층마다 창업 가능 등급과 건물주 등록을 확인하는 중…</div>
        : cur.failed || !data ? <div className="b-rec-note">확인하지 못했어요 — 이 상권에 층 단위 자료가 없거나 서버가 답하지 않았어요.</div>
        : data.units.length === 0 ? <div className="b-rec-note">이 건물에는 등급을 붙일 빈 층이 없어요.</div>
        : (
          <ul className="sf-list">
            {data.units.map((u, i) => (
              <li key={`${u.id}:${u.certainty}:${i}`} className="sf-item">
                <div className="sf-row">
                  <span className="sf-floor">{u.floor_label}{u.certainty === "probable" && <i title="층 미상 점포가 다른 층에 있으면 빈다"> 추정</i>}</span>
                  <GradeBadge grade={u.grade} label={u.grade_label} />
                  <OwnerCell u={u} status={data.owner_status} />
                </div>
                <details className="sf-why">
                  <summary>이유 {u.reasons.length}가지</summary>
                  <ul>
                    {u.reasons.map((r) => (
                      <li key={r.code} className={`sf-r-${r.tone}`}><b>{TONE_LABEL[r.tone]}</b> {r.text}</li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ul>
        )}
      {data && data.owner_status !== "ready" && <p className="sf-owner-note" role="note">{data.owner_note}</p>}
      {data && <p className="b-rec-note">{data.note}</p>}
      {cur && (
        <p className="sf-when">
          {data ? `확인 ${timeOf(data.computed_at)} · ` : ""}
          <button type="button" className="b-floor-clear" onClick={() => setNonce((n) => n + 1)}>다시 확인</button>
        </p>
      )}
    </div>
  );
}
