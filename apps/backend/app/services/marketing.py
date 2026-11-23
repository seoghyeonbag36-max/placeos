"""상권 단위 마케팅 서비스 — 상권 컨텍스트(Gold) · 행사 · 온라인 콘텐츠.

2026-11-22 사용자 정의 「Program = 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」으로 **검증 프로그램 생성**
(`generate_program` · 검증 브리프 → 모객·연계·검증 지표 · LLM/규칙 스텁)과 그 입력 자료(자리 `program_site` · 브리프 `program_brief`)를 지웠다
→ docs/decision-program-post-opening-2026-11-22.md. 남은 것:

- **상권 컨텍스트**: Platform 수집 정보(상권분석 시계열·감성·블로그 키워드)를 담은 gold/program_content_context — 실행 카드의 빈 시간대(`context_rows` ·
  `_gap_band`)와 `GET /marketing/{district_id}` 의 온라인 콘텐츠가 같은 Gold 를 쓴다.
- **행사**: 서울열린데이터광장 문화행사·전국 행사 실데이터 — services/events.py 가 서빙하고 `get_district_events` 가 출처를 밝힌다(행사 연계 계획 · 지도 칩).

윤리 기준: Humanistic Authority(균형·공생·공감) — 과장·허위·특정 자본 편중 금지.
"""
from __future__ import annotations

import csv
import re
import time
from pathlib import Path

from app.core.config import settings
from app.data.seoul_pages import DISTRICTS_BY_ID
from app.schemas.marketing import LLMDistrictContents
from app.services import districts as svc
from app.services import events, ha_guard


# 상권 컨텍스트 결합용 district_id → gold 슬러그 매핑.
# 2026-08-01: 거점 id 와 gold 슬러그가 같은 54거점이 build_program13_context 로 모두
# 생성돼(garosugil 만 전용 Bronze), 표 대신 **동명 슬러그 + 파일 존재 확인**으로 푼다.
# 여기에는 id 가 슬러그와 다른 예외(별칭)만 남긴다. 새 거점을 추가하려면
# `python -m data.pipelines.build_gold --platform13` 로 Gold 만 만들면 자동 반영된다.
_DISTRICT_ALIAS: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
}

# district_id 는 요청 본문에서 오므로 경로로 쓰기 전에 형태를 제한한다(경로 이탈 방지).
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"


def _context_path(slug: str) -> Path:
    """상권 컨텍스트 CSV 경로."""
    return _GOLD_DIR / slug / "program_content_context.csv"


def _load_context_rows(slug: str) -> list[tuple[str, str, float]] | None:
    """컨텍스트 CSV 를 (kind, key, value) 행 목록으로. 없거나 깨졌으면 None.

    **표준 라이브러리로만 읽는다 — pandas 를 쓰지 않는다.** 예전에는 파케이를
    `pd.read_parquet` 로 읽었는데, 배포에는 pandas 도 pyarrow 도
    없어서 `import pandas` 가 그대로 실패했다. 그 실패는 아래 호출부의 except 에
    잡혀 컨텍스트가 **항상 None** 이 됐고, 결과적으로 상권 단위 LLM 경로가
    프로덕션에서 한 번도 돈 적이 없다(2026-08-06 발견). 화면은 시드 카피를
    보여주고 있었으므로 눈으로는 알 수 없었다.

    파케이를 되살리는 대신 산출물을 CSV 로 옮겼다 — 3열 80행짜리 표에 파케이는
    이득이 없고(실측 174KB → 116KB 로 **작아졌다**), 런타임에 읽히는 다른 Gold
    산출물은 이미 전부 JSON/GeoJSON 이라 이것만 예외였다.

    인코딩은 utf-8-sig 로 읽는다 — BOM 이 있으면 벗기고 없으면 그대로 읽으므로
    파이프라인이 어느 쪽으로 쓰든 안전하다.
    """
    path = _context_path(slug)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = []
            for r in csv.DictReader(f):
                try:
                    rows.append((r["kind"], r["key"], float(r["value"])))
                except (KeyError, TypeError, ValueError):
                    continue    # 값이 비거나 깨진 행은 건너뛴다 (전체를 버리지 않는다)
        return rows or None
    except OSError:
        return None


def context_rows(district_id: str | None) -> list[tuple[str, str, float]] | None:
    """상권 컨텍스트 CSV 를 (kind, key, value) 행으로 — **거점 id 로** 묻는 공개 입구.

    Platform(services/platform_profile)이 같은 파일을 읽되 파서를 두 벌 두지 않도록
    별칭 해석·슬러그 검증까지 여기서 한 번에 한다. 로더가 갈리면 인코딩·결측 규칙이
    조용히 달라져 두 화면이 같은 거점을 다르게 말하게 된다.
    """
    slug = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    if not _SLUG_RE.match(slug):
        return None
    return _load_context_rows(slug)


def _top_n(rows: list[tuple[str, str, float]], kind: str, n: int = 5) -> list[tuple[str, float]]:
    """해당 kind 의 상위 n건 (value 내림차순) — 예전 nlargest 대체."""
    hits = [(k, v) for kd, k, v in rows if kd == kind]
    return sorted(hits, key=lambda kv: kv[1], reverse=True)[:n]


def _district_context(district_id: str | None) -> str | None:
    """Platform Gold(program_content_context)에서 상권 컨텍스트 요약 텍스트 생성.

    거점 id 형식이 아니거나 Gold 미적재면 None (컨텍스트 없이 생성).
    """
    slug = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    if not _SLUG_RE.match(slug):
        return None
    rows = _load_context_rows(slug)
    if rows is None:
        return None

    parts: list[str] = []
    if (kw := _top_n(rows, "blog_keyword")):
        parts.append("블로그 언급 키워드: " + ", ".join(
            f"{k}({int(v)}건)" for k, v in kw))
    if (cat := _top_n(rows, "category")):
        parts.append("상권 업종 분포: " + ", ".join(
            f"{k} {int(v)}곳" for k, v in cat))

    # 트렌드는 kind 가 "trend:{이름}" 이라 이름별로 묶는다(예전 groupby 대체).
    trends: dict[str, list[tuple[str, float]]] = {}
    for kd, k, v in rows:
        if kd.startswith("trend:"):
            trends.setdefault(kd, []).append((k, v))
    summaries = [s for kd, pts in trends.items()
                 if (s := _trend_summary(kd.split(":", 1)[1], pts))]
    if summaries:
        parts.append("검색 트렌드(최근 6개월, 방향은 계산된 값이다): " + "; ".join(summaries))

    if (dm := _demand_context(rows)):
        parts.append(dm)

    # 행사는 수요신호의 **빈 시간대**를 알아야 고를 수 있다 — 두 축을 같은 눈금으로 맞춘다.
    if (ev := _events_context(district_id, _gap_band(rows))):
        parts.append(ev)
    return "\n".join(parts) or None


# 오프라인 제안이 겨냥할 수 있는 시간대 — 00~06 은 뺀다.
# 심야에 유동이 매출을 앞서는 건 상권의 빈틈이 아니라 가게가 닫혀 있어서다. 빼지 않으면
# 대다수 거점에서 00~06 이 '최대 격차'로 뽑히고 새벽 플리마켓 같은 제안이 나온다.
# data/pipelines/build_program_demand.ACTIONABLE_TMZONS 와 같은 값을 유지할 것.
_ACTIONABLE_TMZONS = ["06_11", "11_14", "14_17", "17_21", "21_24"]
_TMZON_LABEL = {"00_06": "0~6시", "06_11": "6~11시", "11_14": "11~14시",
                "14_17": "14~17시", "17_21": "17~21시", "21_24": "21~24시"}


def _gap_band(rows: list[tuple[str, str, float]]) -> str | None:
    """유동 대비 매출이 가장 빈 시간대(= 오프라인 유입 확대가 겨냥할 구간).

    매출이 결측인 거점은 격차를 만들 수 없으므로 None — 없는 근거를 지어내지 않는다.
    """
    d = {k: v for kd, k, v in rows if kd == "demand"}
    gaps = [(d[f"flpop_tmzon_{t}"] - d[f"selng_tmzon_{t}"], t) for t in _ACTIONABLE_TMZONS
            if f"flpop_tmzon_{t}" in d and f"selng_tmzon_{t}" in d]
    return max(gaps)[1] if gaps else None


def _demand_context(rows: list[tuple[str, str, float]]) -> str | None:
    """TRDAR 상권 수요신호를 컨텍스트 문장으로 (build_program_demand 산출 `demand` 행).

    Program 의 대상이 **아직 이 자리에서 장사해 본 적 없는 창업자**라 리뷰가 없다.
    제안의 근거를 리뷰 대신 이 수치가 맡는다 — 없으면 "상권 플리마켓 참여" 같은 어느
    상권에나 해당하는 말이 된다. 검증 지표의 목표선도 여기서 끌어낸다.

    두 출력이 같은 표에서 갈린다:
      - 매출이 유동을 앞서는 시간대 = **전환 구간** → 온라인(모객) 광고를 태울 곳
      - 유동이 매출을 앞서는 시간대 = **빈 구간** → 오프라인(자리·연계)이 칠 곳
    """
    d = {k: v for kd, k, v in rows if kd == "demand"}
    if not d:
        return None

    parts: list[str] = []

    pairs = [(t, d[f"flpop_tmzon_{t}"], d[f"selng_tmzon_{t}"]) for t in _ACTIONABLE_TMZONS
             if f"flpop_tmzon_{t}" in d and f"selng_tmzon_{t}" in d]
    if pairs:
        parts.append("시간대별 유동/매출 구성비(%): " + ", ".join(
            f"{_TMZON_LABEL[t]} 유동 {f:.1f}/매출 {s:.1f}" for t, f, s in pairs))
        gap = max(pairs, key=lambda p: p[1] - p[2])
        conv = min(pairs, key=lambda p: p[1] - p[2])
        parts.append(
            f"유동 대비 매출이 가장 빈 시간대는 {_TMZON_LABEL[gap[0]]}"
            f"(+{gap[1] - gap[2]:.1f}%p) — 오프라인 유입 확대 제안은 이 구간을 겨냥한다. "
            f"매출이 가장 앞서는 시간대는 {_TMZON_LABEL[conv[0]]}"
            f"({conv[1] - conv[2]:+.1f}%p) — 온라인 퍼포먼스 노출은 이 구간에 둔다.")
    elif any(k.startswith("flpop_tmzon") for k in d):
        # 유동만 있고 매출이 결측인 거점 — 격차를 지어내지 않는다.
        parts.append("시간대별 매출 구성비는 이 상권에서 결측이다 — 유동·매출 격차를 근거로 쓰지 말 것.")

    ages = [(a, d[f"agrde_{a}"]) for a in ("10", "20", "30", "40", "50", "60_above")
            if f"agrde_{a}" in d]
    if ages:
        top = sorted(ages, key=lambda x: -x[1])[:3]
        lab = {"60_above": "60대+"}
        parts.append("유동인구 구성: " + ", ".join(
            f"{lab.get(a, a + '대')} {v:.1f}%" for a, v in top)
            + (f", 여성 {d['fml_share']:.1f}%" if "fml_share" in d else ""))

    if "flpop_wkend" in d and "selng_wkend" in d:
        parts.append(f"주말 비중: 유동 {d['flpop_wkend']:.1f}% / 매출 {d['selng_wkend']:.1f}%")

    biz = []
    if "stor_co" in d:
        biz.append(f"점포 {int(d['stor_co'])}곳")
    if "frc_share" in d:
        biz.append(f"프랜차이즈 {d['frc_share']:.1f}%")
    if "clsbiz_rt" in d:
        biz.append(f"폐업률 {d['clsbiz_rt']:.2f}%")
    if biz:
        parts.append("상권 구성: " + " · ".join(biz))

    if "trdar_n" in d:
        n, sn = int(d["trdar_n"]), int(d.get("trdar_selng_n", d["trdar_n"]))
        note = f"(TRDAR 상권 {n}개 유동 가중평균"
        note += f", 매출은 {sn}개" if sn != n else ""
        parts.append(note + ")")

    return "\n".join(parts) or None


# 프롬프트에 실을 행사 수 상한. ikseon 78건처럼 도심 거점은 전부 실으면 컨텍스트를
# 행사가 잠식한다. 가까운 순으로 이만큼만 준다.
_MAX_CONTEXT_EVENTS = 5

# 관람객이 걸어서 넘어올 만한 거리. 이 밖의 행사는 "연계"의 근거가 되지 못한다 —
# 785건의 거리 중앙값이 989m 이고, 500m 안에 행사가 있는 거점은 54곳 중 28곳뿐이다.
# 남은 26곳에 먼 행사를 실으면 LLM 이 남의 동네 행사를 우리 골목 것처럼 쓴다.
_WALKABLE_M = 500


def _events_context(district_id: str | None, gap_band: str | None = None) -> str | None:
    """상권 행사를 컨텍스트 문장으로 — 오프라인 제안이 공허해지는 것을 막는다.

    이 함수 이전에는 컨텍스트에 행사가 없었고, 그래서 오프라인 제안이 "상권
    플리마켓/팝업 부스 참여" 같은 **어느 상권에나 해당하는 말**로 나왔다. 실제 행사
    785건이 이미 Gold 에 있는데 쓰지 않고 있었다.

    세 경우를 구분한다 — 이 구분이 이 함수의 요점이다:

      None(Gold 미적재)  행사를 아는 바가 없다 → 아무 말도 하지 않는다.
                         "행사 없음"이라고 쓰면 모르는 것을 안다고 주장하는 것이다.
      [](예정 행사 없음)  **명시적으로 없다고 말하고 제안을 금지한다.** 침묵하면 LLM 이
                         일반론으로 행사 참여를 지어낸다 — 고치려던 바로 그 증상이다.
      목록 있음           걸어갈 거리(_WALKABLE_M) 안의 것만, 가까운 순 상위 N건.

    **거리를 반드시 싣는다.** 이 API 는 공공·문화시설 행사 중심이라 가두 상권 커버리지가
    낮다 — 가로수길 2건은 둘 다 800m 밖이다. 거리를 빼면 LLM 이 남의 동네 행사를
    "우리 골목 행사"처럼 쓴다. 걸어갈 거리 안에 하나도 없으면 그 사실을 말하고
    연계 제안을 금지한다(네 번째 경우 — 2026-08-16 추가).

    ## 빈 시간대와의 교집합 (2026-08-16)

    `gap_band` 는 수요신호에서 온 "유동 대비 매출이 가장 빈 시간대"다. 그 시간에 실제로
    열리는 행사가 연계 후보이므로 먼저 보여주고, 하나도 없으면 **없다고 밝힌다** —
    시간대를 맞춘 것처럼 쓰는 것을 막는다.

    한때 "문화행사라 상권 상업이벤트와 종류가 다르다"고 판단해 외부 소스를 찾으려 했는데,
    거리로 걸러 열어보니 서울아트위크(59m)·DDP 뮤직페스티벌(107m)·서울야외도서관(158m)
    처럼 광장 활성화 그 자체인 행사들이었다. 종류가 아니라 **필터와 속성이 없던 것**이다.
    시각(`PRO_TIME`)도 원천에 785/785 있었는데 Gold 로 넘기지 않고 있었다.
    """
    if not district_id:
        return None
    rows = events.for_district(district_id)
    if rows is None:
        return None
    if not rows:
        return ("상권 행사: 확인된 예정 행사가 없다(공공 문화행사 기준). "
                "행사 참여·연계를 제안하지 말 것 — 없는 행사를 지어내는 셈이다.")

    # 거리 미상(시드 잔재)은 '멀다'도 '가깝다'도 아니다. 걸러내되 버리지는 않는다 —
    # 거리가 있는 것이 하나도 없을 때는 이들이라도 실어야 정보가 사라지지 않는다.
    known = [e for e in rows if e.get("distance_m") is not None]
    unknown = [e for e in rows if e.get("distance_m") is None]
    walkable = [e for e in known if e["distance_m"] <= _WALKABLE_M]

    if not walkable and not unknown:
        nearest = min(e["distance_m"] for e in known) if known else None
        far = f"(가장 가까운 것이 {nearest}m)" if nearest is not None else ""
        return (f"상권 행사: {_WALKABLE_M}m 안에 예정 행사가 없다{far}. "
                "걸어갈 거리가 아니므로 관람객 유입을 전제한 연계 제안을 하지 말 것 — "
                "매장 자체 접점을 제안한다.")
    if not walkable:
        items = "; ".join(f"{e.get('n')}({e.get('when')} · {e.get('place') or '장소 미상'})"
                          for e in unknown[:_MAX_CONTEXT_EVENTS])
        return ("상권 행사(거리 미상 — 걸어갈 거리인지 확인되지 않았다): " + items
                + " — 거리를 모르므로 관람객 유입 규모를 단정하지 말 것.")

    # 빈 시간대에 실제로 열리는 행사가 연계 후보다. 그 교집합을 먼저 보여준다.
    hit = [e for e in walkable if gap_band and gap_band in (e.get("tm") or [])]
    pick = (hit or walkable)
    pick = sorted(pick, key=lambda e: e.get("distance_m") or 10**9)[:_MAX_CONTEXT_EVENTS]

    items = []
    for e in pick:
        dist = e.get("distance_m")
        where = f"{e.get('place') or '장소 미상'}, {dist}m" if dist is not None \
            else (e.get("place") or "장소 미상")
        when = e.get("when")
        if e.get("time"):
            when = f"{when} {e['time']}"
        items.append(f"{e.get('n')}({when} · {where})")

    head = "상권 행사(공공 문화행사 실데이터, 걸어갈 거리 안)"
    # 전국 행사 Gold(문화포털·TourAPI)에는 시각(tm)이 없다 — 모르는 시각을 「안 열린다」로 단정하지 않는다.
    untimed = [e for e in walkable if not e.get("tm")]
    if hit:
        head += f" — 아래는 **빈 시간대({_TMZON_LABEL.get(gap_band, gap_band)})에 열리는** 행사다"
    elif gap_band and untimed:
        head += (f" — 빈 시간대({_TMZON_LABEL.get(gap_band, gap_band)})에 열리는지 확인된 행사는 없다"
                 f"(시각 정보가 없는 행사 {len(untimed)}건은 판단에서 뺐다). 시간대를 맞춰 연계했다고 쓰지 말 것")
    elif gap_band:
        head += (f" — 빈 시간대({_TMZON_LABEL.get(gap_band, gap_band)})에 열리는 행사는 없다. "
                 "시간대를 맞춰 연계했다고 쓰지 말 것")
    return (head + ": " + "; ".join(items)
            + " — 거리와 시각을 확인하고, 거점 밖 행사를 상권 안 행사처럼 쓰지 말 것.")


# 트렌드 방향 판정 임계 — 최근 3개월 평균이 직전 3개월 평균 대비 이만큼 벗어나야 방향을 붙인다.
# 5%는 검색량의 월별 잡음(계절·요일 구성)을 방향으로 오독하지 않을 정도로 잡은 값이다.
_TREND_FLAT_BAND = 0.05


def _trend_summary(name: str, points: list[tuple[str, float]]) -> str | None:
    """검색 트렌드 한 계열을 **방향이 붙은 한 문장**으로 요약.

    `points` 는 (기간키, 값) 쌍이고 정렬은 여기서 한다 — 호출부가 순서를 보장하지
    않아도 되게. (2026-08-06: pandas 제거로 DataFrame 대신 평범한 쌍을 받는다.)

    왜 숫자를 그대로 넘기지 않는가 — 2026-08-01 실사고. 이 함수 이전에는 최근 3개월의
    원시 수치만 프롬프트에 실었고(`신사동 2026-05=67.7; …`), LLM 이 하락 시계열을 보고
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다. 같은 실행에서 가게 단위는
    방향을 맞혔으므로 모델이 아니라 **해석을 LLM 에 맡긴 설계**가 원인이다.
    방향은 여기서 계산해 확정하고, LLM 에는 판정 결과를 문장으로 준다.

    판정: 최근 3개월 평균 vs 직전 3개월 평균의 상대 변화. ±5%(_TREND_FLAT_BAND) 안이면 보합.
    6개 점이 안 되면 방향을 만들지 않고 None — 근거 없는 방향을 주느니 트렌드를 빼는 게 낫다.
    (Gold 단계에서 미완성 달은 이미 잘려 있다 — data/pipelines/build_gold._complete_trend_points)
    """
    vals = [v for _, v in sorted(points, key=lambda kv: kv[0])][-6:]
    if len(vals) < 6:
        return None
    prior = sum(vals[:3]) / 3
    recent = sum(vals[3:]) / 3
    if prior <= 0:
        return None
    change = (recent - prior) / prior
    label = "보합" if abs(change) < _TREND_FLAT_BAND else ("상승" if change > 0 else "하락")
    return f"{name} {label}({prior:.1f}→{recent:.1f}, {change * 100:+.1f}%)"


_DISTRICT_SYSTEM_PROMPT = """너는 PlaceOS의 Program(상권 단위 마케팅) 온라인 콘텐츠 생성기다.
입력된 상권 컨텍스트(블로그 언급 키워드 빈도·업종 분포·검색 트렌드)만을 근거로,
그 상권의 온라인 콘텐츠 소재를 한 줄 카피 형태로 제안한다.

형식: "{소재 문장} #{해시태그} #{해시태그}" — 한 줄에 해시태그 2개.

원칙 (Humanistic Authority — 균형·공생·공감):
- 컨텍스트에 실제로 나타난 키워드·업종만 소구한다. 데이터에 없는 점포명·행사·수치를 지어내지 않는다.
- **데이터가 말하지 않는 방향을 주장하지 않는다.** 검색 트렌드에는 이미 판정된 방향
  (상승/보합/하락)이 붙어 있다. 그 방향과 어긋나게 쓰지 말 것 — '하락'인데 "다시 늘고 있는",
  '보합'인데 "급증하는" 식의 서술은 금지다. 하락·보합이면 유입 증가를 전제하지 말고
  이미 있는 강점(키워드·업종)에 소구하거나, 트렌드를 언급하지 않는다.
- 특정 점포나 자본에 편중하지 않고 상권 전체의 활성화를 향한다.
- 과장·허위·검증 불가한 최상급 표현을 쓰지 않는다.
- **금액을 쓰지 않는다.** 상권 컨텍스트에는 가격 정보가 없으므로 어떤 금액을 적든 지어낸
  값이다("1만원대 점심" 같은 표현 금지).
- ha_check 에 위 기준으로 자체 점검한 결과를 1~2문장으로 쓴다.

출력: online_contents 2~4건. 한국어로 작성한다."""


def _call_district_llm(name: str, sub: str, ctx: str) -> LLMDistrictContents:
    """Claude 실호출 — 상권 컨텍스트(Gold) → 온라인 콘텐츠 한 줄 카피."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.parse(
        model=settings.llm_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_DISTRICT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content":
                   f"상권: {name} ({sub})\n\n[상권 컨텍스트 — Platform 수집 데이터]\n{ctx}"}],
        output_format=LLMDistrictContents,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"LLM 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
    return parsed


# 상권 콘텐츠 LLM 결과 캐시: district_id → (컨텍스트 파일 mtime, online_contents, ha_findings)
#
# 캐시가 없으면 이 엔드포인트는 **호출마다** LLM 을 친다 — 실측 12~14초 + 매번 크레딧이
# 나간다(2026-08-01). 거점 심층 뷰가 이 응답을 기다리므로 화면이 그만큼 멈춘다.
# 입력은 Gold 컨텍스트 파일 하나뿐이라 mtime 이 그대로면 결과도 그대로다. TTL 이 아니라
# mtime 으로 무효화하는 이유: 파이프라인을 다시 돌리면 즉시 반영돼야 하고, 안 돌렸다면
# 하루가 지나도 다시 칠 이유가 없다. 프로세스 재시작 시 비므로 코드·시드 변경도 반영된다.
#
# **HA 검증에 걸려 폐기된 결과도 캐시한다** (online_contents 를 빈 리스트로). 안 그러면
# 같은 컨텍스트로 같은 위반을 반복 생성하며 호출마다 크레딧을 태운다. 컨텍스트가 바뀌거나
# 프로세스가 재시작되면(프롬프트·검증기 수정이 반영되는 시점) 어차피 다시 친다.
_district_llm_cache: dict[str, tuple[float, list[str], list[dict]]] = {}

# 상권 콘텐츠 LLM **실패** 캐시: district_id → (컨텍스트 mtime, 이 시각(monotonic)까지 재시도 금지)
#
# 위 캐시는 "생성이 끝난 결과"만 담는다. 응답이 비었거나(online_contents 0건) 호출이 예외로 끝난
# 경우(파싱·스키마 실패 포함)는 아무것도 못 담아서, **같은 요청이 올 때마다 LLM 을 다시 쳤다.**
# 파싱 실패는 토큰을 이미 쓴 뒤에 터지므로 실패한 호출도 비용이다(2026-10-03 발견).
#
# 성공 캐시처럼 mtime 만으로 무효화하지 않고 **시간 제한**을 둔다 — 실패 원인이 일시적인
# 장애(rate limit·네트워크)일 수 있어서, 재시작 전까지 시드에 붙잡아 두면 장애가 끝나도 AI 콘텐츠가
# 돌아오지 않는다. 그 사이 비용 상한은 "거점당 인스턴스당 5분에 1회"다. 5분은 도출한 값이 아니라
# 고른 값이다: 일시 장애가 풀릴 만큼은 짧고, 반복 호출이 비용이 되지 않을 만큼은 길다.
# 컨텍스트가 바뀌면(mtime) 입력이 달라졌으니 시간이 안 지나도 다시 친다.
_DISTRICT_FAILURE_TTL_S = 300.0
_district_llm_failures: dict[str, tuple[float, float]] = {}


def _remember_district_failure(district_id: str, mtime: float) -> None:
    _district_llm_failures[district_id] = (mtime, time.monotonic() + _DISTRICT_FAILURE_TTL_S)


def _district_failure_pending(district_id: str, mtime: float) -> bool:
    """이 입력으로 최근에 실패했고 아직 재시도 금지 시간 안이면 True."""
    hit = _district_llm_failures.get(district_id)
    return bool(hit and hit[0] == mtime and time.monotonic() < hit[1])


def clear_district_cache() -> None:
    """상권 콘텐츠 LLM 캐시 비우기.

    평소에는 컨텍스트 파일 mtime 이 바뀌면 알아서 무효화되므로 부를 일이 없다.
    같은 프로세스 안에서 캐시를 강제로 버려야 할 때 쓴다(테스트 격리, 프롬프트 수정 후 재생성).
    """
    _district_llm_cache.clear()
    _district_llm_failures.clear()


def _context_mtime(district_id: str) -> float:
    """상권 컨텍스트의 mtime. 없으면 0.0 (캐시 키로만 쓴다).

    ⚠ 컨텍스트 입력이 **두 파일**이다 — program_content_context 와 행사 Gold. 행사가
    컨텍스트에 합류(2026-08-06)하면서 앞의 것만 보면 행사 파이프라인만 다시 돌린 경우
    무효화가 안 돼 낡은 카피가 남는다. 둘을 합쳐 키로 쓴다.
    """
    slug = _DISTRICT_ALIAS.get(district_id, district_id)
    if not _SLUG_RE.match(slug):
        return 0.0
    path = _context_path(slug)
    base = path.stat().st_mtime if path.exists() else 0.0
    return base + events.source_mtime()


def _marketing_base(district_id: str) -> dict | None:
    """행사·온라인 콘텐츠의 바탕. 서빙 목록(`PAGES`)에 있으면 시드 없는 거점도 빈 바탕으로 선다.

    종전에는 시드(`DISTRICTS`)로 먼저 걸러, 서빙 117곳 중 시드 밖 63곳(행사 Gold 가 있는 서울 27곳 포함)이 404 였다.
    """
    base = svc.get_marketing(district_id)
    if base is not None:
        return base
    if svc.get_district(district_id) is None:
        return None
    return {"district_id": district_id, "events": [], "online_contents": []}


def _events_unavailable_note(district_id: str) -> str | None:
    """이 거점에 행사 원천이 없으면 그 사유. 있으면 None.

    2026-11-07 부터 전국 행사 Gold(문화포털·TourAPI)가 서울 밖 거점도 덮는다 — 덮으면 원천이 있다.
    """
    d = svc.get_district(district_id)
    if not d or svc.page_city(d).has_city_events or events.national_covers(district_id):
        return None
    return f"행사 자료는 서울만 있어요 — {svc.page_city(d).short} 상권은 수집하지 않았어요."


def _real_events_source(district_id: str) -> str:
    """실데이터 행사의 출처 표기.

    "seoul-open-data"  서울 문화행사 Gold 만 이 거점을 덮는다(전국 Gold 미적재)
    "public-open-data" 전국 행사 Gold(문화포털·TourAPI)가 이 거점을 덮는다 — 서울 거점은 두 원천을 합친다
    행사마다 `src` 로 어느 원천인지 다시 밝힌다(services/events.SRC_LABEL).
    """
    return "public-open-data" if events.national_covers(district_id) else "seoul-open-data"


def get_district_events(district_id: str) -> dict | None:
    """상권 행사만 — **LLM 을 부르지 않는** 조회(2026-09-13).

    Program 화면이 지도 위에 오프라인 홍보 장소(공공 문화행사)를 찍으려고 필요해졌다.
    `get_district_marketing` 을 그대로 부르면 행사 몇 개를 얻자고 온라인 콘텐츠 LLM 생성까지
    돈다(거점마다 1회, 인스턴스가 새로 뜨면 다시). 지도를 옮길 때마다 크레딧을 쓰는 화면이
    되므로 행사 경로만 떼어 낸다. 출처 규칙은 아래 함수와 같다 — 적재됐는데 0건이면 빈 목록.
    """
    base = _marketing_base(district_id)
    if base is None:
        return None
    no_city = _events_unavailable_note(district_id)
    if no_city:
        return {"district_id": district_id, "events": [], "events_source": "none", "events_note": no_city}
    real_events = events.for_district(district_id)
    if real_events is None:
        return {"district_id": district_id, "events": base["events"],
                "events_source": "seed" if base["events"] else "none", "events_note": None}
    return {"district_id": district_id, "events": real_events,
            "events_source": _real_events_source(district_id), "events_note": None}


def get_district_marketing(district_id: str, *, allow_llm: bool = False) -> dict | None:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠) — Program 2단계.

    online_contents: Gold(program_content_context)의 블로그 키워드·업종 분포를 근거로
      LLM 생성. **`allow_llm`(로그인한 호출)이 아니면 LLM 을 부르지 않고 시드를 준다** —
      캐시에 이미 있는 결과도 보여주지 않는다(같은 거점이 호출자에 따라 달라지지 않게, 그리고
      "로그인하면 AI 생성" 안내가 거짓이 되지 않게). 기본값이 False 인 이유는
      `generate_program` 과 같다. 키 미설정·Gold 미적재·호출 실패 시에도 시드 카피로
      폴백(source 로 구분). 생성 결과는 컨텍스트 파일 mtime 기준으로 캐시하고, 실패는 시간
      제한을 두고 따로 캐시한다(위 주석 참조).
    events: 서울열린데이터광장 문화행사 실데이터(services/events.py). LLM 은 절대
      관여하지 않는다 — 좌표·일정이 붙은 실물이라 지어내면 없는 행사를 지도에 찍게 된다.
      Gold 미적재면 시드로 폴백하되 events_source 로 출처를 밝힌다.
    """
    base = _marketing_base(district_id)
    if base is None:
        return None

    no_city = _events_unavailable_note(district_id)
    # 행사: 서울열린데이터광장 문화행사 실데이터. Gold 미적재면 시드로 폴백하되
    # 출처를 밝힌다. 적재됐는데 그 거점에 예정 행사가 없으면 **빈 목록 그대로** —
    # 시드로 채우면 지어낸 행사를 지도에 다시 찍는 셈이다.
    real_events = events.for_district(district_id)
    if no_city:
        base = {**base, "events": [], "events_source": "none", "events_note": no_city}
    elif real_events is None:
        base = {**base, "events_source": "seed"}
    else:
        base = {**base, "events": real_events, "events_source": _real_events_source(district_id)}

    ctx = _district_context(district_id)
    if allow_llm and settings.llm_api_key and ctx:
        mtime = _context_mtime(district_id)
        hit = _district_llm_cache.get(district_id)
        if hit and hit[0] == mtime:
            # contents 가 비어 있으면 HA 검증에 걸려 폐기된 것이다 — 시드로 내려가되
            # 폐기 사유(findings)는 그대로 실어 왜 시드인지 밝힌다.
            if hit[1]:
                return {**base, "online_contents": hit[1], "source": "llm",
                        "ha_findings": hit[2]}
            return {**base, "source": "seed", "ha_findings": hit[2]}

        # 최근에 같은 입력으로 실패했으면 다시 치지 않는다 — 실패한 호출도 토큰을 쓴다.
        if _district_failure_pending(district_id, mtime):
            return {**base, "source": "seed"}

        d = DISTRICTS_BY_ID.get(district_id, {})
        try:
            parsed = _call_district_llm(d.get("name", district_id), d.get("sub", ""), ctx)
            if not parsed.online_contents:
                # 응답이 비었다 — 캐시할 결과가 없으므로 실패로 적어 반복 호출을 막는다.
                _remember_district_failure(district_id, mtime)
            else:
                findings = ha_guard.check_district(parsed, ctx)
                dumped = [f.model_dump() for f in findings]
                if ha_guard.has_violation(findings):
                    print("[marketing] 상권 콘텐츠 HA 검증 위반 → 생성물 폐기: "
                          f"{ha_guard.summarize(findings)}")
                    _district_llm_cache[district_id] = (mtime, [], dumped)
                    return {**base, "source": "seed", "ha_findings": dumped}
                _district_llm_cache[district_id] = (mtime, parsed.online_contents, dumped)
                return {**base, "online_contents": parsed.online_contents,
                        "source": "llm", "ha_findings": dumped}
        except Exception as exc:
            _remember_district_failure(district_id, mtime)
            print(f"[marketing] 상권 콘텐츠 LLM 생성 실패 → 시드 폴백: {exc}")
    return {**base, "source": "seed"}
