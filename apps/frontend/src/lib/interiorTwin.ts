/**
 * 트윈 응답(건물 · 층) → 공실 내부 3D 배치 입력(2026-11-09). 화면(InteriorTwin)과 예시 HTML 이 같은 길을 쓴다.
 * 개략 배치도(`planLayout`)와 같은 입력 — 외곽선 · 층 바닥면적 · 전유부 · 전용 추정 · 주소 도로 전면 · 대장 승강기 · 계단실.
 */
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { interiorLayout, type InteriorLayout, type InteriorStrategy } from "@/lib/interiorLayout";
import { frontRoad, isVacantStatus, planLayout, ringToLocal, windowSpans, type Point, type WindowSpan } from "@/lib/twinGeometry";

/** 이 자리의 층 — 층 매물 id → 층 표기 → 첫 공실 층 → 1층 → 첫 층 */
export function pickFloor(twin: BuildingTwin, unitId?: string | null, floorLabel?: string | null): TwinFloor | null {
  const fs = twin.floors;
  return fs.find((f) => !!unitId && f.unit_id === unitId)
    ?? fs.find((f) => !!floorLabel && (f.label === floorLabel || f.label === `${floorLabel}`.replace(/층$/, "F")))
    ?? fs.find((f) => isVacantStatus(f.status))
    ?? fs.find((f) => f.lv === 1) ?? fs[0] ?? null;
}

export interface InteriorBuild {
  outline: Point[]; windows: WindowSpan[]; frontEdge: [Point, Point] | null; frontName: string | null;
  layout: InteriorLayout;
}

export function buildInterior(twin: BuildingTwin, floor: TwinFloor, opts: { keywords: readonly string[]; industry?: string | null; strategy?: InteriorStrategy | null }): InteriorBuild {
  const outline = ringToLocal(twin.ring, twin.lat, twin.lng);
  const front = frontRoad(outline, twin.roads, twin.road_check?.found ? twin.road_check.name : null, twin.lat, twin.lng);
  const live = twin.ledger_live?.status === "ok" ? twin.ledger_live : null;
  const plan = planLayout(outline, floor.units ?? [], floor.area_m2, {
    front: front?.dir, exclEst: floor.excl_est?.m2 ?? null,
    elevators: live?.elevators ? live.elevators.passenger + live.elevators.emergency : 0,
    stairM2: live?.floors?.[String(floor.lv)]?.stair_m2 ?? null,
    multiStory: twin.floors_above + twin.floors_below > 1,
  });
  const layout = interiorLayout({
    outline, pieces: plan.pieces, frontEdge: plan.frontEdge, angle: plan.angle, lv: floor.lv,
    industry: opts.industry, strategy: opts.strategy, keywords: opts.keywords,
    spaceM2: plan.pieces.some((p) => p.kind === "lease") ? plan.areas.excl : floor.area_m2,
  });
  return { outline, windows: floor.lv > 0 ? windowSpans(outline) : [], frontEdge: plan.frontEdge, frontName: front?.name ?? null, layout };
}
