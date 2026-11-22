"""Humanistic Authority 후처리 검증 — 생성물이 프롬프트 지시를 실제로 지켰는지 서버가 확인한다.

## 왜 필요한가 (docs/feature-program.md §3-4 미이행분)

`ha_check` 는 **LLM 이 스스로 "점검 통과"라고 적은 문장**이다. 그게 사실인지 확인하는 코드는
없었다. 자기신고는 근거가 아니다 — 이 저장소가 실측처럼 보이는 추정치를 가장 나쁜 산출물로
보는 것과 같은 이유다(AGENTS.md §0).

## 두 등급으로 나누는 이유

- **violation(허위)** — 입력과 대조하면 참·거짓이 갈린다. 지어낸 금액, 서버가 이미 계산해
  확정한 트렌드 방향을 뒤집는 서술. 소상공인이 그대로 전단에 인쇄하면 실제 손해가 나므로
  **응답을 버리고 폴백으로 떨어뜨린다.**
- **warning(과장·편중 의심)** — 사전 매칭이라 오탐이 섞인다. 2026-08-01 동명이지 정제에서
  배운 것이 그대로 적용된다: 자동 규칙을 세게 걸면 진짜 상호명까지 죽는다(체험단 필터를
  포기한 이유). 그래서 **통과시키되 findings 로 밝혀 사람이 보게 한다.**

## 오탐을 어디서 끊었나 (규칙마다 근거가 있다)

- 금액: `1만원` 은 잡고 `1만 5천원` 같은 혼합 표기는 못 잡는다 — 아래 한계 참조.
- 트렌드: **주장과 목표를 가른다.** "손님이 늘고 있다"(주장)는 걸고 "손님을 늘리는
  전단"(목표)은 안 건다. 후자는 정당한 오프라인 제안이라 이걸 죽이면 기능이 망가진다.
- 최상급: 입력 텍스트에 같은 표현이 있으면 면제한다(창업자가 낸 차별점에 "최고"가
  있으면 인용할 근거가 있는 것이다). `최대한` 은 `최대` 로 오인되므로 스캔 전에 걷어낸다.
- 비방: `경쟁력` 은 비방이 아니라 제외한다.
- (2026-11-22: 검증 프로그램 생성(`check_program` — 미검증 경험 · 검증 지표 · 채널 균형 · 행사 인용 · 예산)과 그 입력 `program_brief` 를 지웠다.
  Program 이 개업한 자리의 네트워킹·오프라인 마케팅으로 좁혀졌다 → docs/decision-program-post-opening-2026-11-22.md. 상권 콘텐츠 검사만 남는다.)

## 알려진 한계

- 퍼센트 할인("10% 할인")은 금액 검사에 안 걸린다. 금액과 성격은 같지만 정상 표현과
  구분이 어려워 남겨 뒀다.
- `1만 5천원` 처럼 한자어 수 표기가 섞이면 금액 파싱이 놓친다.
- 사전 기반 검사(최상급·비방)는 우회가 쉽다. 이건 정직한 생성물을 확인하는 장치이지
  적대적 입력을 막는 장치가 아니다.
"""
from __future__ import annotations

import re

from app.schemas.marketing import HAFinding, LLMDistrictContents

# ── 금액 ─────────────────────────────────────────────────────────────────────
# "6,000원" / "6000 원" / "1만원". 앞의 숫자만 잡고 콤마는 지운다.
_PRICE_RE = re.compile(r"(\d[\d,]*)\s*원")
_MAN_PRICE_RE = re.compile(r"(\d[\d,]*)\s*만\s*원")

# ── 트렌드 방향 ───────────────────────────────────────────────────────────────
# marketing._trend_summary 가 만드는 형식: "신사동 하락(67.4→65.0, -3.6%)"
_TREND_LABEL_RE = re.compile(r"(상승|보합|하락)\(")

# 유입을 가리키는 말. 아래 '증가 주장'과 **같은 문장에** 있을 때만 위반으로 본다.
_INFLOW_WORDS = ("발걸음", "유입", "방문객", "방문자", "손님", "인파", "검색량",
                 "관심", "고객", "찾는", "찾아오", "붐빔")

# **주장**만 넣는다. "늘리는"(목표)은 일부러 뺐다 — "손님을 늘리는 전단"은 정당한 제안이다.
_INCREASE_CLAIMS = ("늘고 있", "늘어나", "늘어난", "늘었", "증가하고 있", "증가세",
                    "상승세", "많아지", "높아지고 있", "커지고 있", "회복세")

# 단독으로도 유입 증가를 주장하는 말 — 유입어와 짝지을 필요가 없다.
_STANDALONE_SURGE = ("붐비", "몰리", "북적", "문전성시")

# ── 최상급 ───────────────────────────────────────────────────────────────────
_SUPERLATIVES = ("최고", "최상", "최대", "최초", "유일", "1위", "1등", "완벽",
                 "압도적", "최강", "국내 최", "세계 최", "가장 맛있", "제일 맛있")
# "최대한"은 "최대"로 오인된다. 스캔 전에 지운다.
_SUPERLATIVE_NOISE = ("최대한",)

# ── 비방·출혈경쟁 ────────────────────────────────────────────────────────────
# "경쟁력"은 비방이 아니라서 뺐다.
_DISPARAGE = ("경쟁점", "경쟁업체", "경쟁 업체", "타 매장", "타매장", "다른 가게보다",
              "주변 가게보다", "이웃 가게보다", "주변보다 저렴", "최저가", "보다 우수")

_SENTENCE_RE = re.compile(r"[.!?\n]+")


def _prices(text: str) -> set[int]:
    """텍스트에서 원화 금액을 집합으로. "1만원" → 10000."""
    out: set[int] = set()
    for m in _MAN_PRICE_RE.finditer(text or ""):
        try:
            out.add(int(m.group(1).replace(",", "")) * 10_000)
        except ValueError:
            continue
    for m in _PRICE_RE.finditer(text or ""):
        # "1만원"은 숫자와 원 사이에 "만"이 끼어 여기서는 안 잡힌다(위에서 이미 처리했다).
        raw = m.group(1).replace(",", "")
        try:
            out.add(int(raw))
        except ValueError:
            continue
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text or "") if s.strip()]




def _check_prices(generated: str, allowed_text: str) -> list[HAFinding]:
    """생성물의 금액이 전부 입력에 있던 것인지. 없으면 지어낸 것이다."""
    allowed = _prices(allowed_text)
    invented = sorted(_prices(generated) - allowed)
    if not invented:
        return []
    shown = ", ".join(f"{v:,}원" for v in invented[:5])
    return [HAFinding(
        severity="violation", code="fabricated_price",
        message=(f"입력에 없는 금액 {len(invented)}건을 생성물이 말한다 — 가격은 입력에 적힌 "
                 "것만 쓸 수 있다. 지어낸 가격은 그대로 전단에 인쇄된다."),
        evidence=shown)]


def _check_trend(generated: str, context: str | None) -> list[HAFinding]:
    """서버가 확정한 트렌드 방향(하락·보합)을 생성물이 뒤집는지.

    2026-08-01 실사고가 이 검사의 이유다 — 입력이 하락인데 생성 카피가
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다.
    상승이 하나라도 섞여 있으면 증가 서술이 정당할 수 있으므로 걸지 않는다.

    ## 못 돌린 것과 통과한 것을 가른다 (2026-09-16 fail-open 차단)

    종전에는 컨텍스트나 트렌드 라벨이 없으면 `[]` 를 돌려줬다. 그러면 응답에서
    **"검사했고 깨끗하다"와 "검사 자체를 못 했다"가 똑같이 보인다.** 이 검사는
    violation 등급이라 응답을 버리는 힘이 있는데, 입력 하나가 비면 그 힘이 조용히
    사라진다 — `pppp_status` 가 트렌드 라벨 게이트를 세우며 적어 둔 위험이 이것이다
    ("라벨이 없으면 트렌드 역행 검사가 조용히 통과한다").

    그래서 못 돌렸을 때는 `trend_unverified` 를 남긴다. 등급은 **warning** 이다 —
    검사 불가는 허위의 증거가 아니므로 응답을 버릴 근거가 못 되지만, 무엇이 검증
    안 됐는지는 드러나야 한다(§0-3 의 '통과시키되 findings 로 밝힌다'와 같은 처리).
    """
    if not context:
        return [HAFinding(
            severity="warning", code="trend_unverified",
            message=("상권 컨텍스트가 없어 트렌드 역행 검사를 돌리지 못했다 — "
                     "이 응답은 '트렌드를 뒤집지 않았다'가 검증된 것이 아니다."),
            evidence="context=None")]
    labels = set(_TREND_LABEL_RE.findall(context))
    if not labels:
        return [HAFinding(
            severity="warning", code="trend_unverified",
            message=("컨텍스트에 트렌드 라벨(상승/보합/하락)이 없어 역행 검사를 "
                     "돌리지 못했다 — 검색 트렌드 수집이 비었을 때 이 값이 뜬다."),
            evidence="라벨 0건")]
    if "상승" in labels:
        return []

    for sent in _sentences(generated):
        surge = next((w for w in _STANDALONE_SURGE if w in sent), None)
        claim = next((w for w in _INCREASE_CLAIMS if w in sent), None)
        inflow = any(w in sent for w in _INFLOW_WORDS)
        if surge or (claim and inflow):
            return [HAFinding(
                severity="violation", code="trend_contradiction",
                message=(f"검색 트렌드가 {'·'.join(sorted(labels))}인데 생성물이 유입 증가를 "
                         "주장한다 — 방향은 서버가 계산해 확정한 값이다."),
                evidence=sent[:120])]
    return []


def _check_superlatives(generated: str, source_text: str) -> list[HAFinding]:
    """근거 없는 최상급. 입력에 같은 표현이 있으면 인용할 근거가 있으므로 면제한다."""
    haystack = generated
    for noise in _SUPERLATIVE_NOISE:
        haystack = haystack.replace(noise, "")
    hits = [w for w in _SUPERLATIVES if w in haystack and w not in (source_text or "")]
    if not hits:
        return []
    return [HAFinding(
        severity="warning", code="unsupported_superlative",
        message=("입력에 근거가 없는 최상급 표현이다 — 검증 불가한 최상급은 쓰지 않는다. "
                 "(사전 매칭이라 오탐일 수 있으니 눈으로 확인하라)"),
        evidence=", ".join(hits[:5]))]


def _check_disparagement(generated: str) -> list[HAFinding]:
    """이웃 가게 비방·출혈 경쟁 조장 — 공생(Symbiosis) 원칙 위반."""
    hits = [w for w in _DISPARAGE if w in (generated or "")]
    if not hits:
        return []
    return [HAFinding(
        severity="warning", code="competitor_disparagement",
        message=("이웃 가게와의 비교·출혈 경쟁을 암시한다 — 상권 공동 활성화(공생)를 해친다. "
                 "(사전 매칭이라 오탐일 수 있으니 눈으로 확인하라)"),
        evidence=", ".join(hits[:5]))]





# ── 새 출력 계약(2026-08-23) 검증 ────────────────────────────────────────────
# 스키마가 필드의 **존재**를 강제해도 내용이 규칙을 지켰는지는 서버가 봐야 한다.
# `ha_check` 가 자기신고라 근거가 아닌 것과 같은 이유다(§0-3).






def check_district(parsed: LLMDistrictContents, context: str) -> list[HAFinding]:
    """상권 단위 온라인 카피 검증.

    상권 컨텍스트에는 가격 정보가 없다(키워드 빈도·업종 분포·트렌드뿐). 그래서 카피에
    나오는 금액은 근거가 컨텍스트에 있지 않는 한 지어낸 값이다.
    """
    # 줄바꿈으로 잇는 이유는 check_program 과 같다 — 카피 하나의 주장이 옆 카피의
    # 표현과 한 문장으로 읽히면 문장 단위 판정이 어긋난다.
    generated = "\n".join([*parsed.online_contents, parsed.ha_check or ""])
    return [
        *_check_prices(generated, context or ""),
        *_check_trend(generated, context),
        *_check_superlatives(generated, context or ""),
        *_check_disparagement(generated),
    ]


def has_violation(findings: list[HAFinding]) -> bool:
    """폐기해야 하는 등급이 섞여 있는가."""
    return any(f.severity == "violation" for f in findings)


def summarize(findings: list[HAFinding]) -> str:
    """로그 한 줄용 요약."""
    return "; ".join(f"[{f.severity}] {f.code}={f.evidence or '-'}" for f in findings)
