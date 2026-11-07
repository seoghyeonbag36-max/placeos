"""[Program] 상권 행사 서빙 — 서울 문화행사 Gold + 전국 행사 Gold 를 합쳐 거점별로 준다.

행사는 좌표·일정이 붙은 **실물**이라 지어내면 안 된다. 시드 행사는 좌표·일정까지
손으로 적은 값이었고, 근거 없는 효과 지표("유입 +52%")·이해관계자 역할·HA 메모까지
달고 있었다. 이제 공공 원천에서 실제 행사만 싣는다.

원천 두 파일 (2026-11-07 Program 리뉴얼):
  gold/platform_events.json           서울열린데이터광장 문화행사(culturalEventInfo) — 서울 거점만
  gold/platform_events_national.json  문화포털 기간별 문화정보 + 한국관광공사 TourAPI 축제 — 서빙 거점 전부
                                      (data/pipelines/build_national_events.py)

**끝난 행사는 서빙 시점에 거른다**(2026-11-07). Gold 는 적재일에 한 번 「종료 행사 제외」를
했을 뿐이라, 10-11 적재본은 11-07 에 749건 중 498건(66.5%)이 이미 끝나 있었고 19거점은 실린
행사가 전부 끝나 있었다 — 그런데 화면과 LLM 컨텍스트는 그것을 「예정 행사」로 실었다.

**없으면 비운다.** 공공·문화시설 행사 중심이라 가두 상권 커버리지가 낮다(가로수길 2건, 둘 다
800m 밖). 빈 거점을 시드로 채우면 지어낸 행사를 다시 지도에 찍는 셈이라, 빈 목록을 그대로
돌려주고 프론트가 빈 상태를 표시한다.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_EVENTS_JSON = _GOLD / "platform_events.json"
_NATIONAL_JSON = _GOLD / "platform_events_national.json"
_TTL_SECONDS = 300.0

# 거점 id 별칭 → 정규 slug (building_vacancy._ALIASES 와 동일하게 유지)
_ALIASES = {"gangnam-garosugil": "garosugil", "sinsa": "garosugil"}

# 원천 이름(행사 하나하나의 `src`) — 서울 Gold 는 필드가 없어 여기서 붙인다.
SRC_SEOUL = "seoul-culture"
SRC_LABEL = {
    SRC_SEOUL: "서울 문화행사",
    "culture-portal": "문화포털",
    "tourapi": "한국관광공사 축제",
}

# 한국 표준시는 서머타임이 없다 — tzdata 없이도 고정 오프셋이 정확하다(Windows 개발 환경 포함).
_KST = timezone(timedelta(hours=9))
_DATE = re.compile(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})")

_cache: dict[Path, dict[str, Any]] = {}


def _load_file(path: Path) -> dict | None:
    now = time.monotonic()
    hit = _cache.get(path)
    if hit is not None and now - hit["at"] < _TTL_SECONDS:
        return hit["data"]
    if not path.exists():
        _cache.pop(path, None)
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[path] = {"data": data, "at": now}
    return data


def _load() -> dict | None:
    """서울 문화행사 Gold."""
    return _load_file(_EVENTS_JSON)


def _load_national() -> dict | None:
    """전국 행사 Gold(문화포털·TourAPI)."""
    return _load_file(_NATIONAL_JSON)


def is_available() -> bool:
    """행사 Gold 가 하나라도 적재돼 있는가."""
    return _load() is not None or _load_national() is not None


def source_mtime() -> float:
    """행사 Gold 두 파일 중 늦은 mtime. 없으면 0.0.

    상권 콘텐츠 LLM 캐시가 이 값을 키에 섞는다 — 행사가 상권 컨텍스트에 들어가면서
    `program_content_context` 만으로는 무효화가 안 되기 때문이다(행사 파이프라인만
    다시 돌린 경우 mtime 이 그대로여서 낡은 카피가 남는다). 어느 파일을 다시 만들어도
    그 파일이 가장 늦으므로 max 로 충분하다.
    """
    return max((p.stat().st_mtime for p in (_EVENTS_JSON, _NATIONAL_JSON) if p.exists()), default=0.0)


def today_kst() -> date:
    return datetime.now(_KST).date()


def event_dates(event: dict) -> tuple[date | None, date | None]:
    """`when`("2026-10-17~2026-10-25" · "2026.10.17" …)의 첫 날짜와 마지막 날짜. 못 읽으면 None."""
    found = []
    for y, m, d in _DATE.findall(str(event.get("when") or "")):
        try:
            found.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    if not found:
        return None, None
    return found[0], found[-1]


def is_ended(event: dict, today: date) -> bool:
    """끝난 행사인가 — 종료일을 못 읽으면 끝났다고 단정하지 않는다(모름 ≠ 종료)."""
    _, end = event_dates(event)
    return end is not None and end < today


def _norm_title(title: str) -> str:
    return re.sub(r"[\s\[\]()<>「」『』\"'·•,.!?~\-_/:]", "", title or "").lower()


def _slug(district_id: str) -> str:
    return _ALIASES.get(district_id, district_id)


def national_covers(district_id: str) -> bool:
    """전국 행사 Gold 가 이 거점을 덮는가(적재됐고 거점 키가 있다 — 0건이어도 덮은 것이다)."""
    data = _load_national()
    return bool(data) and _slug(district_id) in (data.get("districts") or {})


def for_district(district_id: str, *, today: date | None = None) -> list[dict] | None:
    """거점의 실제 행사 목록 — 끝난 행사를 빼고, 두 원천을 합쳐 가까운 순으로.

    반환값의 의미를 구분할 것:
      - `None`  두 Gold 모두 미적재 (파이프라인 미실행) → 호출부가 출처를 "none" 으로 표기
      - `[]`    적재됐고 그 거점에 예정 행사가 없음 → 빈 상태를 그대로 보여준다

    같은 행사가 두 원천에 다 있으면(정규화한 제목 + 같은 시작일) 서울 Gold 쪽을 남긴다 —
    시각(`tm`)·요금·원문 링크 같은 필드가 그쪽에만 있다.
    """
    seoul, national = _load(), _load_national()
    if not seoul and not national:
        return None
    today = today or today_kst()
    slug = _slug(district_id)
    rows: list[dict] = []
    seen: set[tuple[str, date | None]] = set()
    for data, default_src in ((seoul, SRC_SEOUL), (national, None)):
        if not data:
            continue
        for e in (data.get("districts") or {}).get(slug, []) or []:
            if is_ended(e, today):
                continue
            key = (_norm_title(str(e.get("n") or "")), event_dates(e)[0])
            if key in seen:
                continue
            seen.add(key)
            rows.append(e if e.get("src") else {**e, "src": default_src})
    rows.sort(key=lambda e: e["distance_m"] if e.get("distance_m") is not None else 10**9)
    return rows


def sources_meta() -> list[dict]:
    """적재된 원천의 이름·기준일 — 화면이 「출처: …(기준일)」을 밝히는 데 쓴다."""
    out: list[dict] = []
    if (s := _load()):
        out.append({"id": SRC_SEOUL, "name": SRC_LABEL[SRC_SEOUL], "as_of": s.get("as_of")})
    if (n := _load_national()):
        for src in n.get("sources") or []:
            sid = src.get("id")
            out.append({"id": sid, "name": SRC_LABEL.get(sid, src.get("name") or sid),
                        "as_of": n.get("as_of"), "license": src.get("license")})
    return out
