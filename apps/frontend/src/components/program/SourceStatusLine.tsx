import type { ProgramSourceStatus } from "@/lib/api";

const WORD: Record<ProgramSourceStatus["status"], string> = { ok: "", no_key: "연결 전", error: "지금 확인할 수 없음" };

/** 원천마다 몇 건을 받았는지, 비었다면 왜 비었는지 — 지난 목록을 최신처럼 보이지 않는다(services/program_sources). */
export default function SourceStatusLine({ sources }: { sources: ProgramSourceStatus[] }) {
  return <ul className="program-sources" aria-label="자료 원천 상태">
    {sources.map((s) => <li key={s.id} data-status={s.status}>
      <b>{s.name}</b> {s.status === "ok" ? `${s.count}건` : WORD[s.status]}
      {s.status !== "ok" && s.note && <small> — {s.note}</small>}
    </li>)}
  </ul>;
}
