"""[Program] 지원 프로그램 — 국가·지자체 창업 지원 공고를 거점·단계·업종에 맞춰 고른다(2026-11-07 리뉴얼).

묻는 질문: 「내 단계·업종·지역에 지금 신청할 수 있는 국가·지자체 지원은 무엇이고, 언제 마감인가?」

원천 셋(services/program_sources):
  K-Startup 모집 중 공고 · 정부24 공공서비스(혜택) 중 「소상공인」 · 기업마당 지원사업정보(지역 해시태그)

**고르는 규칙은 결정론이다 — LLM 을 부르지 않는다.** 금액·자격을 지어낼 여지를 없애고, 같은 질문에
같은 답이 나와야 한다. 원문에 있는 것만 싣고(발췌 ≤ 200자), 원문 링크를 붙인다.

**자격 판정이 아니다.** 「조건이 맞을 수 있는 공고」다 — 지역·단계·업종 문구가 맞는지만 본다.
선정 가능성·지원 금액을 말하지 않는다. 지원금은 Posting 회수기간 계산에 넣지 않는다(선정 전 금액을
넣으면 실측처럼 보이는 추정이 된다 — docs/renewal-program-2026-11-07.md §1-4).

「행사ㆍ네트워크」 분야 공고는 여기서 빼고 네트워킹(services/program_network)에서 보인다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape

from app.services import districts as svc
from app.services import events, program_sources as src

STAGES = {"pre_founder": "예비창업자", "founder": "기창업자(업종 바꾸기·상권 옮기기)"}
_FOUNDER_ENYY = ("1년미만", "2년미만", "3년미만", "5년미만", "7년미만", "10년미만")
_MAX_ITEMS = 80
_SUMMARY_MAX = 200

# K-Startup supt_regin · 기업마당 해시태그가 쓰는 짧은 지역 이름. 광주는 2026 통합으로 원천마다 표기가 갈린다.
_SIDO_TAGS: dict[str, tuple[str, ...]] = {
    "서울특별시": ("서울",), "경기도": ("경기",), "인천광역시": ("인천",), "부산광역시": ("부산",),
    "대구광역시": ("대구",), "대전광역시": ("대전",), "울산광역시": ("울산",), "세종특별자치시": ("세종",),
    "강원특별자치도": ("강원",), "충청북도": ("충북",), "충청남도": ("충남",), "전북특별자치도": ("전북",),
    "전남광주통합특별시": ("광주", "전남", "전남광주"), "경상북도": ("경북",), "경상남도": ("경남",),
    "제주특별자치도": ("제주",),
}
# 기업마당 해시태그 표(공식 명세 URL코드표) — 지역 하나를 고른다.
_BIZINFO_TAG = {"전남광주통합특별시": "전남광주"}
# 시도청 이름(옛 이름 포함) — 기업마당 공고의 소관기관이 이 중 하나면 그 지역 공고, 아니면(부·처·청·위원회) 전국 공고다.
# ⚠ 기업마당 `hashtags` 는 지역을 가르지 못한다 — 11-08 실측에서 #전북 응답 300건이 전부 「전북」을, 256건이 「서울」을
#   달고 있었다(서울시 「서울패션위크」 공고도 17개 시도를 다 단다). 지역은 소관기관(jrsdInsttNm)으로 가른다.
_SIDO_GOV: dict[str, str] = {
    "서울특별시": "서울특별시", "부산광역시": "부산광역시", "대구광역시": "대구광역시", "인천광역시": "인천광역시",
    "광주광역시": "전남광주통합특별시", "전라남도": "전남광주통합특별시", "전남광주통합특별시": "전남광주통합특별시",
    "대전광역시": "대전광역시", "울산광역시": "울산광역시", "세종특별자치시": "세종특별자치시", "경기도": "경기도",
    "강원특별자치도": "강원특별자치도", "강원도": "강원특별자치도", "충청북도": "충청북도", "충청남도": "충청남도",
    "전북특별자치도": "전북특별자치도", "전라북도": "전북특별자치도", "경상북도": "경상북도", "경상남도": "경상남도",
    "제주특별자치도": "제주특별자치도",
}


def sido_of_org(org: str | None) -> str | None:
    """기관 이름이 시도청이면 그 시도(지금 이름), 아니면 None(중앙부처·공공기관 = 전국)."""
    return _SIDO_GOV.get((org or "").strip())


def area_scope(area: str | None, region: Region) -> str | None:
    """기업마당 행사의 개최 지역(areaNm) → "local"(이 시도) · "national"(전국·미상) · None(다른 시도 — 뺀다)."""
    a = (area or "").strip()
    if not a or a == "전국":
        return "national"
    return "local" if (a == region.bizinfo_tag or a in region.tags) else None


@dataclass(frozen=True)
class Region:
    sido: str                    # "서울특별시"
    tags: tuple[str, ...]        # ("서울",)
    city: str                    # "서울특별시" · "수원특례시" · "광주광역시"
    local: str | None            # 시군구 — 서울은 구("강남구"), 서울 밖은 시("수원시"·"광주광역시")
    bizinfo_tag: str             # "서울" · "전남광주"

    @property
    def label(self) -> str:
        return f"{self.sido} {self.local}" if self.local and self.local not in self.sido else self.sido

    def as_dict(self) -> dict:
        return {"sido": self.sido, "local": self.local, "label": self.label}


def region_of(district_id: str) -> Region | None:
    d = svc.get_district(district_id)
    if not d:
        return None
    c = svc.page_city(d)
    tags = _SIDO_TAGS.get(c.sido, (c.short,))
    # 서울은 거점에 구가 있다. 서울 밖 거점의 gu 는 도시 약칭(「수원」)이라 구를 모른다 — 시 단위까지만 맞춘다.
    local = d.get("gu") if c.id == "seoul" else c.name.replace("특례시", "시")
    return Region(sido=c.sido, tags=tags, city=c.name, local=local,
                  bizinfo_tag=_BIZINFO_TAG.get(c.sido, tags[0]))


# ── 공통 ───────────────────────────────────────────────────────────────────
_YMD = re.compile(r"(\d{4})[-.]?(\d{2})[-.]?(\d{2})")


def parse_ymd(s: object) -> date | None:
    m = _YMD.search(str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_range(s: object) -> tuple[date | None, date | None]:
    """"20220727 ~ 20220930" · "2026-11-01~2026-11-20" → (시작, 끝). 하나만 있으면 둘 다 그 날."""
    found = []
    for m in _YMD.finditer(str(s or "")):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    if not found:
        return None, None
    return found[0], found[-1]


def clean(s: object, limit: int | None = None) -> str | None:
    """원문 정리 — HTML 엔티티·태그·연속 공백. 자를 때는 「…」를 붙인다(원문 발췌임을 드러낸다)."""
    if s is None:
        return None
    t = re.sub(r"<[^>]+>", " ", unescape(str(s)))
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    if limit and len(t) > limit:
        t = t[:limit].rstrip() + "…"
    return t


def industry_terms(industry: str | None) -> list[str]:
    """「카페·디저트」 → ["카페", "디저트"]. 두 글자 미만은 버린다(오탐)."""
    if not industry:
        return []
    return [t for t in re.split(r"[·,/\s]+", industry) if len(t) >= 2]


def _mentions(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in text]


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ── K-Startup ─────────────────────────────────────────────────────────────
def is_network_category(category: str | None) -> bool:
    return bool(category) and "행사" in category


def kstartup_item(r: dict, region: Region, stage: str | None, terms: list[str], today: date) -> dict | None:
    regin = clean(r.get("supt_regin")) or ""
    regins = [v.strip() for v in regin.split(",") if v.strip()]
    if "전국" not in regins and not any(v in region.tags for v in regins):
        return None
    enyy = [v.strip() for v in str(r.get("biz_enyy") or "").split(",") if v.strip()]
    if stage == "pre_founder" and "예비창업자" not in enyy:
        return None
    if stage == "founder" and not any(v in _FOUNDER_ENYY for v in enyy):
        return None
    start, end = parse_ymd(r.get("pbanc_rcpt_bgng_dt")), parse_ymd(r.get("pbanc_rcpt_end_dt"))
    if end and end < today:
        return None
    title = clean(r.get("biz_pbanc_nm")) or clean(r.get("intg_pbanc_biz_nm")) or "(공고명 없음)"
    category = clean(r.get("supt_biz_clsfc"))
    summary = clean(r.get("pbanc_ctnt"), _SUMMARY_MAX)
    target = clean(r.get("aply_trgt_ctnt"), _SUMMARY_MAX) or clean(r.get("aply_trgt"))
    sn = clean(r.get("pbanc_sn"))
    matched = [f"지역: {regin}"]
    if stage:
        matched.append(f"단계: {STAGES[stage]}")
    if (hits := _mentions(" ".join(filter(None, [title, summary, target])), terms)):
        matched.append("업종 언급: " + "·".join(hits))
    return {
        "source": "kstartup", "source_label": src.SOURCE_LABEL["kstartup"], "id": f"ks-{sn or r.get('id')}",
        "title": title, "org": clean(r.get("pbanc_ntrp_nm")), "region": regin, "category": category,
        "target": target, "start": _iso(start), "end": _iso(end), "deadline_text": None,
        "url": src.KSTARTUP_DETAIL.format(sn=sn) if sn else clean(r.get("detl_pg_url")),
        "apply_url": clean(r.get("biz_aply_url")), "summary": summary, "matched": matched,
    }


# ── 정부24 혜택 ────────────────────────────────────────────────────────────
def gov24_region(r: dict, region: Region) -> str | None:
    """정부24 혜택이 이 거점 지역 것인가 — 맞으면 이유 문구, 아니면 None.

    중앙행정기관·공공기관 → 전국. 광역시도 → 시도 이름. 시군구 → 「서울특별시 성동구」처럼 시도 + 시군구.
    지방 출자·출연기관·지방공기업 → 이름에 지역이 있을 때만(없으면 어느 지역 기관인지 모른다).
    「경기도 광주시」가 광주(전남광주) 거점에 섞이지 않도록 시군구는 시 이름 전체(「광주광역시」)로 맞춘다.
    """
    typ = str(r.get("소관기관유형") or "")
    org = str(r.get("소관기관명") or "")
    in_sido = region.sido in org or region.city in org or any(t in org for t in region.tags)
    if typ in ("중앙행정기관", "공공기관"):
        return "전국(중앙·공공기관)"
    if typ == "광역시도":
        return f"지역: {org}" if in_sido else None
    if typ == "시군구":
        return f"지역: {org}" if (in_sido and region.local and region.local in org) else None
    return f"지역 기관: {org}" if any(t in org for t in region.tags) else None


def gov24_item(r: dict, region: Region, stage: str | None, terms: list[str]) -> dict | None:
    why = gov24_region(r, region)
    if not why:
        return None
    title = clean(r.get("서비스명")) or "(서비스명 없음)"
    target = clean(r.get("지원대상"), _SUMMARY_MAX)
    summary = clean(r.get("서비스목적요약"), _SUMMARY_MAX) or clean(r.get("지원내용"), _SUMMARY_MAX)
    text = " ".join(filter(None, [title, target, summary, clean(r.get("선정기준"))]))
    startup = "창업" in text or "예비" in text or str(r.get("서비스분야") or "") == "고용·창업"
    if stage == "pre_founder" and not startup:
        return None          # 영업 중 사업자만 받는 혜택은 예비창업자에게 소음이다
    matched = [why]
    if stage:
        matched.append(f"단계: {STAGES[stage]}" + (" · 창업 언급" if startup else ""))
    if (hits := _mentions(text, terms)):
        matched.append("업종 언급: " + "·".join(hits))
    return {
        "source": "gov24", "source_label": src.SOURCE_LABEL["gov24"], "id": f"gov24-{r.get('서비스ID')}",
        "title": title, "org": clean(r.get("소관기관명")), "region": None, "category": clean(r.get("서비스분야")),
        "target": target, "start": None, "end": None, "deadline_text": clean(r.get("신청기한"), 120),
        "url": clean(r.get("상세조회URL")), "apply_url": None, "summary": summary, "matched": matched,
    }


# ── 기업마당 지원사업정보 ────────────────────────────────────────────────────
def _pick(r: dict, *keys: str) -> object:
    for k in keys:
        if r.get(k) not in (None, ""):
            return r.get(k)
    return None


def bizinfo_item(r: dict, region: Region, stage: str | None, terms: list[str], today: date) -> dict | None:
    start, end = parse_range(_pick(r, "reqstBeginEndDe", "reqstDt"))
    if end and end < today:
        return None
    title = clean(_pick(r, "pblancNm", "title")) or "(공고명 없음)"
    category = clean(_pick(r, "pldirSportRealmLclasCodeNm", "lcategory"))
    summary = clean(_pick(r, "bsnsSumryCn", "description"), _SUMMARY_MAX)
    target = clean(r.get("trgetNm"))
    text = " ".join(filter(None, [title, summary, target, category, clean(r.get("hashTags"))]))
    startup = "창업" in text
    if stage == "pre_founder" and not startup:
        return None
    inst = clean(_pick(r, "jrsdInsttNm", "author"))
    inst_sido = sido_of_org(inst)
    if inst_sido and inst_sido != region.sido:
        return None          # 다른 시도청 공고 — 해시태그는 17개 시도를 다 달아 거르지 못한다(위 _SIDO_GOV)
    matched = [f"지역: {inst}" if inst_sido else f"전국({inst or '중앙·공공기관'})"]
    if stage:
        matched.append(f"단계: {STAGES[stage]}" + (" · 창업 언급" if startup else ""))
    if (hits := _mentions(text, terms)):
        matched.append("업종 언급: " + "·".join(hits))
    pid = clean(_pick(r, "pblancId", "seq"))
    return {
        "source": "bizinfo", "source_label": src.SOURCE_LABEL["bizinfo"], "id": f"biz-{pid}",
        "title": title, "org": inst, "region": region.bizinfo_tag if inst_sido else "전국",
        "category": category, "target": target, "start": _iso(start), "end": _iso(end),
        "deadline_text": None if end else clean(_pick(r, "reqstBeginEndDe", "reqstDt"), 60),
        "url": clean(_pick(r, "pblancUrl", "link")), "apply_url": clean(r.get("rceptEngnHmpgUrl")),
        "summary": summary, "matched": matched,
    }


# ── 묶기 ───────────────────────────────────────────────────────────────────
_SOURCE_ORDER = {"kstartup": 0, "bizinfo": 1, "gov24": 2}


# 기업마당 제목 머리 「[경기] 안성시 …」·「[전남광주] 해남군 …」 — 그 시·군 주민·기업 대상인 경우가 많다.
_TITLE_CITY = re.compile(r"^\s*\[[^\]]{1,8}\]\s*([가-힣]{1,6}(?:시|군|구))(?=\s|$|[(\[ㆍ·,])")


def region_rank(it: dict, region: Region) -> int:
    """지역이 좁을수록 앞 — 0 내 시군구 · 1 시도 · 2 전국 · 3 같은 시도의 **다른** 시군구.

    원천마다 지역 필드가 달라서(K-Startup supt_regin · 정부24 소관기관 · 기업마당 소관기관·행사 개최지) 항목이 이미 단
    「지역」 칩과 지역 칸으로 가르고, 기업마당 제목 머리의 시·군 이름을 본다. 다른 시·군 공고는 대개 그 시·군 주민·기업만
    신청할 수 있어 전국 공고 뒤로 보낸다. **걸러 내지 않는다** — 순서만 바꾼다. 11-08 실측에서 마감 순으로만 세우자 강남
    카페 예비창업자 화면 맨 위에 「청년 어촌창업 공모전」(전국), 네트워킹 맨 위에 경남·충주 기관 공고(전국)가 섰다.
    """
    chips = [m for m in it.get("matched", []) if m.startswith(("지역", "전국"))]
    text = " ".join(chips + [str(it.get("region") or it.get("area") or "")])
    if not text.strip() or "전국" in text:
        return 2
    local = region.local if region.local and region.local != region.sido else None
    if local and local in text:
        return 0
    if (m := _TITLE_CITY.match(str(it.get("title") or ""))):
        return 0 if local and m.group(1) == local else 3
    return 1


def support_programs(district_id: str, stage: str | None = None, industry: str | None = None,
                     *, today: date | None = None) -> dict | None:
    region = region_of(district_id)
    if region is None:
        return None
    if stage not in (None, *STAGES):
        raise ValueError("stage 는 pre_founder · founder 중 하나다")
    today = today or events.today_kst()
    terms = industry_terms(industry)
    items: list[dict] = []
    statuses: list[dict] = []

    ks = src.kstartup_open()
    got = [it for r in ks.rows if not is_network_category(clean(r.get("supt_biz_clsfc")))
           if (it := kstartup_item(r, region, stage, terms, today))]
    items += got
    statuses.append(src.status_of("kstartup", ks, len(got)))

    bz = src.bizinfo("support", region.bizinfo_tag)
    got = [it for r in bz.rows if (it := bizinfo_item(r, region, stage, terms, today))]
    items += got
    statuses.append(src.status_of("bizinfo", bz, len(got)))

    gv = src.gov24_smallbiz()
    got = [it for r in gv.rows if (it := gov24_item(r, region, stage, terms))]
    items += got
    statuses.append(src.status_of("gov24", gv, len(got)))

    # 마감 임박 순 — 마감일이 있는 공고 먼저, 같은 날이면 업종 언급이 있는 것 먼저, 그다음 원천 순.
    def sort_key(it: dict) -> tuple:
        has_terms = any(m.startswith("업종 언급") for m in it["matched"])
        # 지역이 좁은 순 → 업종 언급 → 마감이 가까운 순(마감일 없는 혜택은 뒤) — 화면이 이 순서를 그대로 밝힌다
        return (region_rank(it, region), not has_terms, it["end"] is None, it["end"] or "",
                _SOURCE_ORDER[it["source"]], it["title"])

    items.sort(key=sort_key)
    return {
        "district_id": district_id, "region": region.as_dict(), "stage": stage, "industry": industry,
        "items": items[:_MAX_ITEMS], "total": len(items), "sources": statuses,
        "note": ("조건이 맞을 수 있는 공고입니다 — 지역·단계·업종 문구만 맞춰 봤어요. 자격·선정 여부와 "
                 "지원 금액은 공고 원문에서 확인하세요. 지원금은 Posting 회수기간 계산에 넣지 않아요."),
    }
