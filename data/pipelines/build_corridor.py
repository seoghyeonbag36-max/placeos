"""[Platform·흐름] 파주-고양-서울 흐름 Gold — 고객 유입 흐름 · 지역 연결 · 시너지 후보.

입력: bronze/corridor/*/capital_od_{corridor}.json (data/collectors/capital_od.py)
산출: gold/platform_corridor.json

## 이 산출물이 답하는 세 질문 (2026-10-26 사용자 요청)

1. **고객이 어떻게 이동하나** — 구간(파주·고양·서울) 사이 하루 이동, 마디마다 손님이 어디서
   오는가(같은 동네 · 같은 구간 · 다른 구간 · 흐름 밖), 언제 닿는가(도착 시각), 무엇 하러 오는가
   (이동목적 7종을 출근·귀가·방문 셋으로 묶어).
2. **서로 어떻게 이어지나** — 마디 ↔ 마디의 하루 이동과 평균 이동시간.
3. **지역마다 어떤 시너지** — 위 두 축에서 **측정으로 고른 짝**(아래 `_synergies`). 짝을 고르는
   규칙은 여기 한 곳에 있고, 결과를 약속하지 않는다 — 「이 지역 사람이 하루 N명 저 상권으로
   간다」까지가 측정이고, 그 짝으로 무엇을 해 볼지는 화면이 **가설로** 적는다.

## 마디(node)는 해상도를 따른다 — 경기는 시군구, 서울은 거점

수도권 생활이동은 서울만 행정동으로, 경기·인천은 **시군구로만** 싣는다(capital_od 머리말).
그래서 경기 쪽 마디는 시군구(파주시 · 고양 덕양구 · 일산동구 · 일산서구)이고 각 경기 거점은
자기 점포가 가장 많은 시군구 마디에 속한다. **같은 마디의 거점들은 같은 흐름 값을 공유한다**
— 금촌과 운정이 다른 값을 가진 척하지 않는다(`hub_nodes` 가 그 소속을 밝힌다). 서울 쪽
마디는 거점이고, 거점의 행정동(점포 10% 이상)을 점포 비중으로 가중한다.

## 쓰지 않는 말

- 「동선」 — 원천에 개인 궤적이 없다(출발→도착 집계). 「유입 흐름」으로 쓴다.
- 「쇼핑하러 온다」 — KT 목적 추정에서 쇼핑·관광은 1% 안팎이고 비업무 방문의 대부분은
  「기타」로 잡힌다(2026-10-26 실측). 「기타」를 쇼핑으로 바꿔 부르지 않는다.

실행: python -m data.pipelines.build_corridor
"""
from __future__ import annotations

import datetime as dt
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from data.collectors.common import BRONZE, GOLD
from data.config.corridors import CORRIDORS, OUTER_LABEL, SGG_NAMES
from data.config.page_hubs import ACTIVE_HUBS

OUT = GOLD / "platform_corridor.json"

# 이동목적 묶음 — 화면은 셋으로 읽는다. 등교는 출근 쪽(정해진 시각에 오는 이동)에 둔다.
WORK = ("출근", "등교")
HOME = ("귀가",)
VISIT = ("쇼핑", "관광", "병원", "기타")

# 역할 판정의 여백 — 세 묶음 중 가장 두드러진 것이 흐름 안 마디 중앙값보다 이만큼 높아야
# 그 이름을 붙인다. 넘는 것이 없으면 「혼합」. **계수다** — 실측이 아니라 이름표를 아낄 문턱이고,
# 값은 언제나 숫자와 함께 나간다(이름만 나가지 않는다).
ROLE_MARGIN_PP = 3.0

# 짝 후보의 최소 하루 이동. 이보다 적은 짝은 표본 잡음과 구분하기 어렵다(KT 추정치는 소수점
# 인원까지 나온다 — 한 사람 미만의 짝을 시너지라 부르지 않는다). 계수다.
PAIR_MIN_PER_DAY = 50.0

# 흐름에 붙일 서울 상권 수 — 파주·고양 유입 상위. 화면이 한 번에 읽을 수 있는 길이로 정했다
# (계수다). 나머지 서울 거점도 산출물에는 남는다(on_corridor=False).
SEOUL_ENDS = 12


def _latest(corridor_id: str) -> Path | None:
    found = sorted(BRONZE.glob(f"corridor/*/capital_od_{corridor_id}.json"))
    return found[-1] if found else None


def _share(m: dict, total: float) -> dict:
    return {k: round(v / total * 100, 1) for k, v in m.items()} if total else {}


def _group(purpose: dict) -> dict[str, float]:
    return {"work": sum(purpose.get(k, 0.0) for k in WORK),
            "home": sum(purpose.get(k, 0.0) for k in HOME),
            "visit": sum(purpose.get(k, 0.0) for k in VISIT)}


def _hours(arr_hour: dict) -> dict[str, float]:
    """시각 키를 0~23시로 접는다 — 출퇴근대 HHMM 이 섞여 들어와도 여기서 묶인다."""
    out: dict[str, float] = defaultdict(float)
    for k, v in arr_hour.items():
        h = str(k)[:2]
        if h.isdigit() and 0 <= int(h) <= 23:
            out[h] += v
    return out


def _peaks(arr_hour: dict, n: int = 3) -> list[int]:
    hrs = _hours(arr_hour)
    return [int(h) for h, _ in sorted(hrs.items(), key=lambda kv: -kv[1])[:n]]


def _hour_share(arr_hour: dict) -> list[float]:
    hrs = _hours(arr_hour)
    tot = sum(hrs.values())
    return [round(hrs.get(f"{h:02d}", 0.0) / tot * 100, 2) if tot else 0.0 for h in range(24)]


def _adong_names() -> dict[str, str]:
    """행정동 코드 → 이름. 거점 점포(상가정보)가 들고 있는 이름을 쓴다(외부 호출 0)."""
    names: dict[str, str] = {}
    for slug in ACTIVE_HUBS:
        files = sorted((BRONZE / slug).glob("*/stores_raw.json"))
        if not files:
            continue
        rows = json.loads(files[-1].read_text(encoding="utf-8"))
        for x in rows if isinstance(rows, list) else rows.get("items", []):
            cd, nm = x.get("adongCd"), x.get("adongNm")
            if cd and nm:
                names.setdefault(str(cd), str(nm))
    return names


def _day_kinds(days: list[str]) -> dict[str, int]:
    wk = sum(1 for d in days if dt.datetime.strptime(d, "%Y%m%d").weekday() < 5)
    return {"weekday": wk, "weekend": len(days) - wk}


def _nodes(od: dict, seg_keys: list[str], names: dict[str, str]) -> tuple[dict, dict]:
    """마디와 거점→마디 소속. 경기 거점은 점포가 가장 많은 시군구 마디에 붙는다."""
    nodes: dict[str, dict] = {}
    hub_nodes: dict[str, str] = {}
    for slug, units in sorted(od["hub_adongs"].items()):
        hub = ACTIVE_HUBS.get(slug)
        if hub is None or hub.city not in seg_keys or not units:
            continue
        levels = {od.get("unit_level", {}).get(cd, "adong") for cd in units}
        if levels == {"adong"}:
            nodes[slug] = {"id": slug, "kind": "hub", "segment": hub.city, "name": hub.name,
                           "units": {cd: {"name": names.get(cd, ""), "weight": w} for cd, w in units.items()},
                           "hubs": [slug]}
            hub_nodes[slug] = slug
            continue
        cd = max(units, key=units.get)          # 주 시군구
        nid = f"sgg:{cd}"
        node = nodes.setdefault(nid, {"id": nid, "kind": "sgg", "segment": hub.city,
                                      "name": SGG_NAMES.get(cd[:5], cd),
                                      "units": {cd: {"name": SGG_NAMES.get(cd[:5], cd), "weight": 1.0}},
                                      "hubs": []})
        node["hubs"].append(slug)
        hub_nodes[slug] = nid
    return nodes, hub_nodes


def _profile(node: dict, od: dict, n_days: int) -> dict | None:
    """마디 하나의 유입 구성 — 단위 비중으로 가중한 구성비."""
    rows = [(cd, u["weight"], od["adong_in"].get(cd)) for cd, u in node["units"].items()]
    rows = [(cd, w, a) for cd, w, a in rows if a and a["total"] > 0]
    if not rows:
        return None
    wsum = sum(w for _, w, _ in rows)
    src, purpose, hours = defaultdict(float), defaultdict(float), defaultdict(float)
    from_seg_per_day = defaultdict(float)
    for _, w, a in rows:
        t = a["total"]
        for k, v in a["from_seg"].items():
            src[k] += w / wsum * v / t
            from_seg_per_day[k] += v / n_days
        for k, v in a["purpose"].items():
            purpose[k] += w / wsum * v / t
        for k, v in _hours(a["arr_hour"]).items():
            hours[k] += w / wsum * v / t
    seg_key = node["segment"]
    inflow = {"same_dong": src.get("self", 0.0), "same_segment": src.get(seg_key, 0.0)}
    for k, v in src.items():
        if k not in OUTER_LABEL and k not in ("self", seg_key):
            inflow[k] = v
    inflow["outer"] = sum(v for k, v in src.items() if k in OUTER_LABEL)
    g = _group(purpose)
    return {
        "arrivals_per_day": round(sum(a["total"] for _, _, a in rows) / n_days, 1),
        "from_segment_per_day": {k: round(v, 1) for k, v in sorted(from_seg_per_day.items(),
                                                                    key=lambda kv: -kv[1])},
        "inflow_share": {k: round(v * 100, 1) for k, v in inflow.items()},
        "purpose_share": {k: round(v * 100, 1) for k, v in sorted(purpose.items(), key=lambda kv: -kv[1])},
        "purpose_group_share": {k: round(v * 100, 1) for k, v in g.items()},
        "arr_hour_share": [round(hours.get(f"{h:02d}", 0.0) * 100, 2) for h in range(24)],
        "peak_hours": [int(h) for h, _ in sorted(hours.items(), key=lambda kv: -kv[1])[:3]],
        # 같은 동네·같은 구간 밖에서 온 몫 — 다른 구간 + 흐름 밖
        "external_share": round((1 - inflow["same_dong"] - inflow["same_segment"]) * 100, 1),
    }


def _assign_roles(nodes: list[dict]) -> None:
    """세 묶음(출근·귀가·방문) 중 흐름 안 마디 중앙값보다 가장 크게 높은 것을 역할로 붙인다."""
    med = {k: st.median(n["purpose_group_share"][k] for n in nodes) for k in ("work", "home", "visit")}
    label = {"work": "출근형", "home": "주거형", "visit": "방문형"}
    for n in nodes:
        dev = {k: round(n["purpose_group_share"][k] - med[k], 1) for k in med}
        k, v = max(dev.items(), key=lambda kv: kv[1])
        n["role"] = {"kind": label[k] if v >= ROLE_MARGIN_PP else "혼합",
                     "deviation_pp": dev, "median_share": {x: round(y, 1) for x, y in med.items()},
                     "margin_pp": ROLE_MARGIN_PP}


def _pairs(nodes: dict[str, dict], od: dict, n_days: int) -> dict[tuple[str, str], dict]:
    """마디 A → 마디 B 하루 이동(단위 기준 합).

    **구간을 넘는 짝과 경기 안의 짝만** 만든다. 서울 ↔ 서울 짝은 이 흐름의 질문(파주·고양·
    서울이 어떻게 이어지나)이 아니고, 81거점끼리면 수천 쌍이라 산출물만 불린다.
    """
    pair = od["adong_pair"]
    out: dict[tuple[str, str], dict] = {}
    for a, na in nodes.items():
        for b, nb in nodes.items():
            if a == b or (na["segment"] == "seoul" and nb["segment"] == "seoul"):
                continue
            tot, msum = 0.0, 0.0
            purpose, hours = defaultdict(float), defaultdict(float)
            for oa in na["units"]:
                for db in nb["units"]:
                    if oa == db:
                        continue        # 같은 단위 안 이동은 마디 사이 흐름이 아니다
                    p = pair.get(f"{oa}|{db}")
                    if not p:
                        continue
                    tot += p["total"]
                    for k, v in p["purpose"].items():
                        purpose[k] += v
                    for k, v in _hours(p.get("arr_hour") or {}).items():
                        hours[k] += v
                    if p.get("avg_min") is not None:
                        msum += p["avg_min"] * p["total"]
            if tot / n_days < PAIR_MIN_PER_DAY:
                continue
            g = _group(purpose)
            out[(a, b)] = {
                "from": a, "to": b,
                "per_day": round(tot / n_days, 1),
                "visit_per_day": round(g["visit"] / n_days, 1),
                "work_per_day": round(g["work"] / n_days, 1),
                "home_per_day": round(g["home"] / n_days, 1),
                "purpose_group_share": _share(g, tot),
                "peak_hours": [int(h) for h, _ in sorted(hours.items(), key=lambda kv: -kv[1])[:3]],
                "avg_min": round(msum / tot, 1) if tot else None,
            }
    return out


def _synergies(nodes: dict[str, dict], pairs: dict) -> list[dict]:
    """측정으로 고른 짝 — **경기 마디마다 종류별로 하나씩**. 규칙 밖의 짝은 만들지 않는다.

    · visit_link  이 경기 마디 사람들이 **방문**(기타·쇼핑·관광·병원)으로 가장 많이 가는 서울 거점.
                  서울에서 작게 확인하고, 그 손님이 사는 이 지역에 자리를 잡는 가설의 근거다.
    · commute     이 경기 마디 사람들이 **출근·등교**로 가장 많이 가는 서울 거점 — 출퇴근 시간대 손님.
    · inbound     이 경기 마디로 **방문**하러 가장 많이 오는 서울 거점 — 서울에서 오는 손님.
    · local_belt  이 경기 마디와 양방향 이동이 가장 많은 **다른 시**의 경기 마디(파주↔고양) — 한 생활권.

    각 짝은 측정값(하루 이동·목적 구성·도착 시각·평균 이동시간)만 싣는다. 무엇을 해 볼지는
    화면이 가설로 적는다 — 이 함수는 결과를 약속하지 않는다.
    """
    def seg(s):
        return nodes[s]["segment"]

    out: list[dict] = []
    for g in sorted(s for s in nodes if seg(s) != "seoul"):
        to_seoul = [p for (a, b), p in pairs.items() if a == g and seg(b) == "seoul"]
        from_seoul = [p for (a, b), p in pairs.items() if b == g and seg(a) == "seoul"]
        for kind, cands, key in (("visit_link", to_seoul, "visit_per_day"),
                                 ("commute", to_seoul, "work_per_day"),
                                 ("inbound", from_seoul, "visit_per_day")):
            cands = [p for p in cands if p[key] > 0]
            if cands:
                p = max(cands, key=lambda p: p[key])
                out.append({"kind": kind, "node": g, **p, "basis": key, "value": p[key]})
        belt = []
        for (a, b), p in pairs.items():
            if a == g and seg(b) not in ("seoul", seg(g)):
                back = pairs.get((b, a), {})
                belt.append({**p, "back_per_day": back.get("per_day", 0.0),
                             "per_day_both": round(p["per_day"] + back.get("per_day", 0.0), 1)})
        if belt:
            p = max(belt, key=lambda p: p["per_day_both"])
            out.append({"kind": "local_belt", "node": g, **p, "basis": "per_day_both",
                        "value": p["per_day_both"]})
    return out


def build(corridor_id: str = "paju-goyang-seoul") -> dict:
    cor = CORRIDORS[corridor_id]
    src = _latest(corridor_id)
    if src is None:
        raise SystemExit("[corridor] bronze 없음 — python -m data.collectors.capital_od --days …")
    od = json.loads(src.read_text(encoding="utf-8"))
    n = od["n_days"]
    seg_keys = [s.key for s in cor.segments]

    # 구간 사이 연결(같은 구간 포함)
    links = []
    for a in seg_keys:
        for b in seg_keys:
            v = od["city_od"].get(f"{a}|{b}")
            if not v:
                continue
            g = _group(v["purpose"])
            links.append({"from": a, "to": b, "per_day": round(v["total"] / n, 1),
                          "avg_min": v["avg_min"], "avg_km": v["avg_km"],
                          "purpose_group_share": _share(g, v["total"]),
                          "arr_hour_share": _hour_share(v["arr_hour"]),
                          "peak_hours": _peaks(v["arr_hour"])})
    outer = {s: {"in_per_day": {OUTER_LABEL[g]: round(od["city_od"].get(f"{g}|{s}", {}).get("total", 0.0) / n, 1)
                                for g in OUTER_LABEL},
                 "out_per_day": {OUTER_LABEL[g]: round(od["city_od"].get(f"{s}|{g}", {}).get("total", 0.0) / n, 1)
                                 for g in OUTER_LABEL}}
             for s in seg_keys}

    nodes, hub_nodes = _nodes(od, seg_keys, _adong_names())
    for nid in list(nodes):
        prof = _profile(nodes[nid], od, n)
        if prof is None:
            nodes.pop(nid)
            continue
        nodes[nid].update(prof)
    hub_nodes = {s: nid for s, nid in hub_nodes.items() if nid in nodes}
    _assign_roles(list(nodes.values()))

    # 서울 쪽 끝 — 파주·고양에서 오는 하루 유입으로 순위를 매긴다. 흐름에 붙일 서울 상권을
    # 사람이 고르지 않고 **이동이 고른다**(상위 SEOUL_ENDS 곳에 on_corridor 표시).
    def from_gg(nd):
        fs = nd["from_segment_per_day"]
        return fs.get("paju", 0.0) + fs.get("goyang", 0.0)

    for nd in nodes.values():
        nd["from_gyeonggi_per_day"] = round(from_gg(nd), 1)
    seoul_rank = sorted((nd for nd in nodes.values() if nd["segment"] == "seoul"), key=lambda nd: -from_gg(nd))
    for i, nd in enumerate(seoul_rank):
        nd["corridor_rank"], nd["on_corridor"] = i + 1, i < SEOUL_ENDS
    for nd in nodes.values():
        if nd["segment"] != "seoul":
            nd["corridor_rank"], nd["on_corridor"] = None, True

    pairs = _pairs(nodes, od, n)
    for nid, nd in nodes.items():
        nd["top_destinations"] = sorted((p for (a, _), p in pairs.items() if a == nid),
                                        key=lambda p: -p["per_day"])[:5]
        nd["top_origins"] = sorted((p for (_, b), p in pairs.items() if b == nid),
                                   key=lambda p: -p["per_day"])[:5]
    synergies = _synergies(nodes, pairs)

    # 흐름에 안 붙은 서울 거점은 순위를 매기는 데 쓴 값만 남긴다 — 화면은 붙은 마디만 그리고,
    # 81거점 전부의 24시간 곡선·짝을 실으면 산출물만 커진다(배포 이미지에 실리는 파일이다).
    keep = {"id", "kind", "segment", "name", "hubs", "arrivals_per_day", "from_gyeonggi_per_day",
            "corridor_rank", "on_corridor", "role"}
    for nd in nodes.values():
        if not nd["on_corridor"]:
            for k in [k for k in nd if k not in keep]:
                nd.pop(k)
            nd["role"] = {"kind": nd["role"]["kind"]}
    on = {nid for nid, nd in nodes.items() if nd["on_corridor"]}
    pairs = {k: p for k, p in pairs.items() if k[0] in on and k[1] in on}

    order = {k: i for i, k in enumerate(seg_keys)}
    return {
        "id": cor.id, "name": cor.name, "note": cor.note,
        "segments": [{"key": s.key, "name": s.name} for s in cor.segments],
        "period": {"days": od["days"], "n_days": n, **_day_kinds(od["days"])},
        "source": od["source"], "dataset": od["dataset"],
        "resolution": {"seoul": "adong", "gyeonggi": "sgg"},
        "caveats": [
            "출발 → 도착 집계다. 한 사람의 동선이 아니다.",
            "인원은 KT 통신 기반 추정치의 일평균이다(기간 합계 ÷ 일수).",
            "서울은 행정동, 파주·고양은 시군구 단위로만 실린다 — 같은 시군구의 거점은 같은 흐름 값을 쓴다.",
            "서울 거점 값은 거점이 걸친 행정동 기준이라 거점 손님 수보다 넓다.",
            "이동목적 「기타」에 비업무 방문 대부분이 들어간다. 쇼핑으로 바꿔 부르지 않는다.",
        ],
        "links": links,
        "outer": outer,
        "nodes": sorted(nodes.values(), key=lambda nd: (order[nd["segment"]], nd.get("corridor_rank") or 0,
                                                          nd["name"])),
        "hub_nodes": hub_nodes,
        "pairs": sorted(pairs.values(), key=lambda p: -p["per_day"]),
        "synergies": synergies,
        "params": {"role_margin_pp": ROLE_MARGIN_PP, "pair_min_per_day": PAIR_MIN_PER_DAY,
                   "seoul_ends": SEOUL_ENDS},
        "built_from": str(src.relative_to(BRONZE.parent)).replace("\\", "/"),
    }


def main() -> None:
    corridors = {cid: build(cid) for cid in CORRIDORS}
    OUT.write_text(json.dumps({"corridors": corridors}, ensure_ascii=False, indent=1), encoding="utf-8")
    for cid, c in corridors.items():
        gg = [nd for nd in c["nodes"] if nd["segment"] != "seoul"]
        print(f"[corridor:{cid}] 마디 {len(c['nodes'])}(경기 시군구 {len(gg)}) · 짝 {len(c['pairs'])} · "
              f"시너지 후보 {len(c['synergies'])} · {c['period']['n_days']}일 → {OUT.relative_to(GOLD.parent)}")


if __name__ == "__main__":
    main()
