"""거점 체인 상태 — 한 거점이 등록에서 서빙까지 어디까지 왔는지 **산출물로** 판정한다.

`/hub-chain`(선형 체인)과 `/loop-engine`(상태기반 루프)이 둘 다 이 스크립트를 읽는다.
별도 진행 원장을 두지 않는 이유는 이 저장소의 실패 양식이 **선언이 낡는 것**이기
때문이다(`scripts/pppp_status.py` 와 같은 원칙 — 산출물이 단일 기준이다).

읽기만 한다. 네트워크를 타지 않고 아무 파일도 쓰지 않는다.

실행:
    python scripts/chain_status.py hwajeong geumchon
    python scripts/chain_status.py --all --json
    python scripts/chain_status.py hwajeong --next    # 다음 명령 한 줄만
    python scripts/chain_status.py --all --next --include-paused   # 보류 도시까지

⚠ 서빙 보류 도시(`measured_pages.SERVED_CITIES` 밖)의 거점과 추후 확장 과제 거점
  (`page_hubs.PageHub.deferred` — 계획상가·단일시설, 2026-10-26)은 **다음 한 수를 내지 않는다.**
  단계와 근거는 그대로 보이고 명령만 가려진다 — `--include-paused` 로 꺼낸다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BRONZE = ROOT / "data" / "bronze"
GOLD = ROOT / "data" / "gold"

# 게이트 임계 — 근거는 각 skill 에 적혀 있다.
STORES_PER_BLDG_MAX = 10.0   # 초과 = 계획상가 밀집 (plan-gyeonggi §3-B)
PRECISE_COVERAGE_MIN = 80.0  # 미만 = floor_approx 잔여 많음 (build_page_master 경고선)
ANCHOR_GAP_MAX = 30.0        # 초과 = 앵커 가드레일 위반 (test_gold_anchor_comparison_attached)

OK, PARTIAL, TODO, BLOCKED = "ok", "partial", "todo", "blocked"
# 산출물이 없어서 못 한 것이 아니라 **안 하기로 정해서** 비어 있는 단계. 미완과 갈라
# 두지 않으면 제품 판단이 배선 결손으로 보고되고, 읽는 사람이 멀쩡한 코드를 고치러 간다.
PAUSED = "paused"
MARK = {OK: "[OK]", PARTIAL: "[~ ]", TODO: "[  ]", BLOCKED: "[!!]", PAUSED: "[--]"}


def _hubs() -> dict:
    """조회 대상 거점 전부 — `ALL_HUBS` 를 쓴다.

    ⚠ 종전에는 `HUBS + GYEONGGI_HUBS` 를 손으로 합쳤다. 그래서 2026-08-30 서울 미커버
      자치구 배치(`SEOUL_BATCH2_HUBS`)를 더하자 프로버가 그 12거점을 **"등록 안 됨"으로
      보고**했다 — 수집은 멀쩡히 끝났는데 프로버만 못 본 것이다. 배치가 늘 때마다 여기를
      고쳐야 하는 구조였고, 그게 곧 잊히는 자리다. `page_hubs` 가 이미 `ALL_HUBS` 로
      전부 합쳐 두므로 그것을 단일 출처로 삼는다.
    """
    from data.config import page_hubs as ph
    return dict(getattr(ph, "ALL_HUBS", None) or ph.HUBS)


def _latest(slug: str, name: str) -> Path | None:
    """bronze/{slug}/{날짜}/{name} 중 가장 최근 것."""
    found = sorted(BRONZE.glob(f"{slug}/*/{name}"))
    return found[-1] if found else None


def _load(p: Path | None):
    if not p or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _served_ids() -> set[str]:
    """API 거점 목록(화면 노출)에 오른 id. 수집 등록과 다른 축이다.

    시드(`seoul_pages.DISTRICTS`)가 아니라 **서빙이 실제로 내려보내는 합본**을 본다
    (2026-08-30 `measured_pages` 도입 — Gold 만으로 서는 거점이 시드 없이 목록에 오른다).
    시드만 세면 화정처럼 실제로 서빙되는 거점을 '미등재'로 잘못 보고한다.
    """
    try:
        from app.services.districts import PAGES_BY_ID
        return set(PAGES_BY_ID)
    except Exception:
        try:
            from app.data.seoul_pages import DISTRICTS
            return {d["id"] for d in DISTRICTS}
        except Exception:
            return set()


def _served_cities() -> frozenset[str] | None:
    """지금 **서빙하기로 정한** 도시. 판단을 못 읽으면 None.

    `_served_ids()` 와 다른 축이다: 저쪽은 "목록에 실제로 올랐나", 이쪽은 "올릴 도시로
    정했나"다. 둘을 안 가르면 제품 판단으로 뺀 거점이 **배선 결손으로 보고된다** —
    2026-09-05 에 geumchon·tanhyeon·yadang 셋이 그렇게 나왔다. Gold·건물마스터·앵커가
    다 서 있는데 프로버가 `_is_measured` 를 디버깅하라고 시켰고, 정작 거르는 것은 그
    다음 줄의 `SERVED_CITIES` 였다(measured_pages.build).

    None 을 돌려주면 판정하지 않는다 — 판단을 못 읽었을 때 "보류"라고 단정하면 진짜
    배선 결손이 조용히 묻힌다. 못 읽은 것과 안 하기로 한 것은 같지 않다.
    """
    try:
        from app.data.measured_pages import SERVED_CITIES
    except Exception:
        return None
    return frozenset(SERVED_CITIES)


def _batch_unserved(slug: str) -> bool:
    """경기 3차 배치 중 **서빙 목록 밖**으로 정한 거점인가(`page_hubs.GYEONGGI_BATCH3_SERVED_HUBS`).

    도시 판단(`_served_cities`)·추후 확장 표기(`deferred`)와 같은 축의 **거점 단위** 판단이다. 2026-10-31 화성을 서빙
    도시로 넣자(병점역 1곳) 같은 도시의 봉담이 「Gold 가 섰는데 목록에 없다 — _is_measured 확인」으로 보고됐다. 서빙 도시의
    다른 미서빙 3차 거점(ganeung·jeongja·skku …)도 그 전부터 그렇게 나왔다(리뷰). 못 읽으면 False — 판정하지 않는다.
    `slug not in ACTIVE_HUBS` 로 쓰지 않는 이유: 배치 밖 거점의 진짜 결손까지 보류로 삼킨다.
    """
    try:
        from data.config import page_hubs as ph
    except Exception:
        return False
    batch = getattr(ph, "GYEONGGI_BATCH3_HUBS", None) or {}
    served = getattr(ph, "GYEONGGI_BATCH3_SERVED_HUBS", None) or frozenset()
    return slug in batch and slug not in served


def _city_of(hub) -> tuple[str, str]:
    """(page_hubs 의 city, 백엔드 레지스트리가 아는 city). 어긋나면 그 자리에서 드러난다."""
    declared = getattr(hub, "city", "seoul")
    try:
        from app.data import cities
        known = declared if declared in cities.CITIES else ""
    except Exception:
        known = "?"
    return declared, known


def _is_gyeonggi(city_id: str) -> bool:
    """도시 레지스트리의 시도가 경기도인가. 못 읽으면 False(인허가 줄을 안 단다)."""
    try:
        from app.data import cities
    except Exception:
        return False
    city = cities.CITIES.get(city_id)
    return bool(city and city.sido == "경기도")


def _backend_caveat(slug: str) -> str:
    """서빙이 실제로 내려보내는 예외 문구(app/data/hub_caveats). 없으면 빈 문자열.

    판단이 코드에 있는데 프로버가 계속 "정해라"를 물으면 그것이 곧 낡은 선언이다 —
    이 저장소가 반복해 당한 실패 양식이라 프로버가 같은 자리를 본다.
    """
    try:
        from app.data import hub_caveats
    except Exception:
        return ""
    # 문구의 비율은 서빙이 집계에서 뽑는다. 프로버는 서빙을 띄우지 않으므로 같은 재료
    # (coverage.json 의 capacity 근거별 호실 수)로 같은 값을 만들어 넘긴다 — 넘기지
    # 않으면 문구가 "일부" 로 뭉개져, 프로버만 숫자 없는 문장을 보게 된다.
    by = ((_load(GOLD / slug / "coverage.json") or {}).get("by_capacity_method") or {})
    counted = (by.get("floor_ouln") or {}).get("capacity") or 0
    mall = (by.get("expos_units") or {}).get("capacity") or 0
    cells = {"capacity": counted or None,
             "inventory_coverage_pct": round(counted / (counted + mall) * 100, 1)
                                       if counted + mall else None}
    return hub_caveats.caveat_of(slug, cells)


def _served_vac(cov: dict | None) -> float | None:
    """서빙과 **같은 기준**의 거점 대표 공실률 — `floor_ouln` 만 센다.

    coverage.json 의 `reference_vacancy_pct` 를 쓰면 안 된다. 그 값은 `expos_units`
    (집합건물)를 섞은 것이고, 서빙(`services/gold_vacancy._COUNTED_METHODS`)은 그것을
    뺀다 — 집합상가 내부 점포가 분자에 안 잡혀 공실률이 78~86% 로 튀기 때문이다.
    두 값을 섞어 말하면 화면과 이 표가 다른 수를 말하게 된다.

    ⚠ API 최종값과도 완전히 같지는 않다. `GET /heatmap/vacancy` 는 지번 중복 제거와
      셀 집계를 더 하므로 소수점 단위로 다르다. **최종 확인은 API 로** 한다.
    """
    m = ((cov or {}).get("by_capacity_method") or {}).get("floor_ouln") or {}
    return m.get("vacancy_pct")


def stages(slug: str) -> list[dict]:
    """단계별 (이름, 상태, 근거, 다음 명령)."""
    hubs = _hubs()
    out: list[dict] = []

    def add(name, status, evidence, nxt=""):
        out.append({"stage": name, "status": status, "evidence": evidence, "next": nxt})

    # S1 등록
    hub = hubs.get(slug)
    if not hub:
        add("등록", TODO, f"page_hubs 에 {slug} 없음",
            "data/config/page_hubs.py 의 HUBS/GYEONGGI_HUBS 에 PageHub 한 줄 추가")
        return out
    declared, known = _city_of(hub)
    if known == "":
        add("등록", BLOCKED, f"page_hubs.city={declared} 인데 app/data/cities 에 없음",
            "apps/backend/app/data/cities.py 의 CITIES 에 같은 슬러그 추가")
    else:
        add("등록", OK, f"{hub.name} · city={declared} · r={hub.radius_m}m/{hub.stores_radius_m}m")

    # S2 점포 (Page 분자) + 계획상가 프로브
    stores = _load(_latest(slug, "stores_raw.json"))
    if not stores:
        add("점포", TODO, "bronze stores_raw.json 없음",
            f"python -m data.collectors.building_vacancy {slug} --no-ledger")
    else:
        bldgs = {s.get("bldMngNo") for s in stores if s.get("bldMngNo")}
        ratio = round(len(stores) / len(bldgs), 1) if bldgs else 0.0
        ev = f"점포 {len(stores):,} · 건물 {len(bldgs):,} · 건물당 {ratio}"
        # 예외 승인은 두 곳에 있을 수 있다. 경기 실측 거점은 `page_hubs.PageHub.caveat`
        # 에 적고, 서울 시드 거점은 백엔드 판단(app/data/hub_caveats)에 적는다 —
        # `data/config` 가 배포 이미지에 안 실려서(Dockerfile 51~53행) 서울 거점의
        # 문구를 page_hubs 에 두면 프로덕션 화면에 안 나온다.
        approval = hub.caveat or _backend_caveat(slug)
        if ratio > STORES_PER_BLDG_MAX and approval:
            add("점포", OK,
                ev + f" (>{STORES_PER_BLDG_MAX} 계획상가 밀집 · 예외 승인: {approval})")
        elif ratio > STORES_PER_BLDG_MAX:
            add("점포", BLOCKED, ev + f" (>{STORES_PER_BLDG_MAX} 계획상가 밀집)",
                "거점을 내리거나 집합상가 비중을 명시한 채 진행 — plan-gyeonggi 3-B")
        else:
            add("점포", OK, ev)

    # S3 폴리곤
    pj = _load(_latest(slug, "bldg_polygons.geojson"))
    if not pj:
        add("폴리곤", TODO, "bronze bldg_polygons.geojson 없음",
            f"python -m data.collectors.vworld_bldg {slug}")
    else:
        add("폴리곤", OK, f"{len(pj.get('features', [])):,}동")

    # S4~S5 대장 + 정밀 분모
    bv = _load(GOLD / slug / "building_vacancy.json")
    if not bv:
        add("대장", TODO, "gold building_vacancy.json 없음",
            f"python -m data.collectors.building_vacancy {slug}   # 쿼터: scripts/quota_preflight.py")
        add("정밀분모", TODO, "대장 선행", "")
    else:
        methods: dict[str, int] = {}
        for b in bv:
            m = b.get("capacity_method", "?")
            methods[m] = methods.get(m, 0) + 1
        mix = " ".join(f"{k}={v}" for k, v in sorted(methods.items()))
        # ⚠ 파일이 있다고 대장이 끝난 게 아니다(2026-10-28) — 수집기는 쿼터가 끝나도 받은 데까지 저장한다.
        #   후보(점포를 건물로 묶은 수) 대비 **받은** 행 수로 잘림을 잰다 — run_hub_chain_batch.ledger_counts 와 같은 셈이다.
        #   429 로 못 받은 `rate_limited` 행은 수집기가 재개 때 다시 받으므로 받은 것이 아니다.
        #   종전에는 존재만 봐서 대장이 239동 잘린 평택역이 Tier1 · 앵커 OK 로 보였다.
        try:
            import contextlib
            import io
            from data.collectors.building_vacancy import group_by_building
            with contextlib.redirect_stdout(io.StringIO()):   # 「[group] …」 이 --json·--next 출력을 깨뜨린다
                cand = len(group_by_building(stores)) if stores else None
        except Exception:
            cand = None
        got = len(bv) - methods.get("rate_limited", 0)
        gap = cand - got if cand is not None else 0
        if gap > 0:
            # TODO 로 둔다 — PARTIAL 은 「다음 한 수」로 뽑히지 않아 잘린 대장이 「모두 통과」로 읽혔다(리뷰).
            add("대장", TODO, f"{got:,}/{cand:,}동 받음 — {gap:,}동 남음(쿼터 소진·중단으로 잘렸다) · {mix}",
                f"python -m data.collectors.building_vacancy {slug}   # 쿼터: scripts/quota_preflight.py")
        else:
            add("대장", OK, f"{len(bv):,}동 · {mix}")
        precise = methods.get("floor_ouln", 0) + methods.get("expos_units", 0)
        # 분모는 **상업 건물만**이다. 비상업(non_commercial)·대장 미확인(no_ledger)은
        # 애초에 capacity 를 매길 대상이 아니라, 분모에 넣으면 정밀도가 낮아 보인다
        # (화정 2026-08-30: 비상업 182동을 섞어 40.6% → 실제 대상 기준 95.2%).
        target = len(bv) - methods.get("non_commercial", 0) - methods.get("no_ledger", 0)
        pct = round(precise / target * 100, 1) if target else 0.0
        if methods.get("floor_approx"):
            enough = pct >= PRECISE_COVERAGE_MIN
            # 임계를 넘겼으면 **명령을 제안하지 않는다.** 잔여 floor_approx 에는 '미시도'와
            # '판정완료(상업층 0 확정)'가 섞여 있고, 후자에 콜을 태우면 회수 0 이다
            # (2026-08-19 에 672콜/22동으로 겪었고 quota_preflight 가 같은 구분을 한다).
            # 화정 잔여 2동도 재호출 결과 회수율 0.0% 였다.
            add("정밀분모", PARTIAL if enough else TODO,
                f"floor_ouln+expos {pct}% · floor_approx {methods['floor_approx']}동 잔여"
                + (" (임계 충족 — 잔여는 판정완료일 수 있다)" if enough else ""),
                "" if enough else f"python -m data.collectors.floor_capacity {slug} --only-approx")
        else:
            add("정밀분모", OK, f"floor_approx 잔여 0 · 정밀 {pct}%")

    # S6 Page 마스터
    cov = _load(GOLD / slug / "coverage.json")
    master = GOLD / slug / "page_building_master.geojson"
    if not cov or not master.exists():
        add("Page마스터", TODO, "coverage.json / page_building_master.geojson 없음",
            f"python -m data.pipelines.build_building_attrs {slug} && "
            f"python -m data.pipelines.build_page_master {slug}")
    else:
        tier = str(cov.get("tier", "?"))
        rc = cov.get("reference_coverage_pct")
        ev = (f"{tier} · 노출 {cov.get('shown')}동 · 대표공실 {_served_vac(cov)}% "
              f"· 정밀커버리지 {rc}%")
        ok = tier.startswith("Tier1") and (rc or 0) >= PRECISE_COVERAGE_MIN
        add("Page마스터", OK if ok else PARTIAL, ev,
            "" if ok else f"python -m data.collectors.floor_capacity {slug} --only-approx  → 재빌드")

    # S7 앵커 대조
    cal = _load(GOLD / slug / "calibration.json")
    if not cal:
        add("앵커", TODO, "calibration.json 없음", "python -m data.pipelines.calibrate_vacancy")
    else:
        anchor = cal.get("anchor_pct") or (cal.get("combined") or {}).get("anchor_pct")
        ref = _served_vac(cov)
        if cal.get("anchor_is_fallback"):
            # 앵커 값이 R-ONE 이 아니라 폴백 10.0 이다 — 격차가 작아 보여도 **대조를 한 적이 없다**(2026-10-31).
            # TODO 로 둔다 — PARTIAL 은 「다음 한 수」로 뽑히지 않아 「모두 통과」로 읽힌다(위 대장 줄과 같은 이유 · 리뷰).
            add("앵커", TODO, f"앵커가 폴백 {anchor}% 다 — R-ONE 값을 아직 안 받았다 · 대표 {ref}%",
                "python -m data.collectors.rone_rent  →  python -m data.pipelines.calibrate_vacancy " + slug)
        elif anchor is None:
            add("앵커", PARTIAL, "R-ONE 앵커 없음 (표본 미매핑)",
                "data/config/rone_districts.py 에 매핑 추가 — 공유면 rone-shared 로 표기")
        elif ref is None:
            add("앵커", PARTIAL, f"앵커 {anchor}% · 대표값 미산출", "")
        else:
            gap = round(ref - anchor, 2)
            add("앵커", BLOCKED if abs(gap) > ANCHOR_GAP_MAX else OK,
                f"대표 {ref}% vs 앵커 {anchor}% = {gap:+}%p",
                "" if abs(gap) <= ANCHOR_GAP_MAX else "가드레일 30%p 초과 — 원인 규명 전 서빙 등재 금지")

    # S8 공실 유닛
    vu = GOLD / slug / "vacant_units.json"
    if vu.exists():
        add("공실유닛", OK, "vacant_units.json 있음")
    else:
        # ⚠ 이 단계는 **미실행과 후보 부재를 구분하지 못한다.** 파이프라인이 0유닛을 내면
        #   파일을 쓰지 않기 때문이다. 화정(2026-08-30)이 후자였다 — 정밀 분모(floor_ouln)
        #   공실 후보가 덕양구청 1동뿐이었고 호당 442평이라 면적 상한(200평)에서 걸렸다.
        #   집합건물이 유닛 대상에서 빠지는 거점은 이 상태가 정상일 수 있다.
        add("공실유닛", TODO,
            "없음 — 미실행이거나 후보 0(파이프라인은 0유닛이면 파일을 안 쓴다)",
            f"python -m data.pipelines.build_vacant_units {slug}")

    # 체인 실패 표식(2026-10-28) — 무인 배치가 이 거점의 한 단계에서 멈췄다. 뒤 산출물(앵커·유닛)이
    # 있어도 그것은 실패한 단계 **앞**의 입력으로 선 값이다(run_hub_chain_batch §지키는 것 4).
    # 표식이 있을 때만 줄을 단다 — 정상 거점은 9단계 그대로다.
    mark = _load(GOLD / slug / "chain_failed.json")
    if mark:
        tries = int(mark.get("attempts") or 1)
        add("체인실패", BLOCKED,
            f"「{mark.get('step', '?')}」 실패 {tries}회({mark.get('at', '?')}) — "
            + ("같은 단계가 연달아 실패해 배치·재개가 건너뛴다(사람 확인 · 원인을 본 뒤 표식 파일을 지울 것)"
               if tries >= 3 else f"다음 배치가 '{mark.get('redo_from', 'none')}' 부터 다시 민다"),
            f"python scripts/run_hub_chain_batch.py --hubs {slug}")

    # 경기 인허가(2026-10-28) — 없거나 Page 마스터보다 늦게 들어왔으면 분자 보강이 빠진 값이라 공실이 과대다.
    # 대조 기준은 인허가를 실제로 읽는 page_building_master 다(앵커 보정만 다시 돌면 calibration 은 새로워진다).
    # 문제가 있을 때만 줄을 단다 — 할 일이라 TODO 다(PARTIAL 은 「다음 한 수」로 안 뽑힌다).
    if cal and _is_gyeonggi(declared):
        lic = _latest(slug, "licensing_biz.json")
        if lic is None:
            add("인허가", TODO, "경기 인허가(GENRESTRT) 없이 Gold 가 섰다 — 공실이 과대일 수 있다",
                f"python -m data.collectors.gg_licensing {slug}")
        elif master.exists() and lic.stat().st_mtime > master.stat().st_mtime:
            add("인허가", TODO, f"인허가({lic.parent.name})가 Page 마스터보다 늦게 들어왔다 — 다시 세워야 반영된다",
                f"python scripts/run_hub_chain_batch.py --hubs {slug}")

    # S9 서빙 등재 — 수집 등록과 다른 축이다
    if slug in _served_ids():
        add("서빙등재", OK, "거점 목록(services.districts.PAGES)에 있음")
    else:
        prev = {s["stage"]: s["status"] for s in out}
        ready = prev.get("Page마스터") in (OK, PARTIAL) and prev.get("앵커") != BLOCKED
        on = _served_cities()
        deferred = getattr(_hubs().get(slug), "deferred", "")
        if on is not None and declared not in on:
            # 산출물이 없어서가 아니라 **안 올리기로 정해서** 빠진다. 여기에 수집·디버깅
            # 명령을 주면 안 된다 — 다음 한 수로 뽑히지 않도록 next 를 비운다.
            add("서빙등재", PAUSED,
                f"'{declared}' 는 서빙 대상 도시가 아니다 — 제품 판단으로 뺐다"
                f" (measured_pages.SERVED_CITIES={{{', '.join(sorted(on))}}})"
                + ("" if ready else " · Gold 도 아직 안 섰다"))
        elif deferred:
            # 도시는 서빙하지만 이 거점은 **추후 확장 과제**로 표기됐다(2026-10-26 ·
            # page_hubs.PageHub.deferred). 도시 보류와 같은 이유로 명령을 가린다.
            add("서빙등재", PAUSED,
                f"추후 확장 과제({deferred}) — 신규 확장에서 뺐다 (page_hubs.PageHub.deferred)"
                + ("" if ready else " · Gold 도 아직 안 섰다"))
        elif _batch_unserved(slug):
            add("서빙등재", PAUSED,
                "경기 3차 서빙 목록(page_hubs.GYEONGGI_BATCH3_SERVED_HUBS) 밖 — 제품 판단으로 뺐다"
                + ("" if ready else " · Gold 도 아직 안 섰다"))
        else:
            add("서빙등재", TODO if ready else BLOCKED,
                "거점 목록 미등재 (지도·API 목록에 안 뜬다)",
                "Gold 가 섰는데 목록에 없다 — app/data/measured_pages._is_measured 조건 확인" if ready
                else "Gold 가 서기 전에는 등재하지 않는다 — 시드를 지어내지 않기 위해")

    return out


def summarize(slug: str, *, include_paused: bool = False) -> dict:
    st = stages(slug)
    blocked = [s for s in st if s["status"] == BLOCKED]
    done = sum(1 for s in st if s["status"] == OK)
    # 다음 한 수는 **파이프라인 순서로 가장 앞선 미완 단계**다. 막힌 단계를 먼저 고르면
    # 안 된다 — 마지막 단계(서빙등재)는 선행이 없을 때 항상 막힘으로 나오므로, 그것을
    # 집으면 루프가 "아직 수집도 안 한 거점을 등재하라"는 헛수를 둔다.
    nxt = next((s for s in st if s["status"] in (BLOCKED, TODO) and s["next"]), {})
    # 서빙이 보류된 도시의 거점은 **다음 한 수를 내지 않는다.** 단계는 그대로 보이되
    # 명령만 거둔다 — 2026-09-05 결정(경기 중단 유지 + 수집도 멈춤)이다.
    #
    # 종전에는 명령을 그대로 냈다. 그래서 서빙은 09-03 에 껐는데 프로버는 경기 17거점의
    # 대장·공실유닛을 계속 "다음 한 수"로 냈고, 그걸 집으면 **화면에 닿지 않을 데이터에
    # 하루치 쿼터를 태우게** 된다. 재개할 때는 `--include-paused` 로 되살린다(명령이
    # 지워진 것이 아니라 가려진 것이다 — 단계 목록에는 그대로 있다).
    paused = any(s["status"] == PAUSED for s in st)
    if paused and not include_paused:
        nxt = {}
    return {"slug": slug, "done": done, "total": len(st), "stages": st,
            "blocked": [b["stage"] for b in blocked], "serving_paused": paused,
            "next_stage": nxt.get("stage", ""), "next": nxt.get("next", "")}


def main() -> int:
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in flags
    only_next = "--next" in flags
    incl = "--include-paused" in flags
    slugs = sorted(_hubs()) if ("--all" in flags or not args) else args

    reports = [summarize(s, include_paused=incl) for s in slugs]
    if as_json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    if only_next:
        for r in reports:
            nxt = r["next"]
            if nxt and r["serving_paused"]:
                nxt += "   # ⚠ 서빙 보류 도시 — 화면에는 안 오른다(--include-paused 로 꺼낸 값)"
            print(f"{r['slug']}\t{r['next_stage']}\t{nxt}")
        return 0

    for r in reports:
        head = f"\n■ {r['slug']}  {r['done']}/{r['total']} 단계 통과"
        if r["blocked"]:
            head += "  막힘: " + ", ".join(r["blocked"])
        if r["serving_paused"]:
            kind = getattr(_hubs().get(r["slug"]), "deferred", "")
            why = (f"추후 확장 과제({kind})" if kind else
                   "경기 3차 서빙 목록 밖" if _batch_unserved(r["slug"]) else "서빙 대상 도시 아님")
            head += f"  보류: {why}" + ("" if incl else " (다음 한 수 없음)")
        print(head)
        for s in r["stages"]:
            print(f"  {MARK[s['status']]} {s['stage']:10s} {s['evidence']}")
            # 보류 거점의 명령은 **지우지 않고 가린다** — 재개할 때 다시 찾아야 하므로.
            if s["next"] and (incl or not r["serving_paused"]):
                print(f"       -> {s['next']}")
            elif s["next"]:
                print(f"       -  (보류 중 — --include-paused 로 명령 표시)")
    pending = next((r for r in reports if r["next"]), None)
    if pending:
        print(f"\n다음 한 수 [{pending['slug']} / {pending['next_stage']}]: {pending['next']}")
    elif reports:
        print("\n다음 한 수: 없음 — 지정한 거점은 모두 통과했다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
