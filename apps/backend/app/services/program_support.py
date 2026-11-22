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
from app.services import program_sources as src

# founder 의 이름표는 2026-11-22 「기창업자(개업 후)」 — Program 네트워킹이 개업한 자리 기준으로 이 단계만 쓴다
# (그전 「기창업자(업종 바꾸기·상권 옮기기)」 · 지원 공고 매칭(/program/support)은 화면에서 뺐고 서버 경로만 남았다).
STAGES = {"pre_founder": "예비창업자", "founder": "기창업자(개업 후)"}
_FOUNDER_ENYY = ("1년미만", "2년미만", "3년미만", "5년미만", "7년미만", "10년미만")
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

