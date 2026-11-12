import { lazy, Suspense, useEffect, useRef } from "react";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./PpppReport.css";

const PpppReport = lazy(() => import("./PpppReport"));

/** 네 트랙의 작업을 유지한 채 창업자용 요약과 다운로드를 연다. */
export default function AnalysisReportDialog({ districtId, handoff, onClose }: {
  districtId: string; handoff?: ProgramHandoff; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const node = ref.current;
    node?.showModal();
    return () => { node?.close(); opener?.focus(); };
  }, []);
  return <dialog ref={ref} className="analysis-report-dialog" aria-label="상권 분석 보고서"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <button type="button" className="analysis-report-close" onClick={onClose}>보고서 창 닫기</button>
    <Suspense fallback={<p role="status">보고서를 불러오는 중…</p>}>
      <PpppReport districtId={districtId} handoff={handoff} />
    </Suspense>
  </dialog>;
}
