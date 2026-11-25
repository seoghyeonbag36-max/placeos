/**
 * 건물주가 올리는 빈 자리를 **지도의 그 건물에 잇는** 칸(2026-11-22).
 *
 * 건물 id(`building_id`)가 비면 건물주가 올린 층은 Page 의 건물 화면 · 흐름의 자리 상세에서 그 건물과 만나지 못한다 —
 * 주소만 적어 올린 매물은 어느 건물인지 PlaceOS 가 맞춰 주지 않는다(지어내지 않는다). 그래서 건물주가 상권의 건물 목록에서 직접 고른다.
 * 고르면 대장 주소·층 목록을 채워 주고(건물주가 고칠 수 있다), 층마다 대장 층 바닥면적·용도를 참고로 보인다.
 * 건물이 목록에 없으면 비워 두고 주소로 올린다 — 그 경우엔 지도 건물에 안 붙는다고 알린다.
 */
import { useMemo, useState } from "react";
import { getBuildingTwin, getBuildingVacancy, type TwinFloor } from "@/lib/api";
import { useLoad } from "../data";

export interface PickedBuilding {
  id: string; name: string; address: string; lat: number | null; lng: number | null;
  floors: Pick<TwinFloor, "lv" | "label" | "area_m2" | "purps">[];
}

const centroid = (ring: number[][] | undefined): { lat: number; lng: number } | null => {
  if (!ring?.length) return null;
  const n = ring.length;
  return { lng: ring.reduce((a, p) => a + p[0], 0) / n, lat: ring.reduce((a, p) => a + p[1], 0) / n };
};

export default function BuildingPicker({ districtId, picked, onPick, onClear }: {
  districtId: string; picked: PickedBuilding | null; onPick: (b: PickedBuilding) => void; onClear: () => void;
}) {
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const res = useLoad(`direct-buildings:${districtId}`, () => getBuildingVacancy(districtId));
  const buildings = useMemo(() => {
    if (res.status !== "ready") return [];
    const seen = new Set<string>();
    return res.data.features.flatMap((f) => {
      const p = f.properties;
      if (!p?.id || seen.has(p.id)) return [];
      seen.add(p.id);
      return [{ id: p.id, name: p.name || "이름 없는 건물", addr: p.road_addr ?? "", at: centroid(f.geometry?.coordinates?.[0]) }];
    });
  }, [res]);
  const term = q.trim().toLowerCase();
  const shown = term ? buildings.filter((b) => `${b.name} ${b.addr}`.toLowerCase().includes(term)).slice(0, 8) : [];

  const choose = async (b: (typeof buildings)[number]) => {
    setBusyId(b.id);
    setNote(null);
    let floors: PickedBuilding["floors"] = [];
    let address = b.addr;
    try {
      const twin = await getBuildingTwin(b.id, districtId);
      if (!twin) throw new Error("no twin");     // 트윈이 없는 건물 — 건물 이음은 그대로 두고 층만 직접 적게 한다
      floors = twin.floors.map((f) => ({ lv: f.lv, label: f.label, area_m2: f.area_m2, purps: f.purps }));
      address = twin.road_addr || address;
    } catch { setNote("층 목록을 불러오지 못했어요. 층은 직접 적어 주세요."); }
    onPick({ id: b.id, name: b.name, address, lat: b.at?.lat ?? null, lng: b.at?.lng ?? null, floors });
    setBusyId(null);
    setQ("");
  };

  if (picked) {
    return (
      <div className="dr-picked" role="status">
        <p><b>지도의 이 건물에 이어져요</b> · {picked.name}{picked.address ? ` · ${picked.address}` : ""}</p>
        <button type="button" className="fl-btn" onClick={onClear}>다른 건물 고르기</button>
        {note && <p className="fl-source">{note}</p>}
      </div>
    );
  }
  return (
    <div className="dr-picker">
      <label className="dr-field"><span>지도의 건물 찾기(선택)</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="건물 이름이나 도로명 주소의 일부" aria-label="지도의 건물 찾기" />
        <small>고르면 대장 주소와 층 목록을 채워 드려요. 이어 두면 창업자가 지도에서 이 건물을 열었을 때 올린 층이 보여요. 목록에 없으면 비워 두고 주소로 올리세요. 그땐 지도 건물에 붙지 않아요.</small>
      </label>
      {res.status === "loading" && <p className="fl-source" role="status">건물 목록을 불러오는 중…</p>}
      {res.status === "error" && <p className="fl-source">건물 목록을 불러오지 못했어요. 주소로 올려도 돼요.</p>}
      {term && res.status === "ready" && (shown.length === 0
        ? <p className="fl-source">맞는 건물이 없어요.</p>
        : <ul className="dr-picker-list" aria-label="건물 검색 결과">
          {shown.map((b) => (
            <li key={b.id}>
              <button type="button" disabled={busyId !== null} onClick={() => void choose(b)}>
                <b>{b.name}</b>{b.addr ? <small> {b.addr}</small> : null}{busyId === b.id ? <small> · 불러오는 중…</small> : null}
              </button>
            </li>
          ))}
        </ul>)}
    </div>
  );
}
