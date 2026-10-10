// Platform 점포 후보 탐색. 데이터가 없는 사진·영업 여부는 채우지 않는다.
import { useEffect, useMemo, useRef, useState } from "react";
import { getBenchmarkPlaces, listBenchmarkIndustries, type BenchmarkIndustry, type BenchmarkPlaces } from "@/lib/api";
import { useFitMap, useMapMarkers } from "@/components/useMapMarkers";
import { mapLabelHTML } from "@/design/components/MapMarkerPin";
import { colors } from "@/design/tokens/colors";
import { space } from "@/design/tokens/layout";
import "./BenchmarkExplorer.css";

export default function BenchmarkExplorer({ districtId, defaultIndustry = "" }: {
  districtId: string; defaultIndustry?: string;
}) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<BenchmarkIndustry[] | null>(null);
  const [industry, setIndustry] = useState(defaultIndustry);
  const [result, setResult] = useState<BenchmarkPlaces | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    return () => { generation.current += 1; };
  }, [districtId, industry]);
  useEffect(() => {
    if (!open || options) return;
    let live = true;
    listBenchmarkIndustries().then((rows) => { if (live) setOptions(rows); })
      .catch(() => { if (live) setError("검색 업종 목록을 불러오지 못했습니다. 닫았다 다시 열어 주세요."); });
    return () => { live = false; };
  }, [open, options]);
  const current = result?.district_id === districtId && result.industry_key === industry ? result : null;
  const places = useMemo(() => open ? current?.places ?? [] : [], [open, current]);
  const selected = places.find((p) => p.id === selectedId);
  const markers = useMemo(() => places.map((p) => ({ id: p.id, lat: p.lat, lng: p.lng,
    html: mapLabelHTML({ text: p.name, sub: "벤치마킹 후보", color: colors.brand.primary, active: p.id === selectedId }),
    zIndex: p.id === selectedId ? 110 : 90,
  })), [places, selectedId]);
  useMapMarkers(markers, setSelectedId);
  useFitMap(open && current ? `${districtId}:${industry}:${current.queried_at}:${selectedId ?? "all"}` : null,
    selected ? [selected] : places, null);
  async function search() {
    const request = ++generation.current;
    setBusy(true); setError(null); setResult(null); setSelectedId(null);
    try {
      const response = await getBenchmarkPlaces(districtId, industry);
      if (generation.current === request) setResult(response);
    } catch (e) {
      if (generation.current === request) setError(e instanceof Error ? e.message : "점포 검색 실패");
    } finally {
      if (generation.current === request) setBusy(false);
    }
  }
  return <section className="benchmark-explorer" aria-label="벤치마킹 가게 찾기" style={{ marginBlock: space[4], padding: space[4] }}>
    <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)}>벤치마킹 가게 찾기</button>
    {open && <>
      <p>선택한 Platform의 기존 공실 측정 범위 안에서 찾습니다. 지도 선은 공식 상권 경계가 아닙니다.</p>
      <label>벤치마킹 업종<select aria-label="벤치마킹 업종" value={industry} disabled={!options} style={{ margin: space[2] }}
        onChange={(e) => { generation.current += 1; setIndustry(e.target.value); setResult(null); setSelectedId(null); setError(null); setBusy(false); }}>
        <option value="">업종 선택</option>
        {industry && options && !options.some((o) => o.key === industry) && <option value={industry}>선택한 업종 · 현재 검색 미지원</option>}
        {options?.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select></label>
      <button type="button" disabled={busy || !options?.some((o) => o.key === industry)} onClick={search}>
        {busy ? "검색 중…" : "후보 검색"}</button>
      {error && <p role="alert">{error}</p>}
      {current && <>
        <p>출처: 카카오 Local · 조회 {new Date(current.queried_at).toLocaleString("ko-KR")}</p>
        <p>{current.note}</p>
        {current.truncated && <p>검색 제한으로 일부 결과만 조회했습니다.</p>}
        {!places.length && <p role="status">측정 범위와 업종 조건에 맞는 검색 후보가 없습니다.</p>}
        <ul aria-label="벤치마킹 후보 목록">{places.map((p) => <li key={p.id} style={{ paddingBlock: space[2] }}>
          <button type="button" aria-pressed={selectedId === p.id} onClick={() => setSelectedId(p.id)}>
            {p.name} · 중심에서 {p.distance_m.toLocaleString()}m
          </button><small>{p.category}</small>
        </li>)}</ul>
        {selected && <article aria-label="선택한 벤치마킹 점포">
          <h3>{selected.name}</h3><p>{selected.category}</p>
          <p>{selected.address || "주소 미제공"}</p><p>전화: {selected.phone || "미제공"}</p>
          <a href={selected.place_url} target="_blank" rel="noopener noreferrer">카카오맵에서 상세 보기 (새 창)</a>
          <p>사진·메뉴·후기·영업시간은 외부 상세 페이지에서 확인하세요.</p>
        </article>}
      </>}
    </>}
  </section>;
}
