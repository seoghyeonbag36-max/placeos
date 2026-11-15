"""지원 공고 매칭 정밀도 — 표본 동결 (사전등록 2026-11-15).

사전등록: docs/prereg-program-support-precision-2026-11-15.md. 채점: `score_support_labels.py`.

**짝 = 같은 질의(거점·단계·업종)에 대한 M(매칭이 보여 준 공고) 한 건 + C(그 질의에는 걸러졌지만 거점도 단계도 다른 질의에는 보인
공고) 한 건.** 라벨러에게는 두 줄로 섞어서 주고, 어느 쪽인지는 `key.csv` 에만 둔다(`labels.csv` 에 팔·매칭 표시·화면 순서가 없다).

순수 로직(`draw_districts` · `frame` · `build_design` · `write_sample`)은 호출기를 받아 테스트가 가짜로 돌린다.
라이브 호출은 `--freeze` 일 때만 — `program_support.support_programs` 가 키(K-Startup·정부24 = DATA_GO_KR_SERVICE_KEY ·
기업마당 = BIZINFO_SUPPORT_API_KEY)를 `app.core.config.settings` 로 읽는다. 키가 없으면 원천이 `no_key` 로 비어 동결하지 않는다.

실행(키가 있는 환경에서 한 번):
  python -m data.validation.support_sample --freeze

이미 있는 표본 폴더는 **덮어쓰지 않는다**(라벨이 달려 있을 수 있다) — 다시 뽑으려면 폴더를 직접 치우고 새 사전등록을 한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_OUT = Path(__file__).resolve().parent
_ROOT = _OUT.parents[1]

from data.validation.score_support_labels import KPI_SAMPLE_TAG  # noqa: E402

STAGES = ("pre_founder", "founder")
STAGE_NAME = {"pre_founder": "예비창업자", "founder": "기창업자(업종 바꾸기·상권 옮기기)"}
INDUSTRIES = ("카페·디저트", "음식점", "미용·네일")      # business_fit.INDUSTRIES 의 라벨
N_DISTRICTS, PAIRS_PER_STAGE, SEED = 4, 25, 20261115
_MAX_DRAWS = 2000                                      # 단계마다 짝을 못 채울 때 무한 반복을 막는 상한
# 라벨러에게 보이는 공고 필드 — 매칭 표시(`matched`)·팔·순서는 넣지 않는다
SHOWN = ("title", "org", "target", "region", "summary", "end", "deadline_text", "url")
_HEAD = ["id", "지역", "단계", "업종", "공고명", "기관", "신청대상", "지역표기", "요약", "마감", "링크", "라벨", "메모"]


def qid(district: str, stage: str, industry: str) -> str:
    return f"{district}|{stage}|{industry}"


def parse_qid(q: str) -> tuple[str, str, str]:
    d, s, i = q.split("|")
    return d, s, i


def draw_districts(slugs: list[str], n: int = N_DISTRICTS, seed: int = SEED) -> list[str]:
    """서울 서빙 거점 슬러그를 정렬한 목록에서 n 곳 — 결정적이다."""
    return sorted(random.Random(seed).sample(sorted(slugs), n))


def frame(districts: list[str]) -> list[str]:
    return [qid(d, s, i) for d in districts for s in STAGES for i in INDUSTRIES]


def _slim(item: dict) -> dict:
    keep = ("id", "source", "title", "org", "target", "region", "summary", "end", "deadline_text", "url", "matched")
    return {k: item.get(k) for k in keep}


def build_design(outputs: dict[str, list[dict]], seed: int = SEED, per_stage: int = PAIRS_PER_STAGE) -> dict:
    """질의별 매칭 결과 → 짝 표본. 결정적이다(정렬된 입력 · 고정 seed).

    M: 단계마다 질의를 균등 복원 추출 → 그 질의 결과에서 공고를 균등 비복원 추출(같은 질의·공고는 한 번만).
    C: 같은 질의 q 에 대해 거점도 단계도 q 와 다른 질의들의 결과를 합친 풀에서, q 자신의 결과에 없는 공고를 id 기준 균등 추출.
    C 풀이 비면 그 짝은 버리고 센다.
    """
    rng = random.Random(seed)
    usable = sorted(q for q, items in outputs.items() if items)
    excluded = sorted(q for q, items in outputs.items() if not items)
    by_id: dict[str, dict[str, dict]] = {q: {it["id"]: it for it in outputs[q]} for q in usable}
    pairs: list[dict] = []
    dropped = 0
    for stage in STAGES:
        qs = [q for q in usable if parse_qid(q)[1] == stage]
        if not qs:
            continue
        used: set[tuple[str, str]] = set()
        made = draws = 0
        while made < per_stage and draws < _MAX_DRAWS:
            draws += 1
            q = rng.choice(qs)
            cands = sorted(i for i in by_id[q] if (q, i) not in used)
            if not cands:
                continue
            m_id = rng.choice(cands)
            d, s, _ = parse_qid(q)
            pool: dict[str, dict] = {}
            for q2 in usable:
                d2, s2, _ = parse_qid(q2)
                if d2 == d or s2 == s:
                    continue
                for i2, it2 in by_id[q2].items():
                    if i2 not in by_id[q]:
                        pool.setdefault(i2, it2)
            if not pool:
                dropped += 1
                continue
            c_id = rng.choice(sorted(pool))
            used.add((q, m_id))
            made += 1
            pairs.append({"qid": q, "district": d, "stage": s, "industry": parse_qid(q)[2],
                          "M": _slim(by_id[q][m_id]), "C": _slim(pool[c_id])})
    for n, p in enumerate(pairs, 1):
        p["pair_id"] = f"P{n:03d}"
    return {"seed": seed, "per_stage": per_stage, "n_pairs": len(pairs), "n_dropped": dropped,
            "queries_used": usable, "excluded_queries": excluded, "pairs": pairs}


GUIDE = """# 지원 공고 라벨 안내 — 사전등록 2026-11-15

`labels.csv` 의 **라벨** 칸을 줄마다 채운다(메모는 선택). 한 줄 = 「창업자 상황(지역·단계·업종)」 + 공고 하나.
공고는 표본을 뽑은 날 **동결한 원문**이다 — 링크를 열어 최신 내용을 보지 않는다(최신 공고와 다를 수 있다).

| 라벨 | 뜻 |
|---|---|
| `맞을 수 있음` | 보이는 원문이 그 창업자(지역·단계)를 **명백히 배제하지 않는다** — 자격 판정이 아니다 |
| `맞지 않음` | 원문이 명백히 배제한다 — ① 지역: 다른 시도·시군구 주민·기업만 대상 ② 단계: 예비창업자 상황인데 사업자등록 후 기업만 대상, 또는 기창업자 상황인데 예비창업자만 대상 ③ 창업자가 아닌 신청 주체만 대상(연구기관·지자체 등) |
| `판단 불가` | 대상·지역 정보가 원문에 없어 가를 수 없다 — 채점에서 빠진다 |

- **업종**이 안 맞는 것은 `맞지 않음` 사유가 아니다(업종은 거르는 기준이 아니다).
- 빈칸은 미응답이다. **추측해서 채우지 않는다** — 모르겠으면 `판단 불가`.
- 어느 줄이 시스템이 보여 준 공고인지는 알려 주지 않는다. 알려고 하지 않는다.
- 규칙: docs/prereg-program-support-precision-2026-11-15.md §3
"""


def write_sample(design: dict, out_dir: Path, *, district_labels: dict[str, str] | None = None,
                 frozen_at: str | None = None, source_status: list[dict] | None = None) -> Path:
    """표본 폴더를 쓴다. 이미 있으면 덮지 않는다(라벨이 달려 있을 수 있다)."""
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} 가 이미 있다 — 라벨이 달려 있을 수 있어 덮어쓰지 않는다")
    out_dir.mkdir(parents=True)
    labels = district_labels or {}
    order = [(p, arm) for p in design["pairs"] for arm in ("M", "C")]
    random.Random(design["seed"] + 1).shuffle(order)           # 라벨러가 팔·짝을 짐작하지 못하게 섞는다
    rows, key = [], []
    for n, (p, arm) in enumerate(order, 1):
        it = p[arm]
        rid = f"R{n:03d}"
        shown = {k: ("" if it.get(k) is None else it[k]) for k in SHOWN}
        rows.append({"id": rid, "지역": labels.get(p["district"], p["district"]), "단계": STAGE_NAME[p["stage"]],
                     "업종": p["industry"], "공고명": shown["title"], "기관": shown["org"], "신청대상": shown["target"],
                     "지역표기": shown["region"], "요약": shown["summary"],
                     "마감": shown["end"] or shown["deadline_text"], "링크": shown["url"], "라벨": "", "메모": ""})
        key.append({"id": rid, "pair_id": p["pair_id"], "arm": arm, "qid": p["qid"], "stage": p["stage"],
                    "source": it.get("source") or "", "notice_id": it["id"]})
    with (out_dir / "labels.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=_HEAD)
        w.writeheader()
        w.writerows(rows)
    with (out_dir / "key.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["id", "pair_id", "arm", "qid", "stage", "source", "notice_id"])
        w.writeheader()
        w.writerows(key)
    items = {}
    for p in design["pairs"]:
        for arm in ("M", "C"):
            items[p[arm]["id"]] = p[arm]
    (out_dir / "frozen_items.json").write_text(json.dumps({"frozen_at": frozen_at, "items": items},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {k: design[k] for k in ("seed", "per_stage", "n_pairs", "n_dropped", "queries_used", "excluded_queries")}
    meta.update({"frozen_at": frozen_at, "source_status": source_status or [],
                 "districts": sorted({parse_qid(q)[0] for q in design["queries_used"] + design["excluded_queries"]}),
                 "industries": list(INDUSTRIES), "prereg": "docs/prereg-program-support-precision-2026-11-15.md",
                 "pairs": [{"pair_id": p["pair_id"], "qid": p["qid"], "M": p["M"]["id"], "C": p["C"]["id"]}
                           for p in design["pairs"]]})
    (out_dir / "design.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "GUIDE.md").write_text(GUIDE, encoding="utf-8")
    return out_dir


def _live() -> tuple[dict[str, list[dict]], dict[str, str], list[dict]]:
    """질의 틀을 라이브 매칭으로 채운다 — 키가 있는 환경에서만 의미가 있다."""
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "apps" / "backend"))
    from app.services import program_support as PS
    from data.config.page_hubs import ACTIVE_HUBS

    seoul = [s for s, h in ACTIVE_HUBS.items() if h.city == "seoul"]
    districts = draw_districts(seoul)
    outputs: dict[str, list[dict]] = {}
    status: dict[str, dict] = {}
    dlabels: dict[str, str] = {}
    for q in frame(districts):
        d, s, i = parse_qid(q)
        got = PS.support_programs(d, s, i)
        outputs[q] = (got or {}).get("items", [])
        if got:
            dlabels[d] = got["region"]["label"]
            for st in got.get("sources", []):
                status[st.get("id") or st.get("source") or str(len(status))] = st
    return outputs, dlabels, list(status.values())


def main() -> None:
    ap = argparse.ArgumentParser(description="지원 공고 매칭 정밀도 표본 동결")
    ap.add_argument("--freeze", action="store_true", help="라이브 매칭으로 표본을 뽑아 동결한다")
    ap.add_argument("--tag", default=KPI_SAMPLE_TAG)
    args = ap.parse_args()
    if not args.freeze:
        raise SystemExit("--freeze 를 줘야 한다 — 라이브 호출로 표본을 뽑는다(키 필요)")
    out_dir = _OUT / f"support_sample_{args.tag}"
    if out_dir.exists():
        raise SystemExit(f"[support-sample] {out_dir} 가 이미 있다 — 덮어쓰지 않는다(라벨이 달려 있을 수 있다)")
    outputs, dlabels, status = _live()
    total = sum(len(v) for v in outputs.values())
    bad = [s for s in status if s.get("status") not in (None, "ok")]
    print(f"[support-sample] 질의 {len(outputs)} · 매칭 공고 합계 {total} · 원천 상태 {[(s.get('id'), s.get('status')) for s in status]}")
    if not total:
        raise SystemExit("[support-sample] 매칭 결과가 하나도 없다 — 키(DATA_GO_KR_SERVICE_KEY 등)가 없거나 원천이 응답하지 않았다. 동결하지 않는다")
    design = build_design(outputs)
    frozen_at = datetime.now(timezone.utc).isoformat()
    write_sample(design, out_dir, district_labels=dlabels, frozen_at=frozen_at, source_status=status)
    print(f"[support-sample] 동결 → {out_dir} · 짝 {design['n_pairs']} · 버린 짝 {design['n_dropped']} · 비어 있던 질의 {len(design['excluded_queries'])}")
    if bad:
        print(f"⚠ 상태가 ok 가 아닌 원천: {[(s.get('id'), s.get('status')) for s in bad]} — 결과 옆에 적는다(사전등록 §5-4)")
    print("다음: labels.csv 의 라벨 칸을 채운다(사람 몫) → python -m data.validation.score_support_labels")


if __name__ == "__main__":
    main()
