"""[Page] 건물 단위 공실 확장 거점 레지스트리.

⚠ 이 줄은 오래도록 "핵심 13거점" 이라고 적고 있었다. 레지스트리는 그 뒤 여러 번 자랐다:
  HUBS 54(서울 1차) + SEOUL_BATCH2/3/4_HUBS 12+5+10 = 서울 81 ·
  GYEONGGI_HUBS 20(고양 14·파주 6) = ALL_HUBS 101.
  2026-10-26 부터 고양·파주를 서빙한다 — 단 경기 20 중 **추후 확장 과제 11곳**(계획상가 7 ·
  단일시설 4, `PageHub.deferred`)은 빼고 9곳만이다. 서빙·산출 대상은 `ACTIVE_HUBS` 다.
  (09-15 에 "66" 으로 고친 이 줄도 09-21 확장으로 다시 낡았다.)
**수를 이 독스트링에서 읽지 말고 `len(ACTIVE_HUBS)` 로 셀 것** — 선언이 낡는 것이
이 저장소의 주된 실패 양식이다.

garosugil PoC 파이프라인(config/garosugil.py)을 다거점으로 일반화한 단일 출처(SSOT).
각 거점은 수집기(vworld_bldg·building_vacancy)와 Gold 빌더(build_page_master)가
공유하는 **최소 상수**만 갖는다: 중심좌표(cx/cy)·수집 반경·표시명·거점 id.

시군구/법정동/본번/부번은 거점 상수가 아니라 점포·폴리곤의 PNU(lnoCd) 19자리에서
건별로 파생하므로(수집기 _jibun 참조) 레지스트리에 둘 필요가 없다. 즉 신규 거점을
추가할 때 필요한 것은 중심좌표와 반경뿐이다.

중심좌표 출처: apps/backend/app/data/seoul_pages.py DISTRICTS[*].center([lat, lng]).
  → cx=경도=center[1], cy=위도=center[0].
garosugil 은 2026-07-19 지상검증(정확도 75%)을 통과한 산출물이므로 원
config/garosugil.py 의 검증된 반경(400/600)을 그대로 보존한다 (재수집 대상 아님).

거점 id 는 seoul_pages.py DISTRICTS id 와 동일. 프론트가 heatmap ?district= 로 넘기는 값.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PageHub:
    slug: str                  # bronze/gold 하위 폴더명 (= 거점 id)
    name: str                  # 표시명 (프론트 패널 제목)
    cx: float                  # 중심 경도(lon)
    cy: float                  # 중심 위도(lat)
    radius_m: int = 500        # V-World 폴리곤 수집 bbox 반경(±m). 대각 코너는 ≈radius×√2 까지 커버
    stores_radius_m: int = 700 # 점포 수집 반경 — 폴리곤 커버리지 ⊇ 원칙(경계 건물 empty 오판 방지)
    # 도시 슬러그 — apps/backend/app/data/cities.CITIES 의 키와 같은 값.
    # 54거점이 전부 서울이던 동안은 암묵이었다. 경기 거점이 붙으면서 필드가 됐다.
    # ⚠ 여기와 백엔드 레지스트리가 어긋나면 수집은 되는데 API 가 다른 도시로 부른다
    #   → apps/backend/tests/test_city_registry.py 가 고정한다.
    city: str = "seoul"
    # 예외 표시 — 이 거점의 수치를 **다른 거점과 나란히 놓으면 안 되는 이유**를 적는다.
    # 비어 있으면 예외가 아니다. 채워져 있으면 API 응답(`caveat`)에 그대로 실려
    # 화면이 그 문구를 보여준다. 거점을 빼는 대신 **왜 다른지 밝힌 채로 넣기 위한** 자리다.
    # ⚠ 여기에 적은 문구가 곧 사용자에게 보이는 경고다. 추측이 아니라 실측을 적는다.
    caveat: str = ""
    # 추후 확장 과제 — 등록·수집은 됐지만 **지금은 서빙하지 않는** 이유(2026-10-26 사용자 결정).
    # 비어 있으면 서빙 대상이다. 값은 `DEFERRED_KINDS` 둘 중 하나뿐이다.
    # **신규 확장(서울 밖) 거점에만** 붙인다 — 서울 서빙 거점은 같은 기준에 걸려도 그대로
    # 둔다(같은 날 같은 결정: 여의도·반포·가락·용산·동대문·공덕·독산 7곳은 서빙 유지).
    # → docs/decision-goyang-paju-corridor-2026-10-26.md §2
    deferred: str = ""
    # 가까운 쪽 귀속 — 이 거점의 수집 범위가 **다른 거점의 범위와 겹칠 때**, 겹친 점포·건물을 중심이 더 가까운 거점 한 곳에만 담는다
    # (같으면 slug 가 앞선 쪽). 값은 짝 거점의 slug. 겹침 때문에 반경을 줄여야 했던 자리(2026-10-31 용봉동·전남대 — 중심 416m 라 반경 207m 로
    # 상가가 잘렸다)를 풀기 위한 것이다. 같은 점포가 두 거점에 이중 계수되는 문제만 막고, 반경 자체는 각자 정한다.
    partition_with: tuple[str, ...] = ()


# 추후 확장 과제의 종류. 두 종류를 한 문구로 뭉치지 않는다 — 풀어야 할 문제가 다르다.
#   계획상가 — 건물당 점포 >10 이거나 집합 호실 비중 >80%. 우리 공실 분모(일반건축물)가
#             상업 재고의 일부만 덮는다. 점포↔호실 매칭이 풀려야 재개한다.
#   단일시설 — 점포 대부분이 몰 한 채(top10 지번 집중도 64~82%). '상권'이 아니라 '건물'이다.
DEFERRED_KINDS: tuple[str, ...] = ("계획상가", "단일시설")


# 핵심 13거점 (platform13 원년 거점 집합). garosugil 은 검증 반경 유지.
HUBS: dict[str, PageHub] = {
    "garosugil":       PageHub("garosugil",       "신사동 가로수길", 127.0230, 37.5205, 400, 600),
    "apgujeong-rodeo": PageHub("apgujeong-rodeo", "압구정로데오",   127.0385, 37.5273),
    "hongdae":         PageHub("hongdae",         "홍대",          126.9235, 37.5551),
    "yeonnam":         PageHub("yeonnam",         "연남동",         126.9245, 37.5615),
    "ikseon":          PageHub("ikseon",          "익선동",         126.9900, 37.5740),
    "seochon":         PageHub("seochon",         "서촌",          126.9705, 37.5790),
    "myeongdong":      PageHub("myeongdong",      "명동",          126.9855, 37.5630),
    "euljiro":         PageHub("euljiro",         "을지로(힙지로)", 126.9915, 37.5663),
    "seongsu":         PageHub("seongsu",         "성수동 카페거리", 127.0559, 37.5445),
    "seoulsup":        PageHub("seoulsup",        "서울숲 아틀리에길", 127.0430, 37.5462),
    "itaewon":         PageHub("itaewon",         "이태원",         126.9946, 37.5346),
    "hannam":          PageHub("hannam",          "한남동·용리단길", 127.0005, 37.5352),
    "songridan":       PageHub("songridan",       "송리단길",       127.1055, 37.5087),

    # ── 확장 41거점 (54거점 완성) — 2026-07-26 추가, 수집 미착수 ──────────
    # radius_m 은 config/platform_places.DISTRICT_PLACES 의 검증 반경(SNS·업종·R-ONE
    # 3단 검증 통과값)을 그대로 쓴다. 위 13거점은 garosugil 을 뺀 12곳이 기본값 500 을
    # 그대로 둔 상태라 상권 크기와 무관하게 균일한데, 신규 41거점은 거점별 실제 크기를
    # 따른다(예: nokdu 200m ~ jamsil 800m). "크기보다 보행경로·정체성 우선" 원칙.
    "gangnam":         PageHub("gangnam",         "강남역·강남대로",    127.0268, 37.5004, 600, 800),
    "hapjeong":        PageHub("hapjeong",        "합정",          126.9118, 37.5502, 300, 500),
    "mangwon":         PageHub("mangwon",         "망원동·망리단길",    126.9093, 37.557, 500, 700),
    "samcheong":       PageHub("samcheong",       "삼청동·북촌",      126.9831, 37.5816, 400, 600),
    "gwangjang":       PageHub("gwangjang",       "광장시장·종로4가",   127.0003, 37.5713, 500, 700),
    "dongdaemun":      PageHub("dongdaemun",      "동대문·DDP",     127.0096, 37.5664, 700, 900),
    "jamsil":          PageHub("jamsil",          "잠실·롯데월드타워",   127.1014, 37.5143, 800, 1000),
    "konkuk":          PageHub("konkuk",          "건대입구·화양동",    127.0678, 37.5404, 400, 600),
    "yeouido":         PageHub("yeouido",         "여의도",         126.9242, 37.5249, 600, 800),
    "mullae":          PageHub("mullae",          "문래동 창작촌",     126.8942, 37.5153, 700, 900),
    "banpo":           PageHub("banpo",           "고속터미널·반포",    127.0066, 37.5044, 500, 700),
    "sinchon":         PageHub("sinchon",         "신촌·이대",       126.9391, 37.5572, 600, 800),
    "yeonhui":         PageHub("yeonhui",         "연희동",         126.932, 37.5672, 500, 700),
    "cheongnyangni":   PageHub("cheongnyangni",   "청량리·경동시장",    127.0434, 37.581, 600, 800),
    "sharosugil":      PageHub("sharosugil",      "샤로수길·서울대입구",  126.9549, 37.4789, 400, 600),
    "nokdu":           PageHub("nokdu",           "녹두거리",        126.937, 37.4703, 200, 400),
    "sillim":          PageHub("sillim",          "신림역·별빛거리",    126.9294, 37.4858, 500, 700),
    "noryangjin":      PageHub("noryangjin",      "노량진",         126.9393, 37.5126, 500, 700),
    "sungshin":        PageHub("sungshin",        "성신여대·돈암",     127.0181, 37.5937, 300, 500),
    "anam":            PageHub("anam",            "안암·고려대",      127.0251, 37.5858, 500, 700),
    "cheongdam":       PageHub("cheongdam",       "청담동 명품거리",    127.0483, 37.5248, 500, 700),
    "dosan":           PageHub("dosan",           "도산공원",        127.0334, 37.5223, 500, 700),
    "nonhyeon":        PageHub("nonhyeon",        "논현동",         127.0209, 37.5105, 500, 700),
    "teheran":         PageHub("teheran",         "역삼·테헤란로",     127.0358, 37.5011, 500, 700),
    "seolleung":       PageHub("seolleung",       "선릉",          127.049, 37.5046, 600, 800),
    "yongsan":         PageHub("yongsan",         "용산역",         126.9632, 37.5285, 500, 700),
    "namdaemun":       PageHub("namdaemun",       "남대문시장",       126.9785, 37.5585, 300, 500),
    "cityhall":        PageHub("cityhall",        "시청역",         126.9768, 37.5641, 500, 700),
    "jamsilsaenae":    PageHub("jamsilsaenae",    "잠실새내",        127.0832, 37.5101, 300, 500),
    "garak":           PageHub("garak",           "가락시장",        127.1117, 37.4935, 500, 700),
    "jangan":          PageHub("jangan",          "장안동",         127.0715, 37.5712, 300, 500),
    "gongdeok":        PageHub("gongdeok",        "공덕역",         126.951, 37.5421, 400, 600),
    "gunja":           PageHub("gunja",           "군자역",         127.0802, 37.5562, 400, 600),
    "chungmuro":       PageHub("chungmuro",       "충무로",         126.9943, 37.5615, 600, 800),
    "nambu":           PageHub("nambu",           "남부터미널",       127.0195, 37.4863, 500, 700),
    # kyunghee: platform_places 는 lon 127.0535 이나 SSOT(seoul_pages)의 127.0524 를 채택(97m 차)
    "kyunghee":        PageHub("kyunghee",        "경희대",         127.0524, 37.5937, 500, 700),
    "wangsimni":       PageHub("wangsimni",       "왕십리",         127.0359, 37.5611, 500, 700),
    "sadang":          PageHub("sadang",          "사당역",         126.983, 37.478, 300, 500),
    "sukmyung":        PageHub("sukmyung",        "숙대입구",        126.9711, 37.5448, 400, 600),
    "hyehwa":          PageHub("hyehwa",          "혜화·대학로",      127.0017, 37.5832, 500, 700),
    "dangsan":         PageHub("dangsan",         "당산",          126.902, 37.5346, 300, 500),
}

# ── 서울 미커버 자치구 2차 확장 (2026-08-30 등재) ────────────────────────────
# 서울 25구 중 **10구에 거점이 0개**였다(중랑·강북·도봉·노원·은평·양천·강서·구로·금천·강동).
# 그런데 미사용 R-ONE 표본 16개 중 12개가 **정확히 그 구들**을 가리킨다 — 부동산원이
# 2024Q3 표본개편 때 서울 외곽 구를 새로 넣었고, 우리 미커버 구와 겹친다.
#
# 표본이 그 자리에 있으므로 **정확 매핑**이다(경기 17/20 이 공유였던 것과 다르다).
# ⚠ 대가는 이력 길이다 — 이 표본들은 **8분기**뿐이라 기존 거점(21~22분기)에 못 미친다.
#   Page(공실·앵커 대조)는 8분기로 충분하지만 **LSTM 이력은 짧다**. samcheong 이 북촌
#   7분기를 피해 광화문에 매핑된 것과 같은 제약이고, 분기가 쌓이면 풀린다.
#
# 1차 프로브(등록 없이 상가정보만 · 건축HUB 콜 0): 통과 10 · 주의 2 · 기각 0.
# 건물당 점포 2.3~3.8 로 **가로수길(4.5)보다도 낮다** — 경기(7.7~46.8)와 대비된다.
# 기존 거점과 2.4~7.7km 떨어져 이격 문제도 없다.
# 근거: reports/seoul_uncovered_probe.json
SEOUL_BATCH2_HUBS: dict[str, PageHub] = {
    # ⚠ 양천 목동은 `mokdong-yc` 다 — 파주 운정 목동(`mokdong`)과 슬러그가 부딪혔다.
    #   먼저 등록되고 Gold 까지 선 파주 쪽을 지키고 서울 쪽에 구 약칭을 붙였다.
    #   같은 지명이 여러 시에 있다는 것이 도시 축을 넣은 뒤 처음 드러난 자리다.
    "miasageori":  PageHub("miasageori",  "미아사거리",127.0301, 37.6133, 500, 700),
    "suyu":        PageHub("suyu",        "수유",      127.0255, 37.6379, 500, 700),
    "bulgwang":    PageHub("bulgwang",    "불광",      126.9303, 37.6100, 500, 700),  # 주의: top10 26.3%
    "yeonsinnae":  PageHub("yeonsinnae",  "연신내",    126.9211, 37.6192, 500, 700),
    "hwagok":      PageHub("hwagok",      "화곡",      126.8405, 37.5417, 500, 700),
    "kkachisan":   PageHub("kkachisan",   "까치산",    126.8464, 37.5322, 500, 700),
    "mokdong-yc":       PageHub("mokdong-yc",     "목동",      126.8646, 37.5261, 500, 700),
    "sanggye":     PageHub("sanggye",     "상계",      127.0734, 37.6607, 500, 700),
    "sangbong":    PageHub("sangbong",    "상봉",      127.0857, 37.5969, 500, 700),
    "oryudong":    PageHub("oryudong",    "오류동",    126.8448, 37.4944, 500, 700),
    "doksan":      PageHub("doksan",      "독산",      126.8895, 37.4660, 500, 700),  # 주의: top10 58.3%
    "cheonho":     PageHub("cheonho",     "천호",      127.1239, 37.5385, 500, 700),
}

# ── 서울 3차 확장 5거점 (2026-09-20 등재) ────────────────────────────────────
# **수집 대상 등록일 뿐 화면 노출이 아니다** — Gold 가 서기 전에는 `seoul_pages.DISTRICTS`
# 에 올리지 않는다(2차 확장과 같은 규칙).
#
# 선정 경위: 서울 TRDAR 상권영역 **전량 1,650곳**을 받아 기존 66거점 수집반경과 대조한 뒤
# (덮인 것 496 · 완전공백 297), 1km 초과로 떨어진 발달상권·관광특구 93곳을 600m 단일연결로
# 묶어 78클러스터를 만들고 **전부** §0 게이트를 실측했다 — 통과 53 · 주의 19 · 기각 6.
# 아래 5곳은 통과분 중 점포 수 상위다. 건축HUB 콜은 0이었다(상가정보만 사용).
# 근거: reports/seoul_hub_candidates_2026-09-20.json
#
# ⚠ 다섯 곳 전부 **R-ONE 공유 매핑**이다 — 서울 55개 세부상권이 기존 66거점에 이미
#   전부 배분돼 남은 정확 표본이 없다(2차 확장 12곳이 미사용 표본을 정확 매핑으로
#   가져간 것과 다르다). `rone_districts.SHARED_RONE` 참조.
SEOUL_BATCH3_HUBS: dict[str, PageHub] = {
    # 슬러그는 역명 로마자. `ydp-gucheong` 만 구 약칭을 붙였다 —
    # '구청역'은 서울에 여럿이라 단독으로는 어느 구인지 말하지 않는다.
    "bangbang":     PageHub("bangbang",     "뱅뱅사거리",   127.0315, 37.4903, 500, 700),
    "gildong":      PageHub("gildong",      "길동역",      127.1383, 37.5365, 500, 700),
    "nowon":        PageHub("nowon",        "노원역",      127.0622, 37.6555, 500, 700),
    "gurodigital":  PageHub("gurodigital",  "구로디지털단지", 126.8981, 37.4836, 500, 700),  # 주의: top10 29.0%
    "ydp-gucheong": PageHub("ydp-gucheong", "영등포구청역",  126.8909, 37.5254, 500, 700),  # 주의: top10 25.8%
}

# ── 서울 4차 확장 10거점 (2026-09-20 등재) ───────────────────────────────────
# 3차와 같은 후보 풀에서 이어 뽑았다. 다만 게이트를 **정식 지표로 다시 쟀다** —
# 3차 등재 때 쓴 프로브는 분자에서 사무실형 업종과 bldMngNo 결측을 빼고 세어
# 건물당 점포를 1.1~1.8배 **낮게** 냈다. 저장소 기준은 `scripts/chain_status.py:188`
# 의 **전체 점포 / bldMngNo 보유 건물**이다(고양 라페스타 37.4 도 이 기준).
# 재측정 결과 통과 53 → 51. 강등 2곳(gurodigital top10 29.0% · ydp-gucheong 25.8%)은
# 밀집이 아니라 집중도라 3차에 그대로 두고 주의 표기만 달았다.
# 근거: reports/seoul_hub_candidates_canonical_2026-09-20.json
#
# 아래 10곳은 정식 지표 통과분 중 점포 전량 상위다. R-ONE 은 3차와 같은 이유로
# **전부 공유 매핑**이다 — 서울 55개 정확 표본에 남은 자리가 없다.
SEOUL_BATCH4_HUBS: dict[str, PageHub] = {
    "seochoyeok":   PageHub("seochoyeok",   "서초역",      127.0086, 37.4915, 500, 700),  # 건물당 9.5 — 기준(10) 바로 아래
    "poi":          PageHub("poi",          "포이사거리",   127.0423, 37.4782, 500, 700),
    "dogok":        PageHub("dogok",        "도곡동",      127.0399, 37.4926, 500, 700),
    "yangjae":      PageHub("yangjae",      "양재역",      127.0340, 37.4845, 500, 700),
    "jamsil-tour":  PageHub("jamsil-tour",  "잠실 관광특구", 127.1143, 37.5162, 500, 700),
    "daerim":       PageHub("daerim",       "대림역",      126.8978, 37.4941, 500, 700),
    "guui":         PageHub("guui",         "구의역",      127.0849, 37.5375, 500, 700),
    "maebong":      PageHub("maebong",      "매봉역",      127.0439, 37.4844, 500, 700),
    "gurojeonhwa":  PageHub("gurojeonhwa",  "구로전화국",   126.9054, 37.4799, 500, 700),
    "bonseobu":     PageHub("bonseobu",     "본서부병원",   126.9190, 37.5996, 500, 700),
}

# ── 경기 확장 거점 (2026-08-29 등재 · 2026-10-26 서빙 재개) ─────────────────────
# 등록은 화면 노출이 아니다. Gold 산출물이 서기 전에는 API 거점 목록에 오르지 않는다 —
# 시드 zones/units 를 지어내지 않기 위해서다. 좌표·반경 근거와 선정 기준은
# docs/plan-gyeonggi-expansion-2026-08-29.md.
#
# 2026-10-26 사용자 결정(docs/decision-goyang-paju-corridor-2026-10-26.md):
#   · 고양·파주를 서빙한다. 단 **신규 확장에서는 계획상가·단일시설을 뺀다** — 그 11곳은
#     `deferred` 로 표기해 등록·수집·Gold 는 남기고 서빙·기본 순회에서만 뺀다(추후 확장 과제).
#   · 08-30 의 라페스타·웨스턴돔 예외 서빙 판단은 이 결정으로 대체됐다. 두 상권은 계속
#     각자의 중심·반경과 Gold 산출물을 갖는다(재개할 때 다시 받지 않게).
GYEONGGI_HUBS: dict[str, PageHub] = {
    "hwajeong":  PageHub("hwajeong",  "화정",       126.8330, 37.6350, 500, 700, city="goyang",
                          caveat="대표값 한계 — 집합 호실 비중이 80%를 넘는다. 공실률은 "
                                 "일반건축물 표본에 근거한다.",
                          deferred="계획상가"),
    # 좌표는 카카오 로컬에서 공식 도로명주소를 대조했다(라페스타 중앙로 1305-56,
    # 웨스턴돔 정발산로 24). 350m 점포 프로브의 건물 id 중복은 2동뿐이라 별도 판정한다.
    # 2026-08-30 에는 계획상가 밀집을 밝힌 채 예외 서빙하기로 했다가, 2026-10-26 결정으로
    # 신규 확장에서는 계획상가를 빼고 추후 확장 과제로 돌렸다(deferred). 문구는 그 판단의
    # 근거라 지우지 않는다.
    "ilsan":     PageHub("ilsan",     "일산 라페스타", 126.768308, 37.661029, 250, 350,
                          city="goyang",
                          caveat="계획상가 밀집 — 일반 채택 기준(건물당 점포 10개 이하)을 넘는다. "
                                 "공실률은 일반건축물 표본에만 근거하므로 다른 거점과 직접 "
                                 "비교하지 말 것.",
                          deferred="계획상가"),
    "westerndom": PageHub("westerndom", "일산 웨스턴돔", 126.772184, 37.655885, 250, 350,
                          city="goyang",
                          caveat="계획상가 밀집 — 일반 채택 기준(건물당 점포 10개 이하)을 넘는다. "
                                 "공실률은 일반건축물 표본에만 근거하므로 다른 거점과 직접 "
                                 "비교하지 말 것.",
                          deferred="계획상가"),
    "geumchon":  PageHub("geumchon",  "금촌",       126.7740, 37.7600, 500, 700, city="paju"),
    "unjeong":   PageHub("unjeong",   "운정",       126.7660, 37.7220, 500, 700, city="paju"),
    # 야당역 경의중앙선(소리천로 10) 중심 — 파주 주요 상권 판정 대상이며 운정과 합치지 않는다.
    "yadang":    PageHub("yadang",    "야당",       126.761454, 37.712611, 500, 700, city="paju"),
    # 탄현 — R-ONE `경기>탄현역` **정확 매핑** 후보(좌표는 카카오 로컬 실측:
    # 37.6940,126.7611 = 고양 일산서구. 파주 탄현면과는 12km 떨어져 있다).
    # 라페스타(ilsan)가 탄현역 앵커를 4.07km 공유로 빌려 쓰는 문제의 대안으로 등재.
    "tanhyeon":  PageHub("tanhyeon",  "탄현",       126.7611, 37.6940, 500, 700, city="goyang",
                          caveat="대표값 한계 — 집합 호실 비중이 80%를 넘는다. 공실률은 "
                                 "일반건축물 표본에 근거한다.",
                          deferred="계획상가"),

    # ── 2026-08-30 2차 확장 13거점 ────────────────────────────────────────────
    # 좌표는 전부 카카오 로컬 실측. 등록 전에 1차 프로브(상가정보만, 건축HUB 콜 0)로
    # 지표를 재고 넣었다 → docs/finding-goyang-paju-candidates-2026-08-30.md
    #
    # ⚠ 반경은 **이격 실측으로 정했다.** 겹치면 같은 점포를 두 번 센다(라페스타·웨스턴돔
    #   666m 에서 겪은 문제). 1.0km 미만 쌍만 반경을 줄였다:
    #     마두역 ↔ 웨스턴돔 629m · 대화역 ↔ 킨텍스 825m · 스타필드 ↔ 삼송역 690m
    # ⚠ 운정역은 **넣지 않았다** — 기존 `unjeong` 과 414m 라 이미 그 수집 반경 안이다.

    # 판정 통과 — 예외 표기 없이 서울과 같은 자격으로 선다
    "bamgasi":   PageHub("bamgasi",   "밤가시마을",   126.7778, 37.6743, 500, 700, city="goyang"),
    "wondang":   PageHub("wondang",   "원당역",      126.8429, 37.6531, 500, 700, city="goyang"),

    # 주의 구간 — 건물당 점포는 낮고 집중도만 높다. 대장으로 집합 비중을 확인한다
    "baekseok":  PageHub("baekseok",  "백석역",      126.7881, 37.6430, 500, 700, city="goyang"),
    "daehwa":    PageHub("daehwa",    "대화역",      126.7475, 37.6762, 350, 450, city="goyang"),
    "haengsin":  PageHub("haengsin",  "행신역",      126.8341, 37.6119, 500, 700, city="goyang"),
    "munsan":    PageHub("munsan",    "문산역",      126.7874, 37.8546, 500, 700, city="paju"),

    # 계획상가 밀집 — 건물당 점포가 기준(10)을 넘는다. 08-30 에는 라페스타와 같은 예외
    # 채택이었으나 2026-10-26 결정으로 추후 확장 과제로 돌렸다(deferred).
    "madu":      PageHub("madu",      "마두역",      126.7776, 37.6522, 250, 350, city="goyang",
                          caveat="계획상가 밀집 — 건물당 점포 17.1개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것.",
                          deferred="계획상가"),
    "juyeop":    PageHub("juyeop",    "주엽역",      126.7613, 37.6701, 500, 700, city="goyang",
                          caveat="계획상가 밀집 — 건물당 점포 22.4개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것.",
                          deferred="계획상가"),
    "mokdong":   PageHub("mokdong",   "운정 목동",    126.7330, 37.7331, 500, 700, city="paju",
                          caveat="계획상가 밀집 — 건물당 점포 10.2개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것.",
                          deferred="계획상가"),

    # 단일시설 — '상권'이 아니라 '건물'이다. 점포 대부분이 몰 한 채 안에 있어
    # (top10 지번 집중도 64~82% · 라페스타 40% 보다 높다) 거점 공실률이 건물 하나에 좌우된다.
    # 계획상가 밀집과는 **다른 종류의 예외**라 문구를 따로 쓴다.
    # ⚠ 스타필드는 건물당 점포(21.7)로도 계획상가 기준을 넘지만, 상권이 시설 한 채라는
    #   사실이 더 근본이라 단일시설로 둔다.
    "kintex":    PageHub("kintex",    "킨텍스",      126.7458, 37.6689, 350, 450, city="goyang",
                          caveat="단일시설 상권 — 점포의 69.6%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것.",
                          deferred="단일시설"),
    "starfield": PageHub("starfield", "스타필드 고양",  126.8954, 37.6471, 300, 400, city="goyang",
                          caveat="단일시설 상권 — 점포의 79.9%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것.",
                          deferred="단일시설"),
    "samsong":   PageHub("samsong",   "삼송역",      126.8957, 37.6533, 300, 400, city="goyang",
                          caveat="단일시설 상권 — 점포의 63.9%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것.",
                          deferred="단일시설"),
    "pajuoutlet": PageHub("pajuoutlet", "파주 프리미엄아울렛", 126.6963, 37.7695, 500, 700, city="paju",
                          caveat="단일시설 상권 — 점포의 82.0%가 상위 10개 지번에 몰려 있다. "
                                 "R-ONE 앵커(파주시청)와도 6.9km 떨어져 임대 대조가 약하다. "
                                 "가두 상권과 같은 축에 놓고 비교하지 말 것.",
                          deferred="단일시설"),
}

# ── 경기 3차 확장 50거점 (2026-10-28 · **등록만**) ────────────────────────────────
# 사용자 요청(10-27): 「우선 경기 거점을 59곳까지만 늘려줘」 — 59 = 경기 R-ONE 상권 40(중대형·소규모 세 표 합집합) ×
# 1.47(서울의 앵커당 거점 비). 서빙 경기 9곳에 50곳을 더한다: R-ONE 앵커 자리 35 + 앵커 근처 두 번째 거점 15(공유 매핑).
# 좌표는 카카오 로컬 실측, 판정은 상가정보 1차 프로브(건축HUB 0콜 · hub-chain §0 두 단계)
# → docs/finding-gyeonggi59-candidates-2026-10-28.md · reports/gyeonggi59_candidates_2026-10-28.json
# 계획상가 밀집(건물당 점포 >10)인 서현역·범계역·광교중앙역·동탄역·미사역은 신규 확장 규칙대로 **넣지 않았다**
# (3D 디지털 트윈 대상 후보 — CLAUDE.md §3D 디지털 트윈). 성남 원도심 다섯 곳은 서로 1km 안이라 반경을 줄였다.
# ⚠ 등록은 노출이 아니다 — 도시는 Gold·앵커 대조가 선 뒤에 ACTIVE_CITIES · SERVED_CITIES 에 넣는다.
GYEONGGI_BATCH3_HUBS: dict[str, PageHub] = {
    "suwonst": PageHub("suwonst", "수원역", 127.000095, 37.26579, 500, 700, city="suwon"),  # 주의 — top10 지번 35.8% · 건물당 4.54(대장으로 집합 비중 확인)
    "ingye": PageHub("ingye", "인계동", 127.030857, 37.261923, 500, 700, city="suwon"),
    "paldalmun": PageHub("paldalmun", "팔달문", 127.016733, 37.277562, 500, 700, city="suwon"),
    "pajang": PageHub("pajang", "수원 파장동", 126.997419, 37.310323, 500, 700, city="suwon"),
    "ajou": PageHub("ajou", "아주대삼거리", 127.044099, 37.274674, 500, 700, city="suwon"),
    "yeongtong": PageHub("yeongtong", "영통역", 127.071332, 37.251504, 500, 700, city="suwon"),  # 주의 — top10 지번 32.1% · 건물당 7.81(대장으로 집합 비중 확인)
    "moran": PageHub("moran", "모란", 127.12997, 37.434038, 250, 300, city="seongnam"),  # taepyeong과 669m — 반경을 줄였다
    "sinheung": PageHub("sinheung", "성남 신흥역", 127.147538, 37.440923, 250, 350, city="seongnam"),  # sujin과 733m — 반경을 줄였다
    "dandae": PageHub("dandae", "단대오거리", 127.15677, 37.445022, 350, 450, city="seongnam"),  # sinheung과 934m — 반경을 줄였다
    "bucheonst": PageHub("bucheonst", "부천역", 126.783083, 37.48399, 500, 700, city="bucheon"),
    "anyangst": PageHub("anyangst", "안양역", 126.922644, 37.401857, 500, 700, city="anyang"),
    "indeogwon": PageHub("indeogwon", "인덕원", 126.97668, 37.401494, 500, 700, city="anyang"),  # 주의 — top10 지번 43.7% · 건물당 5.78(대장으로 집합 비중 확인)
    "uijeongbust": PageHub("uijeongbust", "의정부역", 127.04612, 37.73788, 500, 700, city="uijeongbu"),
    "pyeongtaekst": PageHub("pyeongtaekst", "평택역", 127.08557, 36.990645, 500, 700, city="pyeongtaek"),
    "pyeongtaekcity": PageHub("pyeongtaekcity", "평택시청", 127.112688, 36.992261, 500, 700, city="pyeongtaek"),
    "songtan": PageHub("songtan", "송탄(신장·지산·서정)", 127.052927, 37.057043, 500, 700, city="pyeongtaek"),
    "guri": PageHub("guri", "구리역", 127.143351, 37.603269, 500, 700, city="guri"),  # 주의 — top10 지번 26.2% · 건물당 4.66(대장으로 집합 비중 확인)
    "giheung": PageHub("giheung", "기흥역", 127.117046, 37.275453, 500, 700, city="yongin"),  # 주의 — top10 지번 47.7% · 건물당 7.02(대장으로 집합 비중 확인)
    "suji": PageHub("suji", "수지구청", 127.094659, 37.322493, 500, 700, city="yongin"),
    "gimnyangjang": PageHub("gimnyangjang", "김량장동", 127.206315, 37.237107, 500, 700, city="yongin"),
    "byeongjeom": PageHub("byeongjeom", "병점역", 127.033202, 37.206755, 500, 700, city="hwaseong"),  # 주의 — top10 지번 35.9% · 건물당 5.36(대장으로 집합 비중 확인)
    "bongdam": PageHub("bongdam", "화성 봉담읍", 126.949542, 37.220067, 500, 700, city="hwaseong"),  # 주의 — top10 지번 29.3% · 건물당 3.21(대장으로 집합 비중 확인)
    "osan": PageHub("osan", "오산시청", 127.077524, 37.149877, 500, 700, city="osan"),
    "icheon": PageHub("icheon", "이천종합터미널", 127.446936, 37.277421, 500, 700, city="icheon"),
    "yeoju": PageHub("yeoju", "여주시청", 127.637059, 37.298423, 500, 700, city="yeoju"),
    "pocheon": PageHub("pocheon", "포천터미널", 127.203941, 37.897431, 500, 700, city="pocheon"),
    "songu": PageHub("songu", "포천 송우리", 127.143992, 37.831614, 500, 700, city="pocheon"),
    "dongducheon": PageHub("dongducheon", "동두천중앙역", 127.056423, 37.901781, 500, 700, city="dongducheon"),
    "deokjeong": PageHub("deokjeong", "덕정역", 127.061559, 37.843188, 500, 700, city="yangju"),
    "hanam": PageHub("hanam", "하남 원도심", 127.20353, 37.54181, 500, 700, city="hanam"),
    "gyeongan": PageHub("gyeongan", "경기광주 경안동", 127.25703, 37.408858, 500, 700, city="gwangju-gg"),
    "gwangnam": PageHub("gwangnam", "광주 광남동", 127.228933, 37.39435, 500, 700, city="gwangju-gg"),
    "cheolsan": PageHub("cheolsan", "철산역", 126.868211, 37.476193, 500, 700, city="gwangmyeong"),
    "sincheonst": PageHub("sincheonst", "시흥 신천역", 126.786785, 37.439246, 500, 700, city="siheung"),
    "anseong": PageHub("anseong", "안성 서인사거리", 127.2702, 37.006661, 500, 700, city="anseong"),
    "songnae": PageHub("songnae", "송내역", 126.753159, 37.487641, 500, 700, city="bucheon"),  # 주의 — top10 지번 28.7% · 건물당 5.9(대장으로 집합 비중 확인)
    "yeokgok": PageHub("yeokgok", "역곡역", 126.812059, 37.485315, 500, 700, city="bucheon"),
    "sinjungdong": PageHub("sinjungdong", "신중동역", 126.776898, 37.502952, 500, 700, city="bucheon"),
    "myeonghak": PageHub("myeonghak", "명학역", 126.935593, 37.38446, 500, 700, city="anyang"),
    "sujin": PageHub("sujin", "수진역", 127.140535, 37.437378, 250, 350, city="seongnam"),  # sinheung과 733m — 반경을 줄였다
    "taepyeong": PageHub("taepyeong", "태평역", 127.12775, 37.439789, 250, 300, city="seongnam"),  # moran과 669m — 반경을 줄였다
    "yatap": PageHub("yatap", "야탑역", 127.128743, 37.411374, 500, 700, city="seongnam"),  # 주의 — top10 지번 34.0% · 건물당 7.35(대장으로 집합 비중 확인)
    "jeongja": PageHub("jeongja", "정자역", 127.108097, 37.366174, 500, 700, city="seongnam"),  # 주의 — top10 지번 28.7% · 건물당 8.99(대장으로 집합 비중 확인)
    "skku": PageHub("skku", "성균관대역", 126.971022, 37.300329, 500, 700, city="suwon"),
    "maetan": PageHub("maetan", "매탄동", 127.040809, 37.252506, 500, 700, city="suwon"),
    "ganeung": PageHub("ganeung", "가능역", 127.044288, 37.748396, 500, 700, city="uijeongbu"),
    "osanst": PageHub("osanst", "오산역", 127.066815, 37.145528, 500, 700, city="osan"),
    "gyomun": PageHub("gyomun", "구리 교문사거리", 127.130595, 37.600781, 500, 700, city="guri"),
    "gwangmyeongsa": PageHub("gwangmyeongsa", "광명사거리역", 126.854874, 37.479298, 500, 700, city="gwangmyeong"),
    "jukjeon": PageHub("jukjeon", "죽전역", 127.107505, 37.324377, 500, 700, city="yongin"),  # 주의 — top10 지번 46.5% · 건물당 5.56(대장으로 집합 비중 확인)
}

# ── 광주광역시 13곳 (2026-10-30 · **등록만** — 서빙·Gold 는 대장 수집·앵커 대조 뒤) ───────────────────────────
# R-ONE 광주 상권 13곳(중대형·소규모 공실·소규모 임대 세 표의 합집합 · 2026Q2) 각각을 한 후보로 둔다. 중심은 그 상권의
# 공공시설·역·대학의 V-World 검색 좌표이지 **R-ONE 상권 경계가 아니다**(조사 중심) — 겹치는 반경은 절반으로 줄였다.
# → docs/finding-gwangju-collection-2026-10-28.md · reports/gwangju_candidates_collection_2026-10-28.json
# ⚠ 상무지구·어룡동·용봉동·전남대는 top10 지번 집중도 >25% 라 대장으로 집합 비중을 확인한 뒤 판정한다.
# 용봉동·전남대(중심 416m)는 PlaceOS 의 시작점이라 빼지 않는다(2026-10-31 사용자 결정). 겹침을 피하려고 반경을 207m 로 줄였더니
#   1km 안 점포 2,505곳 중 313곳만 담겨 상가가 잘렸다 → 반경을 350m 로 되돌리고 겹친 점포·건물은 중심이 가까운 쪽에만 담는다
#   (점포 반경은 폴리곤 사각형 대각 350×√2 ≈ 495m — 커버리지 ⊇ 원칙. 350 이면 모서리 건물이 점포 없이 「빈 건물」로 찍혔다 · 리뷰)
#   (`partition_with`). 둘 다 서빙 상권 중 건물이 적어 「표본 소형」 문구를 단다(app/data/hub_caveats.SMALL_SAMPLE).
# ⚠ 점포 `bldMngNo` 는 옛 코드(29xxx) · `lnoCd`·PNU 는 새 코드(12xxx) — 대장은 lnoCd 로 부르므로 새 코드만 쓰고, 조인율은 거점마다 센다.
GWANGJU_HUBS: dict[str, PageHub] = {
    "gj-chungjang": PageHub("gj-chungjang", "광주 금남로/충장로", 126.917103, 35.147591, 500, 659, city="gwangju"),  # 동구 · 점포 3,365 · 건물 1,202 · 1차 통과
    "gj-geumho": PageHub("gj-geumho", "광주 금호지구", 126.857148, 35.135181, 500, 700, city="gwangju"),  # 서구 · 점포 1,134 · 건물 371 · 1차 통과
    "gj-bongseon": PageHub("gj-bongseon", "광주 봉선동", 126.915886, 35.123276, 500, 700, city="gwangju"),  # 남구 · 점포 1,213 · 건물 336 · 1차 통과
    "gj-sangmu": PageHub("gj-sangmu", "광주 상무지구", 126.848925, 35.146781, 500, 700, city="gwangju"),  # 서구 · 점포 1,938 · 건물 399 · 주의(대장 확인)
    "gj-songjeong": PageHub("gj-songjeong", "광주 송정동지구", 126.790904, 35.137703, 500, 700, city="gwangju"),  # 광산구 · 점포 949 · 건물 475 · 1차 통과
    "gj-yangsan": PageHub("gj-yangsan", "광주 양산지구", 126.879642, 35.209166, 500, 700, city="gwangju"),  # 북구 · 점포 1,150 · 건물 394 · 1차 통과
    "gj-eoryong": PageHub("gj-eoryong", "광주 어룡동", 126.779895, 35.148413, 500, 700, city="gwangju"),  # 광산구 · 점포 318 · 건물 97 · 주의(대장 확인)
    "gj-yongbong": PageHub("gj-yongbong", "광주 용봉동", 126.901176, 35.180400, 350, 495, city="gwangju", partition_with=("gj-chonnam",)),  # 북구 · 점포 186 · 건물 102 · 주의(대장 확인)
    "gj-usan": PageHub("gj-usan", "광주 우산동", 126.807058, 35.160216, 500, 700, city="gwangju"),  # 광산구 · 점포 958 · 건물 269 · 1차 통과
    "gj-wolsan": PageHub("gj-wolsan", "광주 월산동지구", 126.902621, 35.147544, 500, 659, city="gwangju"),  # 남구 · 점포 797 · 건물 386 · 1차 통과
    "gj-ilgok": PageHub("gj-ilgok", "광주 일곡동", 126.897277, 35.206029, 500, 700, city="gwangju"),  # 북구 · 점포 1,074 · 건물 402 · 1차 통과
    "gj-chonnam": PageHub("gj-chonnam", "광주 전남대", 126.903460, 35.177157, 350, 495, city="gwangju", partition_with=("gj-yongbong",)),  # 북구 · 점포 127 · 건물 61 · 주의(대장 확인)
    "gj-cheomdan1": PageHub("gj-cheomdan1", "광주 첨단1지구", 126.842364, 35.219527, 500, 700, city="gwangju"),  # 광산구 · 점포 1,577 · 건물 315 · 1차 통과
}

# 전주 5곳 — V-World 시설 중심 조사 반경. Gold 검증 후 2026-11-03 사용자 지시로 공개.
JEONJU_HUBS: dict[str, PageHub] = {
    "jj-east": PageHub("jj-east", "전주 전주동부", 127.14782445148437, 35.824307653725654, 425, 425, city="jeonju"),
    "jj-west": PageHub("jj-west", "전주 전주서부", 127.11530577621733, 35.83102037671569, 500, 700, city="jeonju"),
    "jj-newtown": PageHub("jj-newtown", "전주 전주서부신시가지", 127.10152249976325, 35.81772020277232, 500, 700, city="jeonju"),
    "jj-hanok": PageHub("jj-hanok", "전주 전주한옥마을", 127.15366129982053, 35.818290201122394, 425, 425, city="jeonju"),
    "jj-songcheon": PageHub("jj-songcheon", "전주 송천동", 127.1210250001584, 35.85713199864467, 500, 700, city="jeonju"),
}

# ── 광주·전주 2차 51곳 (2026-11-09 · **등록** — 서빙은 Gold·앵커를 통과한 거점만 `GJ_JJ_BATCH2_SERVED_HUBS` 로) ──
# 출처: 광주·전주 탐색 위치 206곳(인허가 관측점 700m 조사 원 · 대장 원본 완주 · 대장 Gold 206/206 검증)
#   reports/regional_hub_candidates_2026-11-03.json · reports/jeonju_requested_areas_2026-11-06.json
# 선정(2026-11-09 사용자 결정 「점포 300 이상 · 51곳」): 700m 점포 ≥300 · 건물당 점포 ≤10(밀집 검토 제외) ·
#   기존 거점·서로 간 중심 1km 이상 — 점포 많은 순으로 탐욕 선택. 「주의」(top10 지번 >25%)는 대장으로 확인한 뒤 판정한다.
# 중심은 일반음식점 인허가 관측점(조사 중심)이지 **상권 경계가 아니다**. 이름은 기존 R-ONE 상권명과 헷갈리지 않게 「도시 구 동」.
# R-ONE 표본이 없어 앵커는 가장 가까운 광주·전주 R-ONE 상권을 공유한다(rone_districts.SHARED_RONE).
# ⚠ 이 51곳은 등록만으로는 서빙되지 않는다 — ACTIVE_HUBS 가 `GJ_JJ_BATCH2_SERVED_HUBS` 로 거른다(경기 3차와 같은 장치).
# → docs/decision-gwangju-jeonju-batch2-2026-11-09.md
GWANGJU_BATCH2_HUBS: dict[str, PageHub] = {
    "gj-gyerim": PageHub("gj-gyerim", "광주 동구 계림동", 126.916226, 35.158808, 500, 700, city="gwangju"),  # 동구 · 점포 1,997 · 건물 1,007 · 건물당 1.98 · top10 20.43% · 통과 · 조사 research-0d6a2980d206
    "gj-jisan": PageHub("gj-jisan", "광주 동구 지산동", 126.93001, 35.14807, 500, 700, city="gwangju"),  # 동구 · 점포 1,975 · 건물 1,012 · 건물당 1.95 · top10 8.35% · 통과 · 조사 research-480477add26a
    "gj-usan-buk": PageHub("gj-usan-buk", "광주 북구 우산동", 126.918346, 35.172444, 500, 700, city="gwangju"),  # 북구 · 점포 1,884 · 건물 914 · 건물당 2.06 · top10 11.2% · 통과 · 조사 research-cd44c439bee8
    "gj-ssangchon": PageHub("gj-ssangchon", "광주 서구 쌍촌동", 126.858916, 35.151462, 500, 700, city="gwangju"),  # 서구 · 점포 1,832 · 건물 777 · 건물당 2.36 · top10 9.99% · 통과 · 조사 research-d3fcc1ea3eb6
    "gj-yudong": PageHub("gj-yudong", "광주 북구 유동", 126.903151, 35.159476, 500, 700, city="gwangju"),  # 북구 · 점포 1,647 · 건물 787 · 건물당 2.09 · top10 23.13% · 통과 · 조사 research-87fef559bfbe
    "gj-suwan": PageHub("gj-suwan", "광주 광산구 수완동", 126.825608, 35.191628, 500, 700, city="gwangju"),  # 광산구 · 점포 1,624 · 건물 414 · 건물당 3.92 · top10 23.77% · 통과 · 조사 research-f18e1be4c888
    "gj-nongseong": PageHub("gj-nongseong", "광주 서구 농성동", 126.885338, 35.152395, 500, 700, city="gwangju"),  # 서구 · 점포 1,566 · 건물 731 · 건물당 2.14 · top10 20.63% · 통과 · 조사 research-a537e60212fc
    "gj-wolgok": PageHub("gj-wolgok", "광주 광산구 월곡동", 126.807377, 35.171372, 500, 700, city="gwangju"),  # 광산구 · 점포 1,553 · 건물 764 · 건물당 2.03 · top10 8.82% · 통과 · 조사 research-aa198661e1ba
    "gj-baegun": PageHub("gj-baegun", "광주 남구 백운동", 126.900469, 35.136784, 500, 700, city="gwangju"),  # 남구 · 점포 1,544 · 건물 795 · 건물당 1.94 · top10 13.34% · 통과 · 조사 research-6f147ceb2d99
    "gj-wolsan-nam": PageHub("gj-wolsan-nam", "광주 남구 월산동", 126.889549, 35.143903, 500, 700, city="gwangju"),  # 남구 · 점포 1,455 · 건물 808 · 건물당 1.8 · top10 9.48% · 통과 · 조사 research-65870e1377cd
    "gj-unam": PageHub("gj-unam", "광주 북구 운암동", 126.874331, 35.176769, 500, 700, city="gwangju"),  # 북구 · 점포 1,226 · 건물 434 · 건물당 2.82 · top10 13.95% · 통과 · 조사 research-ee2001012de0
    "gj-gwangcheon": PageHub("gj-gwangcheon", "광주 서구 광천동", 126.878637, 35.161839, 500, 700, city="gwangju"),  # 서구 · 점포 1,221 · 건물 314 · 건물당 3.89 · top10 51.02% · 주의 · 조사 research-ea16871ac664
    "gj-hwajeong": PageHub("gj-hwajeong", "광주 서구 화정동", 126.874966, 35.147181, 500, 700, city="gwangju"),  # 서구 · 점포 1,205 · 건물 609 · 건물당 1.98 · top10 9.13% · 통과 · 조사 research-f3aa418a9d09
    "gj-yangnim": PageHub("gj-yangnim", "광주 남구 양림동", 126.912549, 35.138832, 500, 700, city="gwangju"),  # 남구 · 점포 1,093 · 건물 676 · 건물당 1.62 · top10 7.04% · 통과 · 조사 research-75ddbe7f8054
    "gj-munheung": PageHub("gj-munheung", "광주 북구 문흥동", 126.919255, 35.184672, 500, 700, city="gwangju"),  # 북구 · 점포 1,061 · 건물 490 · 건물당 2.17 · top10 14.23% · 통과 · 조사 research-1dc1323ab5b3
    "gj-heukseok": PageHub("gj-heukseok", "광주 광산구 흑석동", 126.806597, 35.181369, 500, 700, city="gwangju"),  # 광산구 · 점포 1,005 · 건물 331 · 건물당 3.04 · top10 24.98% · 통과 · 조사 research-3f3c932eeb3d
    "gj-sinyong": PageHub("gj-sinyong", "광주 북구 신용동", 126.860236, 35.208759, 500, 700, city="gwangju"),  # 북구 · 점포 981 · 건물 141 · 건물당 6.96 · top10 42.61% · 주의 · 조사 research-c791893737b7
    "gj-jangdeok": PageHub("gj-jangdeok", "광주 광산구 장덕동", 126.811617, 35.191905, 500, 700, city="gwangju"),  # 광산구 · 점포 912 · 건물 293 · 건물당 3.11 · top10 17.65% · 통과 · 조사 research-494b10969020
    "gj-dongcheon": PageHub("gj-dongcheon", "광주 서구 동천동", 126.862361, 35.170043, 500, 700, city="gwangju"),  # 서구 · 점포 911 · 건물 282 · 건물당 3.23 · top10 20.53% · 통과 · 조사 research-6ce56f421f26
    "gj-gakhwa": PageHub("gj-gakhwa", "광주 북구 각화동", 126.931315, 35.182404, 500, 700, city="gwangju"),  # 북구 · 점포 888 · 건물 461 · 건물당 1.93 · top10 20.38% · 통과 · 조사 research-dc21ef2315a9
    "gj-hakdong": PageHub("gj-hakdong", "광주 동구 학동", 126.924057, 35.135341, 500, 700, city="gwangju"),  # 동구 · 점포 795 · 건물 416 · 건물당 1.91 · top10 19.37% · 통과 · 조사 research-7fabf07f0201
    "gj-jinwol": PageHub("gj-jinwol", "광주 남구 진월동", 126.895074, 35.118806, 500, 700, city="gwangju"),  # 남구 · 점포 772 · 건물 280 · 건물당 2.76 · top10 18.78% · 통과 · 조사 research-1521999833d1
    "gj-sotae": PageHub("gj-sotae", "광주 동구 소태동", 126.930369, 35.126993, 500, 700, city="gwangju"),  # 동구 · 점포 640 · 건물 337 · 건물당 1.9 · top10 14.84% · 통과 · 조사 research-0422a3ecdea5
    "gj-pungam": PageHub("gj-pungam", "광주 서구 풍암동", 126.871787, 35.124892, 500, 700, city="gwangju"),  # 서구 · 점포 628 · 건물 259 · 건물당 2.42 · top10 20.86% · 통과 · 조사 research-90108ace326c
    "gj-sanwol": PageHub("gj-sanwol", "광주 광산구 산월동", 126.846596, 35.207792, 500, 700, city="gwangju"),  # 광산구 · 점포 519 · 건물 150 · 건물당 3.46 · top10 38.92% · 주의 · 조사 research-cf5c25b0e4f7
    "gj-maegok": PageHub("gj-maegok", "광주 북구 매곡동", 126.889677, 35.18931, 500, 700, city="gwangju"),  # 북구 · 점포 500 · 건물 150 · 건물당 3.33 · top10 23.6% · 통과 · 조사 research-a277ddde3c67
    "gj-sinchon": PageHub("gj-sinchon", "광주 광산구 신촌동", 126.801338, 35.144166, 500, 700, city="gwangju"),  # 광산구 · 점포 479 · 건물 296 · 건물당 1.62 · top10 12.73% · 통과 · 조사 research-4264ab930f5b
    "gj-imam": PageHub("gj-imam", "광주 남구 임암동", 126.871609, 35.102345, 500, 700, city="gwangju"),  # 남구 · 점포 414 · 건물 86 · 건물당 4.81 · top10 38.41% · 주의 · 조사 research-ded6e8ebd90b
    "gj-bia": PageHub("gj-bia", "광주 광산구 비아동", 126.820466, 35.221589, 500, 700, city="gwangju"),  # 광산구 · 점포 397 · 건물 231 · 건물당 1.72 · top10 20.15% · 통과 · 조사 research-c8eb401a7a53
    "gj-nodae": PageHub("gj-nodae", "광주 남구 노대동", 126.902133, 35.105421, 500, 700, city="gwangju"),  # 남구 · 점포 332 · 건물 84 · 건물당 3.95 · top10 41.27% · 주의 · 조사 research-d8d6e8d988b8
}

JEONJU_BATCH2_HUBS: dict[str, PageHub] = {
    "jj-jungang4": PageHub("jj-jungang4", "전주 완산구 중앙동4가", 127.141936, 35.815449, 500, 700, city="jeonju"),  # 완산구 · 점포 2,178 · 건물 1,146 · 건물당 1.9 · top10 9.04% · 통과 · 조사 research-32e5c073c38e
    "jj-junghwasan2": PageHub("jj-junghwasan2", "전주 완산구 중화산동2가", 127.116738, 35.817889, 500, 700, city="jeonju"),  # 완산구 · 점포 2,089 · 건물 883 · 건물당 2.37 · top10 10.2% · 통과 · 조사 research-d6bf3c9b9146
    "jj-ua2": PageHub("jj-ua2", "전주 덕진구 우아동2가", 127.168477, 35.832027, 500, 700, city="jeonju"),  # 덕진구 · 점포 1,613 · 건물 801 · 건물당 2.01 · top10 5.02% · 통과 · 조사 research-3d1aec00858a
    "jj-geumam": PageHub("jj-geumam", "전주 덕진구 금암동", 127.132113, 35.840226, 500, 700, city="jeonju"),  # 덕진구 · 점포 1,463 · 건물 680 · 건물당 2.15 · top10 11.69% · 통과 · 조사 research-97bd6aec8139
    "jj-samcheon1": PageHub("jj-samcheon1", "전주 완산구 삼천동1가", 127.116382, 35.796827, 500, 700, city="jeonju"),  # 완산구 · 점포 1,333 · 건물 662 · 건물당 2.01 · top10 9.38% · 통과 · 조사 research-ecb5bb327522
    "jj-jungdong": PageHub("jj-jungdong", "전주 덕진구 중동", 127.057069, 35.836727, 500, 700, city="jeonju"),  # 덕진구 · 점포 1,301 · 건물 232 · 건물당 5.61 · top10 22.67% · 통과 · 조사 research-64b3486bda70
    "jj-songcheon2": PageHub("jj-songcheon2", "전주 덕진구 송천동2가", 127.123329, 35.869984, 500, 700, city="jeonju"),  # 덕진구 · 점포 1,194 · 건물 336 · 건물당 3.55 · top10 18.43% · 통과 · 조사 research-dc3354a751ab
    "jj-hyoja1": PageHub("jj-hyoja1", "전주 완산구 효자동1가", 127.115969, 35.806752, 500, 700, city="jeonju"),  # 완산구 · 점포 1,123 · 건물 428 · 건물당 2.62 · top10 20.57% · 통과 · 조사 research-540803c79d05
    "jj-pyeonghwa1": PageHub("jj-pyeonghwa1", "전주 완산구 평화동1가", 127.132861, 35.795043, 500, 700, city="jeonju"),  # 완산구 · 점포 1,100 · 건물 544 · 건물당 2.02 · top10 9.0% · 통과 · 조사 research-f137b90e1559
    "jj-hyoja2": PageHub("jj-hyoja2", "전주 완산구 효자동2가", 127.10068, 35.808664, 500, 700, city="jeonju"),  # 점포 1,094 · 건물 500 · 건물당 2.19 · top10 9.23% · 통과 · 조사 research-request-b8f3094b6586
    "jj-dongseohak": PageHub("jj-dongseohak", "전주 완산구 동서학동", 127.150606, 35.808641, 500, 700, city="jeonju"),  # 완산구 · 점포 1,030 · 건물 652 · 건물당 1.58 · top10 13.11% · 통과 · 조사 research-07d6a6a59621
    "jj-junghwasan1": PageHub("jj-junghwasan1", "전주 완산구 중화산동1가", 127.129082, 35.813299, 500, 700, city="jeonju"),  # 완산구 · 점포 949 · 건물 485 · 건물당 1.96 · top10 8.75% · 통과 · 조사 research-08f6609cc990
    "jj-ua3": PageHub("jj-ua3", "전주 덕진구 우아동3가", 127.153715, 35.848845, 500, 700, city="jeonju"),  # 덕진구 · 점포 948 · 건물 486 · 건물당 1.95 · top10 13.5% · 통과 · 조사 research-5e1b321994ff
    "jj-hyoja3": PageHub("jj-hyoja3", "전주 완산구 효자동3가", 127.098925, 35.8326, 500, 700, city="jeonju"),  # 점포 789 · 건물 476 · 건물당 1.66 · top10 9.76% · 통과 · 조사 research-request-c0cbf6b2f92a
    "jj-manseong": PageHub("jj-manseong", "전주 덕진구 만성동", 127.073096, 35.843454, 500, 700, city="jeonju"),  # 덕진구 · 점포 785 · 건물 182 · 건물당 4.31 · top10 23.82% · 통과 · 조사 research-ca2e48224f8f
    "jj-inhu2": PageHub("jj-inhu2", "전주 덕진구 인후동2가", 127.145072, 35.842049, 500, 700, city="jeonju"),  # 덕진구 · 점포 784 · 건물 455 · 건물당 1.72 · top10 13.01% · 통과 · 조사 research-b6145a229665
    "jj-yeoui2": PageHub("jj-yeoui2", "전주 덕진구 여의동2가", 127.076645, 35.871835, 500, 700, city="jeonju"),  # 덕진구 · 점포 684 · 건물 308 · 건물당 2.22 · top10 17.98% · 통과 · 조사 research-322f11af42a6
    "jj-deokjin2": PageHub("jj-deokjin2", "전주 덕진구 덕진동2가", 127.109092, 35.844677, 500, 700, city="jeonju"),  # 덕진구 · 점포 523 · 건물 221 · 건물당 2.37 · top10 17.02% · 통과 · 조사 research-67312fb62d44
    "jj-ecocity": PageHub("jj-ecocity", "전주 에코시티", 127.134449, 35.870602, 500, 700, city="jeonju"),  # 점포 500 · 건물 133 · 건물당 3.76 · top10 32.2% · 주의 · 조사 research-request-45ca584a30cc
    "jj-hoseong1": PageHub("jj-hoseong1", "전주 덕진구 호성동1가", 127.150583, 35.860749, 500, 700, city="jeonju"),  # 덕진구 · 점포 432 · 건물 126 · 건물당 3.43 · top10 24.07% · 통과 · 조사 research-7edf319f0fac
    "jj-hyoja2-south": PageHub("jj-hyoja2-south", "전주 완산구 효자동2가 남부", 127.101517, 35.797508, 500, 700, city="jeonju"),  # 점포 355 · 건물 99 · 건물당 3.59 · top10 36.06% · 주의 · 조사 research-request-b96238fbf8b6
}

GJ_JJ_BATCH2_HUBS: dict[str, PageHub] = {**GWANGJU_BATCH2_HUBS, **JEONJU_BATCH2_HUBS}

# 거점 ↔ 그 거점이 된 조사 위치(data/gold/platform_research_locations.json 의 id). 서빙에 오른 거점의 조사 위치는
# 지도 「조사 위치」 레이어에서 빠진다(docs/decision-research-locations-layer-2026-11-09.md §5 — 같은 자리를 두 번 그리지 않는다).
GJ_JJ_BATCH2_RESEARCH_ID: dict[str, str] = {
    "gj-gyerim": "research-0d6a2980d206",
    "gj-jisan": "research-480477add26a",
    "gj-usan-buk": "research-cd44c439bee8",
    "gj-ssangchon": "research-d3fcc1ea3eb6",
    "gj-yudong": "research-87fef559bfbe",
    "gj-suwan": "research-f18e1be4c888",
    "gj-nongseong": "research-a537e60212fc",
    "gj-wolgok": "research-aa198661e1ba",
    "gj-baegun": "research-6f147ceb2d99",
    "gj-wolsan-nam": "research-65870e1377cd",
    "gj-unam": "research-ee2001012de0",
    "gj-gwangcheon": "research-ea16871ac664",
    "gj-hwajeong": "research-f3aa418a9d09",
    "gj-yangnim": "research-75ddbe7f8054",
    "gj-munheung": "research-1dc1323ab5b3",
    "gj-heukseok": "research-3f3c932eeb3d",
    "gj-sinyong": "research-c791893737b7",
    "gj-jangdeok": "research-494b10969020",
    "gj-dongcheon": "research-6ce56f421f26",
    "gj-gakhwa": "research-dc21ef2315a9",
    "gj-hakdong": "research-7fabf07f0201",
    "gj-jinwol": "research-1521999833d1",
    "gj-sotae": "research-0422a3ecdea5",
    "gj-pungam": "research-90108ace326c",
    "gj-sanwol": "research-cf5c25b0e4f7",
    "gj-maegok": "research-a277ddde3c67",
    "gj-sinchon": "research-4264ab930f5b",
    "gj-imam": "research-ded6e8ebd90b",
    "gj-bia": "research-c8eb401a7a53",
    "gj-nodae": "research-d8d6e8d988b8",
    "jj-jungang4": "research-32e5c073c38e",
    "jj-junghwasan2": "research-d6bf3c9b9146",
    "jj-ua2": "research-3d1aec00858a",
    "jj-geumam": "research-97bd6aec8139",
    "jj-samcheon1": "research-ecb5bb327522",
    "jj-jungdong": "research-64b3486bda70",
    "jj-songcheon2": "research-dc3354a751ab",
    "jj-hyoja1": "research-540803c79d05",
    "jj-pyeonghwa1": "research-f137b90e1559",
    "jj-hyoja2": "research-request-b8f3094b6586",
    "jj-dongseohak": "research-07d6a6a59621",
    "jj-junghwasan1": "research-08f6609cc990",
    "jj-ua3": "research-5e1b321994ff",
    "jj-hyoja3": "research-request-c0cbf6b2f92a",
    "jj-manseong": "research-ca2e48224f8f",
    "jj-inhu2": "research-b6145a229665",
    "jj-yeoui2": "research-322f11af42a6",
    "jj-deokjin2": "research-67312fb62d44",
    "jj-ecocity": "research-request-45ca584a30cc",
    "jj-hoseong1": "research-7edf319f0fac",
    "jj-hyoja2-south": "research-request-b96238fbf8b6",
}

# 거점 id 별칭 → 정규 slug (프론트/레거시 경로 호환).
ALIASES: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
    "sinsa": "garosugil",
}


# 명시 지정용 통합 레지스트리 — **순회 대상이 아니다.**
#
# `HUBS`(서울 54)는 인자 없이 실행했을 때의 기본 순회 집합으로 그대로 둔다. 경기 거점은
# 아직 수집 전이라, 전 거점 루프에 섞이면 산출물 없는 거점이 매 실행마다 실패로 찍히고
# 거점 수를 세는 곳(coverage tier · Dockerfile 가드 · pppp_status)의 분모가 흔들린다.
# 그래서 **이름을 대고 부를 때만** 잡히게 한다.
ALL_HUBS: dict[str, PageHub] = {**HUBS, **SEOUL_BATCH2_HUBS, **SEOUL_BATCH3_HUBS,
                                **SEOUL_BATCH4_HUBS, **GYEONGGI_HUBS, **GYEONGGI_BATCH3_HUBS,
                                **GWANGJU_HUBS, **JEONJU_HUBS, **GJ_JJ_BATCH2_HUBS}

# ── 기본 순회 집합 (2026-09-03) ──────────────────────────────────────────────
# 위 주석은 "`HUBS`(서울 54)가 기본 순회 집합"이라고 적었는데, 서울 2차 12거점이
# 08-30 에 Tier1 로 서고 09-03 에 **서빙에 올라간** 뒤로는 그게 틀린 기본값이다.
# 그대로 두면 이런 일이 벌어진다(실측 09-03): 12거점이 Page Gold 는 갖고 있는데
# `platform_page_footfall` · `page_footfall_hourly` · `platform_posting_inputs` ·
# `program_content_context` 에서 **통째로 0/12** 였다. 수집이 덜 된 게 아니라
# 파이프라인이 `HUBS` 만 돌아서다.
#
# 그래서 순회 대상을 **도시**로 가른다 — 지금 산출물을 만드는 도시가 `ACTIVE_CITIES` 다.
# 2026-09-03 ~ 10-25 에는 서울뿐이었고(경기 작업 중단), 2026-10-26 에 고양·파주를 되넣었다.
#
# ⚠ 이 집합은 **서빙 목록과 같아야 한다**(`app/data/measured_pages.SERVED_CITIES`).
#   달라지면 "화면에는 뜨는데 산출물은 안 만드는" 거점이 생긴다 — 그 어긋남을
#   `tests/test_active_cities_match_serving.py` 가 잡는다. 어느 쪽을 바꾸든 둘 다 바꾼다.
# 2026-10-28: 대장 추가 호출 없이 완주한 경기 3차 거점만 서빙한다.
GYEONGGI_BATCH3_SERVED_HUBS: frozenset[str] = frozenset({
    "suwonst", "ingye", "paldalmun", "pajang", "ajou", "yeongtong",
    "moran", "sinheung", "dandae", "bucheonst", "anyangst", "indeogwon", "uijeongbust",
    # 2026-10-31 재판정 뒤 서빙(사용자 지시) — 「+33.6%p」는 집합건물을 섞은 calibration.primary 값이었다.
    # 서빙 대표값 기준은 9.5% vs R-ONE 13.11% = −3.6%p(크기 맞춤 −5.5%p) → docs/decision-gwangju-serve-2026-10-31.md §2
    "byeongjeom",
    # 2026-11-03: 서울과 같은 실측 기준으로 재검증한 경기 36곳 추가. 기존 122곳은 전부 유지한다.
    # 근거: reports/regional_hub_candidates_2026-11-03.json · tests/test_gg3_serving.py
    "pyeongtaekst", "pyeongtaekcity", "songtan", "guri", "giheung", "suji", "gimnyangjang",
    "bongdam", "osan", "icheon", "yeoju", "pocheon", "songu", "dongducheon", "deokjeong",
    "hanam", "gyeongan", "gwangnam", "cheolsan", "sincheonst", "anseong", "songnae", "yeokgok",
    "sinjungdong", "myeonghak", "sujin", "taepyeong", "yatap", "jeongja", "skku", "maetan",
    "ganeung", "osanst", "gyomun", "gwangmyeongsa", "jukjeon",
})
# 광주·전주 2차(2026-11-09 등록) — Tier1 · 정밀 커버리지 ≥80% · 서빙 대표값 앵커 격차 |gap| ≤ 30%p 를 통과한 거점만 넣는다.
# 빈 집합에서 시작한다. 넣는 근거는 docs/decision-gwangju-jeonju-batch2-2026-11-09.md 의 거점별 표다.
GJ_JJ_BATCH2_SERVED_HUBS: frozenset[str] = frozenset()

# 2026-10-31: 광주 13곳 전부 서빙(사용자 결정) — 13곳 모두 Tier1 · R-ONE 정확 매핑 · 앵커 격차 ±30%p 안.
# 2026-11-03: 사용자 지시로 검증 완료한 전주 5곳도 모두 공개한다.
ACTIVE_CITIES: frozenset[str] = frozenset({
    "seoul", "goyang", "paju", "suwon", "seongnam", "bucheon", "anyang", "uijeongbu", "gwangju", "hwaseong", "jeonju",
    "pyeongtaek", "guri", "yongin", "osan", "icheon", "yeoju", "pocheon", "dongducheon", "yangju",
    "hanam", "gwangju-gg", "gwangmyeong", "siheung", "anseong",
})

# 추후 확장 과제(`PageHub.deferred`) — 서빙 도시 안에 있어도 서빙·기본 순회에서 뺀다.
# 지우지 않고 등록·Gold 를 남기는 이유: 재개할 때 쿼터를 다시 태우지 않게.
DEFERRED_HUBS: dict[str, PageHub] = {
    slug: hub for slug, hub in ALL_HUBS.items() if hub.deferred
}

ACTIVE_HUBS: dict[str, PageHub] = {
    slug: hub for slug, hub in ALL_HUBS.items()
    if hub.city in ACTIVE_CITIES and not hub.deferred
    and (slug not in GYEONGGI_BATCH3_HUBS or slug in GYEONGGI_BATCH3_SERVED_HUBS)
    and (slug not in GJ_JJ_BATCH2_HUBS or slug in GJ_JJ_BATCH2_SERVED_HUBS)
}


def resolve(district: str) -> str | None:
    """거점 id/별칭 → 정규 slug. 미지원이면 None. 경기 거점도 여기서 잡힌다."""
    if district in ALL_HUBS:
        return district
    return ALIASES.get(district)


def get_hub(district: str) -> PageHub | None:
    """거점 id/별칭 → PageHub. 수집기·파이프라인의 CLI 진입점이 쓰는 조회구다.

    ⚠ 여기서 None 이 나오면 **조용히 건너뛰지 말 것.** 사람이 이름을 대고 부른 경우이므로
      오타이거나 미등록이다. 2026-08-30 에 `hwajeong` 을 수집하려 했을 때 수집기가
      `HUBS` 만 보고 건너뛴 뒤 exit 0 으로 끝나, 체인이 "수집 완료"로 읽었다.
    """
    slug = resolve(district)
    return ALL_HUBS.get(slug) if slug else None


def owns_point(hub: PageHub, lat: float, lon: float) -> bool:
    """이 좌표가 `hub` 의 몫인가 — `partition_with` 짝 거점보다 중심이 더 가까울 때(같으면 slug 가 앞선 쪽)만 참.

    짝이 없으면 항상 참이라 기존 거점의 수집은 한 글자도 안 바뀐다.
    """
    if not hub.partition_with:
        return True
    k = math.pi / 180

    def dist(h: PageHub) -> float:
        x = (lon - h.cx) * k * math.cos((lat + h.cy) / 2 * k)
        return math.hypot(x, (lat - h.cy) * k)

    mine = dist(hub)
    for slug in hub.partition_with:
        other = ALL_HUBS.get(slug)
        if other is None:
            continue
        theirs = dist(other)
        if theirs < mine or (theirs == mine and slug < hub.slug):
            return False
    return True
