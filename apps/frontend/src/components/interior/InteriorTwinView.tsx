import { useEffect, useMemo, useRef, useState } from "react";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import type { InteriorStrategy } from "@/lib/interiorLayout";
import { buildInterior } from "@/lib/interiorTwin";
import type { InteriorSceneHandle } from "./InteriorScene";
import InteriorPlan2D from "./InteriorPlan2D";
import "./Interior.css";

/**
 * 공실 내부 3D 디지털 트윈(2026-11-09) — 트윈의 개략 배치도 · 공간 정보로 공실 안을 세우고, 키워드대로 가구를 놓는다.
 * three 는 여기서 import 하지 않는다 — 장면은 `InteriorScene` 을 동적으로 불러온다. WebGL 이 안 되면 평면으로 내려간다.
 */
export default function InteriorTwinView({ twin, floor, keywords, industry, strategy, onSummary }: {
  twin: BuildingTwin; floor: TwinFloor; keywords: readonly string[]; industry?: string | null; strategy?: InteriorStrategy | null;
  onSummary?: (lines: string[]) => void;
}) {
  const build = useMemo(() => buildInterior(twin, floor, { keywords, industry, strategy }), [twin, floor, keywords, industry, strategy]);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const handleRef = useRef<InteriorSceneHandle | null>(null);
  const buildRef = useRef(build);
  const [flat, setFlat] = useState(false);
  const [view, setView] = useState<"3d" | "plan">("3d");
  // 장면 만들기 전에 최신 배치를 ref 에 둔다(아래 장면 효과가 읽는다 — 효과는 선언 순서대로 돈다)
  useEffect(() => { buildRef.current = build; }, [build]);

  // 장면은 건물 · 층이 바뀔 때만 새로 만들고, 키워드가 바뀌면 배치만 갈아 끼운다
  useEffect(() => {
    if (flat || view !== "3d" || !hostRef.current || twin.ring.length < 3) return;
    let alive = true;
    const host = hostRef.current;
    const input = () => ({ outline: buildRef.current.outline, layout: buildRef.current.layout, lv: floor.lv, windows: buildRef.current.windows, frontEdge: buildRef.current.frontEdge });
    import("./InteriorScene").then(({ createInteriorScene }) => {
      if (!alive) return;
      try {
        handleRef.current = createInteriorScene(host, input());
        host.dataset.ready = "1";
      } catch { setFlat(true); }
    }).catch(() => { if (alive) setFlat(true); });
    return () => { alive = false; handleRef.current?.dispose(); handleRef.current = null; delete host.dataset.ready; };
  }, [twin, floor, flat, view]);
  const summaryKey = build.layout.summary.join("\n");
  useEffect(() => { onSummary?.(summaryKey ? summaryKey.split("\n") : []); }, [summaryKey, onSummary]);
  useEffect(() => {
    handleRef.current?.setLayout({ outline: build.outline, layout: build.layout, lv: floor.lv, windows: build.windows, frontEdge: build.frontEdge });
  }, [build, floor.lv]);

  const L = build.layout;
  const show3d = !flat && view === "3d";
  return (
    <div className="interior3d">
      <div className="interior3d-bar">
        <span className="interior3d-tag">3D 디지털 트윈 · 규칙 배치 예시 · 실측 도면 아님</span>
        {!flat && <button type="button" aria-pressed={view === "plan"} onClick={() => setView(view === "3d" ? "plan" : "3d")}>{view === "3d" ? "평면 보기" : "3D 보기"}</button>}
        {show3d && <button type="button" onClick={() => handleRef.current?.resetView()}>전체 보기</button>}
      </div>
      {show3d
        ? <div className="interior3d-canvas" ref={hostRef} data-testid="interior-canvas" role="img"
            aria-label={`${twin.name ?? "건물"} ${floor.label} 공실 내부 3D — ${L.summary.join(" · ")}`} />
        : <InteriorPlan2D outline={build.outline} layout={L} />}
      {flat && <p className="interior3d-note">이 브라우저에서 3D 를 그리지 못해 평면으로 보입니다(같은 배치).</p>}
      <ul className="interior3d-summary">{L.summary.map((s) => <li key={s}>{s}</li>)}</ul>
      {L.notes.length > 0 && <ul className="interior3d-notes">{L.notes.map((s) => <li key={s}>{s}</li>)}</ul>}
      <p className="interior3d-note">
        공간: {L.spaceBasis}{build.frontName ? ` · 입구 쪽 ${build.frontName}(도로명주소 × OSM)` : " · 전면 도로를 몰라 긴 변을 앞으로 두었습니다"} ·
        벽 · 창 · 공용 · 계단 · 승강기 자리는 개략입니다. 가구 크기 · 좌석 수 · 통로 폭은 규칙의 예시 값이라 피난 · 접근 · 설비 기준과 실측 도면으로 확인해야 합니다.
      </p>
    </div>
  );
}
