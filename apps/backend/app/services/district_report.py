"""검증 리포트 — `GET /commercial-districts/{id}/report`.

칸마다 `{status, source, as_of, note, data}` 다. 비는 칸도 칸째 내보내 화면이 사유를 적게 한다. 출처 문구는 여기서 사람 말로
쓴다 — 서비스 응답의 `source` 에는 내부 파일 경로가 섞여 있어 그대로 넘기지 않는다. `list_summaries` 는 부르지 않는다(느리다).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services import (building_twin, building_vacancy, business_fit,
                          events, floor_vacancy, footfall_layer, industry_recommend, nearby_stores,
                          platform_profile, posting, posting_inputs, posting_revenue, rent_layer, rone_history,
                          vacant_inventory)
from app.services import districts as svc
from app.services.hub_outlines import type_of

logger = logging.getLogger("spaceos.report")

_SEOUL_ONLY = "서울만 제공 — {city} 상권에는 이 원천이 없어요."
_TOP_EVENTS = 30
_INDUSTRY_TOP = 3


def _ok(source: str, data: Any, as_of: str | None = None, note: str | None = None) -> dict:
    return {"status": "ok", "source": source, "as_of": as_of, "note": note, "data": data}


def _no(note: str, source: str | None = None) -> dict:
    return {"status": "unavailable", "source": source, "as_of": None, "note": note, "data": None}


def _seoul_only(d: dict) -> dict:
    return _no(_SEOUL_ONLY.format(city=svc.page_city(d).short))


def _overview(d: dict) -> dict:
    s = svc.get_summary(d["id"]) or {}
    return _ok("건축물대장 · 소상공인 상가정보 · 사람이 붙인 상권 유형(서울)", {
        "id": d["id"], "name": d.get("name"), "gu": d.get("gu"), "city": s.get("city"), "city_name": s.get("city_name"),
        **type_of(d["id"]),
        "archetype": (platform_profile.identity(d["id"]) or {}).get("archetype"),
        "store_count": s.get("store_count"), "building_count": s.get("building_count"),
        "caveat": s.get("caveat"),
    }, as_of=(floor_vacancy.load(d["id"]) or {}).get("built_at"))


def _industry(d: dict, industry: str | None) -> dict:
    inside = business_fit.industries_in_district(d["id"])
    if inside is None:
        return _no("이 상권의 업종 자료가 없어요.")
    rows = inside["rows"]
    ranked = [r for r in rows if r.get("fit") is not None]
    keep = ("key", "label", "fit", "fit_rank", "same_n", "same_share")
    data: dict[str, Any] = {
        "top": [{k: r.get(k) for k in keep} for r in ranked[:_INDUSTRY_TOP]],
        # 「피해야 한다」가 아니라 이 상권에 잘 안 모이는 쪽이다.
        "bottom": [{k: r.get(k) for k in keep} for r in ranked[-2:]] if len(ranked) > _INDUSTRY_TOP else [],
        "composition": [{k: r.get(k) for k in ("key", "label", "same_n", "same_share")} for r in rows],
        "sample_n": inside.get("sample_n"),
    }
    if industry:
        fit = business_fit.fit_by_district(industry)
        row = next((r for r in (fit or {}).get("districts") or [] if r["district_id"] == d["id"]), None)
        data["selected"] = {
            "key": industry, "label": (fit or {}).get("industry", {}).get("label"),
            "model_covered": bool((fit or {}).get("model_covered")),
            "unavailable_reason": (fit or {}).get("fit_unavailable_reason"),
            **({k: row.get(k) for k in ("fit", "fit_rank", "rank_n", "rank_group_name", "same_n", "sample_n",
                                         "same_share", "rent_1f_per_pyeong")} if row else {}),
        }
    return _ok("업종 모델(이미 모여 있는 정도) · 카카오 플레이스 표본", data,
               note="입지 적합도는 이미 모여 있는 정도이고 매출·생존이 아닙니다. 순위는 묶음(서울·경기·광주)마다 따로 셉니다.")


def _population(d: dict) -> dict:
    ident = platform_profile.identity(d["id"]) or {}
    demand = ident.get("demand") or {}
    wd = footfall_layer.hourly_profile(d["id"], "weekday")
    if not demand and not wd:
        return _seoul_only(d)
    we = footfall_layer.hourly_profile(d["id"], "weekend")
    density = footfall_layer.density_heatmap(d["id"]) or {}
    return _ok("서울시 상권분석(TRDAR) · 생활인구", {
        "bands": [{k: b.get(k) for k in ("band", "label", "flpop")} for b in demand.get("bands") or []],
        "peak_band": demand.get("peak_band"),
        "hourly_weekday": (wd or {}).get("hours"), "hourly_weekend": (we or {}).get("hours"),
        "peak_weekday": (wd or {}).get("peak"), "peak_weekend": (we or {}).get("peak"),
        "ages": demand.get("ages") or [], "female_share": demand.get("female_share"),
        "weekend_share": demand.get("weekend_flpop"),
        "density": {"unit": density.get("unit"), "min": density.get("min"), "max": density.get("max")} if density else None,
    }, as_of=(wd or {}).get("as_of"), note=(wd or {}).get("note"))


def _sales(d: dict) -> dict:
    demand = (platform_profile.identity(d["id"]) or {}).get("demand") or {}
    tiers = {t: posting_revenue.per_pyeong(d["id"], t) for t in svc.TIER}
    if not svc.page_city(d).has_trdar or not demand:
        return _seoul_only(d)
    return _ok("서울시 상권분석 추정매출", {
        "bands": [{k: b.get(k) for k in ("band", "label", "selng", "gap")} for b in demand.get("bands") or []],
        "gap_band": demand.get("gap_band"),
        "weekend_share": demand.get("weekend_selng"),
        "tier_per_pyeong_manwon": tiers,
    }, note="추정매출이고 개별 점포 실적이 아닙니다.")


def _openclose(d: dict) -> dict:
    demand = (platform_profile.identity(d["id"]) or {}).get("demand") or {}
    if not svc.page_city(d).has_trdar or not demand:
        return _seoul_only(d)
    return _ok("서울시 상권분석", {
        "open_rate": demand.get("open_rate"), "close_rate": demand.get("close_rate"),
        "franchise_share": demand.get("franchise_share"),
    })


def _building_classes(district_id: str) -> dict:
    fc = building_vacancy.building_vacancy_geojson(district_id) or {}
    counts = {"confirmed": 0, "probable": 0, "full": 0, "unknown": 0}
    for f in fc.get("features") or []:
        counts[(f.get("properties") or {}).get("vac_class") or "unknown"] += 1
    return counts


def _vacancy(d: dict) -> dict:
    s = svc.get_summary(d["id"]) or {}
    inv = floor_vacancy.load(d["id"]) or {}
    hist = rone_history.history(d["id"]) or {}
    return _ok("건축물대장 · 상가정보 점포 대조 · 한국부동산원 R-ONE", {
        "building_classes": _building_classes(d["id"]),
        "vacancy_rate": s.get("vacancy_rate"), "vacancy_withheld": s.get("vacancy_withheld"),
        "floor_units": inv.get("counts") or {},
        "rone_anchor_pct": s.get("anchor_pct"), "aligned_vacancy_pct": s.get("aligned_vacancy_pct"),
        "aligned_gap_pp": s.get("aligned_gap_pp"),
        "history": {k: hist.get(k) for k in ("quarters", "vacancy_mid_pct", "vacancy_small_pct", "source",
                                             "shared_from")} if hist else None,
    }, as_of=inv.get("built_at"),
        note="공실은 스냅샷이고 현장 미확인입니다. 빈 층 판정의 정확도는 검정하지 못했습니다(현장 라벨 0/458).")


def _rent(d: dict) -> dict:
    rent = rent_layer.rent_heatmap(d["id"])
    hist = rone_history.history(d["id"]) or {}
    if rent is None:
        return _no("이 상권은 R-ONE 임대 표본이 없어요. 이웃 값으로 채우지 않습니다.", "한국부동산원 R-ONE")
    return _ok("한국부동산원 R-ONE × 층 계수(추정)", {
        "floors": rent["floors"], "base_rent_per_pyeong": rent["base_rent_per_pyeong"],
        "rent_source": rent["rent_source"], "shared_from": hist.get("shared_from"),
        "excludes": rent["excludes"], "monthly_min": rent["monthly_min"], "monthly_max": rent["monthly_max"],
        "history": {"quarters": hist.get("quarters"), "rent_per_pyeong_manwon": hist.get("rent_per_pyeong_manwon")}
        if hist else None,
    }, as_of=rent["quarter"], note=rent["note"])


def _find_site(district_id: str, unit_id: str | None, building_id: str | None) -> dict | None:
    """선택 자리 → {lat,lng,unit,building_id}. 고르지 않았거나 모르면 None."""
    if unit_id and unit_id.startswith("vfu-"):
        u = next((x for x in (floor_vacancy.load(district_id) or {}).get("units") or [] if x.get("id") == unit_id), None)
        if u:
            return {"lat": u["lat"], "lng": u["lng"], "unit": u, "building_id": u.get("building_id"), "kind": "floor"}
    if unit_id and unit_id.startswith("vu-"):
        u = next((x for x in vacant_inventory.units(district_id) if x.get("id") == unit_id), None)
        if u:
            return {"lat": u["lat"], "lng": u["lng"], "unit": u, "building_id": unit_id[3:], "kind": "building"}
    if building_id:
        t = building_twin.twin(district_id, building_id)
        if t:
            return {"lat": t["lat"], "lng": t["lng"], "unit": None, "building_id": t["id"], "kind": "lot", "twin": t}
    return None


def _site(d: dict, site: dict | None) -> dict:
    if site is None:
        return _no("자리를 고르지 않았어요.")
    bid = site.get("building_id") or ""
    twin = site.get("twin") or (building_twin.twin(d["id"], bid) if bid else None)
    unit = site.get("unit") or {}
    floors = (twin or {}).get("floors") or []
    picked = next((f for f in floors if f.get("unit_id") == unit.get("id")), None) if unit else None
    rec = industry_recommend.recommend(d["id"], site["lat"], site["lng"]) or {}
    hist = (twin or {}).get("history") or {}
    return _ok("건축물대장 · 상가정보 점포 대조 · 업종 모델 · 인허가", {
        "kind": site["kind"], "unit_id": unit.get("id"), "building_id": (twin or {}).get("id") or bid,
        "name": (twin or {}).get("name") or unit.get("n"), "road_addr": (twin or {}).get("road_addr"),
        "lat": site["lat"], "lng": site["lng"],
        "floor": (picked or {}).get("label") or unit.get("floor_label") or unit.get("floor"),
        "status": (picked or {}).get("status"), "vac_class": (twin or {}).get("vac_class"),
        "area_m2": (picked or {}).get("area_m2") or unit.get("area_m2") or unit.get("com_area_m2"),
        "area_py": unit.get("area"),
        "rent_est_manwon": (picked or {}).get("rent_est_manwon"),
        "representative_industry": (twin or {}).get("representative_industry"),
        "model_top3": rec.get("recommendations") or [], "matched_distance_m": rec.get("matched_distance_m"),
        "history_summary": hist.get("summary"), "history_source": hist.get("source"),
    }, note="업종 점수는 그 자리에서 가까운 모델 노드의 상위 3개이고, 이력은 지번 단위라 층을 모릅니다.")


def _competition(d: dict, site: dict | None, industry: str | None) -> dict:
    if site is None:
        return _no("자리를 고르지 않아 반경 집계를 내지 않았어요.")
    out = nearby_stores.nearby(d["id"], site["lat"], site["lng"], 100, industry, None,
                               building_id=site.get("building_id"))
    if out is None:
        return _no("이 상권의 점포 자료가 없어요.")
    return _ok("소상공인 상가정보", {
        "basis": out["basis"], "by_radius": out["by_radius"], "relative": out["relative"],
        "nearest_same": out["nearest_same"], "chains": out["chains"][:10], "floor_split": out["floor_split"],
        "edge_truncated": out["edge_truncated"],
    }, as_of=out["store_as_of"], note=" ".join(out["notes"][:2]))


def _posting(d: dict, unit_id: str | None) -> dict:
    # 칸이 비어 보이지 않게 대표 유닛으로 내지 않는다 — 고른 자리의 답만 그 자리의 답이다.
    if not unit_id:
        reason = svc.payback_unavailable_reason(d["id"])
        return _no(reason or "자리를 고르지 않아 계산하지 않았어요.")
    sim = posting.simulate(d["id"], unit_id)
    if sim is None:
        return _no("이 자리를 찾지 못했어요.")
    if sim.get("source") == "unavailable":
        return _no(sim.get("unavailable_reason") or "계산할 재료가 없어요.")
    return _ok("서울시 상권분석 추정매출 · KOSIS 비용률 · R-ONE 임대(투자비는 계수 추정)", {
        "scenarios": sim["scenarios"], "inputs_source": sim.get("inputs_source"),
        "unviable_note": sim.get("unviable_note"),
    }, as_of=sim.get("inputs_quarter"), note="투자비는 계수 추정입니다. 실제 견적으로 바꿔 보세요.")


def _events(d: dict) -> dict:
    # 2026-11-07 — 전국 행사 Gold(문화포털·TourAPI)가 덮는 서울 밖 거점도 행사를 싣는다.
    if not svc.page_city(d).has_city_events and not events.national_covers(d["id"]):
        return _seoul_only(d)
    rows = events.for_district(d["id"])
    if rows is None:
        return _no("행사 자료가 적재되지 않았어요.")
    keep = ("n", "category", "when", "place", "org", "fee", "target", "link", "lat", "lng", "distance_m", "src")
    used = {e.get("src") for e in rows}
    metas = [m for m in events.sources_meta() if m["id"] in used] or events.sources_meta()
    source = " · ".join(dict.fromkeys(m["name"] for m in metas)) or "공공 행사 자료"
    as_of = max((m["as_of"] for m in metas if m.get("as_of")), default=None)
    # 끝난 행사는 서빙 시점(오늘)에 빠진다 — 예전 안내 「수집 기준일 뒤에 끝난 행사가 섞여 있을 수 있어요」는 더는 맞지 않다.
    return _ok(source,
               {"n": len(rows), "items": [{k: e.get(k) for k in keep} for e in rows[:_TOP_EVENTS]]},
               as_of=as_of, note="오늘 기준으로 끝난 행사는 뺐어요. 일정·참가 조건은 원문에서 다시 확인하세요.")


_SECTIONS = ("overview", "industry", "population", "sales", "openclose", "vacancy", "rent", "site", "competition",
             "posting", "events")


def report(district_id: str, industry: str | None = None, unit_id: str | None = None,
           building_id: str | None = None) -> dict | None:
    """리포트 한 벌. 거점을 모르면 None · 모르는 업종은 ValueError(→ 422)."""
    d = svc.PAGES_BY_ID.get(district_id)
    if d is None:
        return None
    if industry is not None and business_fit.get(industry) is None:
        raise ValueError("알 수 없는 업종")
    site = _find_site(district_id, unit_id, building_id)
    builders = {
        "overview": lambda: _overview(d),
        "industry": lambda: _industry(d, industry),
        "population": lambda: _population(d),
        "sales": lambda: _sales(d),
        "openclose": lambda: _openclose(d),
        "vacancy": lambda: _vacancy(d),
        "rent": lambda: _rent(d),
        "site": lambda: _site(d, site),
        "competition": lambda: _competition(d, site, industry),
        "posting": lambda: _posting(d, unit_id if site else None),
        "events": lambda: _events(d),
    }
    sections: dict[str, dict] = {}
    for name in _SECTIONS:
        try:
            sections[name] = builders[name]()
        except Exception:  # noqa: BLE001 — 한 칸의 실패가 리포트 전체를 500 으로 만들지 않는다. 칸째 사유를 남긴다
            logger.exception("report section failed: %s/%s", district_id, name)
            sections[name] = _no("이 칸을 만들지 못했어요.")
    return {"district_id": district_id, "selected_industry": industry, "unit_id": unit_id,
            "building_id": building_id, **sections}
