"""메뉴 예시 v2 — 「주기별로 사는 것」을 더한다(2026-11-17 사용자 요청).

- 식재료·포장: 레시피 × 계획 판매량 × 발주 주기 → 1회 발주(구매 단위로 올림)와 월 사용액. 이 돈은 이미 원가율에 들어 있다.
- 위생·청소 · 주방 소모품 · 설비 유지 · 서비스: 레시피에 안 들어가는 주기 구매. 월 환산액을 「기타 월 고정비」에 더한다.
- 개업 첫 주문(초도 물량): 식재료·포장 한 주기분 + 위생·청소·주방 소모품·유니폼 1회분. 한 번 사는 준비물과 더하면
  「개업 전 필요한 돈(설비·물품 — 인테리어·보증금·권리금 제외)」.
모든 값은 예시다(출처 키 guess). 사용자가 「예시 채우기」를 누를 때만 쓰고, 계산 결과 저장·KPI 에 쓰지 않는다.
"""
import math

import menu_data as MD
from menu_data import DEFAULT_RENT, ING, INDUSTRIES, PAID_HOURS, WAGE, menu_cost

# 발주 정보 — key: (구매 단위 크기(환산 단위 기준), 구매 단위 표기, 보관, 발주 주기(일)). None = 사지 않음(자가생산)
ORDER = {
    "bean_blend": (1000, "1kg 봉", "상온·밀봉", 7), "bean_spec": (1000, "1kg 봉", "상온·밀봉", 7),
    "milk": (1000, "1L 팩", "냉장", 2), "cream": (1000, "1L 팩", "냉장", 3), "syrup": (1000, "1L 병", "상온", 14),
    "lemon": (1000, "1kg 병", "냉장", 7), "soda": (1500, "1.5L 병", "상온", 7), "icetea": (1000, "1kg 봉", "상온", 30),
    "ice": None,
    "financier": (10, "10개 납품", "냉장", 2), "cookie": (10, "10개 납품", "상온", 3),
    "cup_ice": (1000, "1,000개 박스", "상온", 30), "cup_hot": (1000, "1,000개 박스", "상온", 30),
    "straw": (1000, "1,000개 박스", "상온", 30), "napkin": (1000, "1,000장 묶음", "상온", 30), "dbox": (100, "100개 묶음", "상온", 30),
    "flour": (20000, "20kg 포대", "상온", 14), "flour_t55": (25000, "25kg 포대", "상온", 14),
    "butter": (1000, "1kg 블록", "냉장", 7), "butter_f": (1000, "1kg 블록", "냉장", 7), "sugar": (15000, "15kg 포대", "상온", 30),
    "egg": (30, "30구 판", "냉장", 3), "yeast": (100, "100개분 묶음", "상온", 14), "redbean": (5000, "5kg 통", "냉장", 7),
    "custard": (1000, "1kg 팩", "냉장", 3), "ccheese": (1000, "1kg 팩", "냉장", 7), "bread_bag": (100, "100장 묶음", "상온", 30),
    "rice": (20000, "20kg 포대", "상온", 14), "pork": (1000, "1kg 팩", "냉장", 2), "beef_hanu": (1000, "1kg 팩", "냉장", 2),
    "beef_imp": (1000, "1kg 팩", "냉동", 7), "kimchi": (10000, "10kg 박스", "냉장", 7), "tofu": (1000, "1kg 판", "냉장", 2),
    "doenjang": (14000, "14kg 통", "상온", 30), "gochujang": (14000, "14kg 통", "상온", 30), "veg": (1000, "1kg 묶음", "냉장", 2),
    "namul": (1000, "1kg 팩", "냉장", 2), "sesame": (1800, "1.8L 병", "상온", 30), "clam": (1000, "1kg 망", "냉장", 1),
    "fish": (10, "10토막 박스", "냉동", 7), "banchan": (50, "50인분 재료", "냉장", 3), "stock": (100, "100인분 재료", "상온", 14),
    "pack_rice": (500, "500개 박스", "상온", 30), "pack_soup": (200, "200개 박스", "상온", 30), "spoon": (500, "500개 박스", "상온", 30),
    "gim": (100, "100장 묶음", "상온", 14), "kb_set": (50, "50줄분 재료", "냉장", 3), "kb_prem": (50, "50줄분 재료", "냉장", 2),
    "tuna": (1000, "1kg 캔", "상온", 14), "tteok": (1000, "1kg 봉", "냉장", 3), "eomuk": (1000, "1kg 봉", "냉장", 3),
    "t_sauce": (1000, "1kg 팩", "냉장", 7), "rose": (1000, "1kg 팩", "냉장", 7), "mozza": (1000, "1kg 봉", "냉장", 7),
    "ramen": (40, "40개 박스", "상온", 14), "sundae": (1000, "1kg 팩", "냉장", 2), "udon": (30, "30개 박스", "냉동", 7),
    "fry_set": (30, "30접시분", "냉동", 7), "pack_kb": (500, "500줄분 묶음", "상온", 30), "pack_tt": (200, "200개 박스", "상온", 30),
    "chk": (10, "10마리 박스", "냉장", 1), "chk_prem": (10, "10마리 박스", "냉장", 1), "chk_bl": (2000, "2kg 팩", "냉장", 2),
    "oil": (65, "18L 캔(약 65마리분)", "상온", 7), "powder": (100, "100마리분 묶음", "상온", 14), "y_sauce": (1000, "1kg 팩", "냉장", 7),
    "radish": (100, "100개 박스", "냉장", 7), "box_chk": (100, "100개 묶음", "상온", 30), "pack_misc": (500, "500세트 박스", "상온", 30),
    "keg": (20000, "20L 케그", "냉장", 7), "jeon": (20, "20접시분", "냉동", 7), "dakbok": (10, "10냄비분", "냉장", 2),
    "dubuk": (20, "20접시분", "냉장", 3), "soju": (20, "20병 상자", "상온", 7), "soju_p": (12, "12병 상자", "상온", 14),
    "yukhoe": (10, "10접시분", "냉장", 1), "seafood": (10, "10접시분", "냉장", 1), "highball": (30, "30잔분", "상온", 14),
    "highball_b": (30, "30잔분", "상온", 14), "fries": (2500, "2.5kg 봉", "냉동", 7), "dry_snack": (20, "20접시분", "상온", 14),
    "fry_oil_s": (80, "80접시분", "상온", 14),
}
CYCLE_LABEL = {1: "매일", 2: "2일마다", 3: "3일마다", 7: "주 1회", 14: "2주 1회", 30: "월 1회", 90: "분기 1회", 180: "반기 1회", 365: "연 1회"}
OPEN_CATS = ("위생·청소", "주방 소모품")   # 개업 전에 1회분을 사 두는 분류(서비스·필터 교체는 아님)

# 레시피에 안 들어가는 주기 구매 — (이름, 분류, 주기(일), 1회 표기, 1회 금액(원))
COMMON = [
    ("주방세제(업소용 18.75L)", "위생·청소", 30, "1통", 35000),
    ("소독제(락스 등)", "위생·청소", 30, "2통", 12000),
    ("위생장갑(니트릴 100매)", "위생·청소", 7, "1박스", 9000),
    ("키친타월·행주", "위생·청소", 7, "1묶음", 12000),
    ("종량제 봉투·음식물 처리", "서비스·기타", 30, "1달분", 60000),
    ("해충 방제(방역 서비스)", "서비스·기타", 30, "1회", 55000),
    ("정수기 필터 교체", "설비 유지", 90, "1세트", 90000),
]
EXTRA = {
    "cafe_coffee": [("머신 세정제(분말)", "위생·청소", 30, "1통", 25000), ("에스프레소 머신 가스켓·샤워스크린", "설비 유지", 180, "1세트", 60000),
                    ("제빙기 필터", "설비 유지", 90, "1개", 70000)],
    "cafe_bakery": [("유산지·테프론 시트", "주방 소모품", 30, "1묶음", 40000), ("오븐 점검·패킹 교체", "설비 유지", 90, "1회", 80000)],
    "restaurant_korean": [("식기세척기 세제·린스", "위생·청소", 30, "1세트", 90000), ("후드 필터 청소", "설비 유지", 90, "1회", 100000)],
    "restaurant_snack": [("김발·조리용 비닐", "주방 소모품", 30, "1묶음", 25000), ("튀김기 청소·필터", "설비 유지", 30, "1회", 20000)],
    "restaurant_chicken": [("튀김기 필터·청소", "설비 유지", 30, "1회", 30000), ("후드·덕트 청소", "설비 유지", 180, "1회", 250000)],
    "bar_cooking": [("식기세척기 세제·린스", "위생·청소", 30, "1세트", 90000), ("후드 필터 청소", "설비 유지", 90, "1회", 100000),
                    ("생맥주 라인 세척(주류사 서비스 — 무료인 경우가 많음)", "설비 유지", 14, "1회", 0)],
}
UTIL = {"cafe_coffee": 45, "cafe_bakery": 75, "restaurant_korean": 55, "restaurant_snack": 40, "restaurant_chicken": 50, "bar_cooking": 45}  # 공과금 예시 만원/월
UNIFORM_EACH = 25000      # 앞치마·유니폼 1인 · 반기 1회
DISH_REFILL = 0.10        # 식기 보충(파손·분실) — 「한 번 사는 것」 중 식기 금액의 연 10%


def periodic_items(ind, tier_key):
    t = ind["tiers"][tier_key]
    rows = [dict(name=n, cat=c, cycle=cy, unit=u, amount=a, src="guess") for n, c, cy, u, a in COMMON + EXTRA.get(ind["key"], [])]
    rows.append(dict(name="앞치마·유니폼", cat="서비스·기타", cycle=180, unit=f"{t['staff']}벌", amount=UNIFORM_EACH * t["staff"], src="guess"))
    dishes = sum(q * p for _n, c, q, p in t["setup"] if c == MD.D_)
    if dishes:
        rows.append(dict(name="식기 보충(파손·분실 — 식기 금액의 연 10%)", cat="위생·청소", cycle=365, unit="1년분",
                         amount=round(dishes * DISH_REFILL), src="guess"))
    for r in rows:
        r["month"] = r["amount"] * 30 / r["cycle"]
        r["opening"] = r["cat"] in OPEN_CATS and r["cycle"] < 365 or r["name"] == "앞치마·유니폼"
    return rows


def periodic_month(ind, tier_key):
    return sum(r["month"] for r in periodic_items(ind, tier_key))


def mix(ind, tier_key):
    t = ind["tiers"][tier_key]
    tot = sum(m["share"] for m in t["menus"])
    avg_price = sum(m["price"] * m["share"] for m in t["menus"]) / tot
    avg_cost = sum(menu_cost(m)[0] * m["share"] for m in t["menus"]) / tot
    return avg_price, avg_cost / avg_price


def order_plan(ind, tier_key, daily):
    """계획 판매량(하루) → 식재료·포장 품목별 하루 사용량 · 1회 발주(구매 단위로 올림) · 1회 금액 · 월 사용액."""
    t = ind["tiers"][tier_key]
    tot = sum(m["share"] for m in t["menus"])
    use = {}
    for m in t["menus"]:
        cnt = daily * m["share"] / tot
        for key, qty in m["lines"]:
            use[key] = use.get(key, 0) + cnt * qty
    out = []
    for key, u in use.items():
        od = ORDER.get(key)
        if od is None or u <= 0:
            continue
        pack, label, storage, cycle = od
        g = ING[key]
        packs = max(1, math.ceil(u * cycle / pack - 1e-9))
        out.append(dict(key=key, name=g[0], cat=g[5], storage=storage, cycle=cycle, packs=packs, label=label,
                        order_cost=packs * pack * g[4], month_cost=u * ind["days"] * g[4], src=g[6]))
    return sorted(out, key=lambda r: (r["cycle"], r["cat"], r["name"]))


def tier_summary(ind, tier_key, rent=DEFAULT_RENT):
    t = ind["tiers"][tier_key]
    avg_price, rate = mix(ind, tier_key)
    labor = t["staff"] * WAGE * PAID_HOURS / 10000
    pm = periodic_month(ind, tier_key) / 10000
    other = UTIL[ind["key"]] + pm
    fixed = rent + labor + other
    bep = fixed / (1 - rate)
    daily = math.ceil(bep * 10000 / avg_price / ind["days"] - 1e-9)
    plan = order_plan(ind, tier_key, daily)
    first_order = sum(r["order_cost"] for r in plan) / 10000
    first_supplies = sum(r["amount"] for r in periodic_items(ind, tier_key) if r["opening"]) / 10000
    setup = sum(q * p for _n, _c, q, p in t["setup"]) / 10000
    return dict(avg_price=avg_price, cost_rate=rate, labor=labor, util=UTIL[ind["key"]], periodic_month=pm, other=other,
                fixed=fixed, bep=bep, daily=daily, first_order=first_order + first_supplies, first_food=first_order,
                first_supplies=first_supplies, setup=setup, pre_open=setup + first_order + first_supplies,
                staff=t["staff"], menus=len(t["menus"]))


if __name__ == "__main__":
    for ind in INDUSTRIES:
        for tk in ("premium", "value", "factory"):
            s = tier_summary(ind, tk)
            print(f'{ind["label"]:8} {MD.TIER_NAMES[tk]:5} 객단가 {s["avg_price"]:>7,.0f} · 원가율 {s["cost_rate"]*100:4.1f}% · 주기구매 {s["periodic_month"]:5.1f}만 '
                  f'· 기타고정 {s["other"]:5.1f}만 · 하루 {s["daily"]:4d}개 · 첫주문 {s["first_order"]:6.1f}만 · 개업전 {s["pre_open"]:7,.0f}만')
