"""[Proposal 메뉴 설정] 농식품부 「2025 외식업체 경영실태 조사 통계보고서」 PDF → gold/mafra_dining_2025.json.

    python data/pipelines/build_mafra_dining_2025.py <보고서 PDF 경로>

## 왜 이 파일이 필요한가
메뉴 설정(2026-11-26 사용자 요청)은 「선택한 업종 · 개인사업/가맹점에 맞는 메뉴 · 판매가 · 원가 · 비중 평균값, 재료값 · 장비값,
월 영업일 · 영업 시간 · 고정비」를 보여 달라고 했다. 이 보고서가 그 숫자들의 공식 원천이다. 손으로 옮겨 적은 표는 낡아도 아무도
모르므로(이 저장소의 주된 실패 양식) PDF 에서 뽑아 산출물로 떨군다. 원문 PDF 는 bronze 성격이라 커밋하지 않고 SHA-256 만 남긴다.
원문 내려받기는 이 저장소의 클라우드 작업 환경에서 막혀(해외 접속 차단) 사용자가 받아 준 파일로 만들었다(2026-11-26).

## 무엇을 뽑나 — 표마다 「평균」 열 하나와 사례수
- 업종(소분류 행) · 운영형태(「프랜차이즈」 · 「비프랜차이즈」 행) · 전체. ⚠ 표는 **한 축씩** 나눈다 — 업종 × 운영형태 교차는 없다.
  그래서 개인사업/가맹점 차이는 **외식업 전체** 기준으로만 말할 수 있다(업종 안에서 나눈 값을 만들지 않는다).
- 운영형태: 「비프랜차이즈」 = 독립운영(개인경영권), 「프랜차이즈」 = 가맹점 + 본사직영(표 30 — 본사직영은 전체의 1.8%).
- 표 24 영업시간 · 25 월 영업일 · 31~34 개업 투자비(전체 · 인테리어 · 주방 · 홀) · 67 객단가 · 95~104 매출과 비용 항목.
- 표 68~86 대표메뉴별 가격(업종별) — 메뉴 · 응답 수(사례수) · 평균 가격. 응답 수는 「그 메뉴를 대표메뉴로 꼽은 업체 수」지 판매 비중이 아니다.
- 표 105 품목별 식재료비 비중(평균 · %) — 쌀 · 곡류 · 채소 · 과일 · 육류 · 수산물 · 가공식품 · 기타 · 주류(2026-11-27 · 메뉴 설정 「식재료비」 칸).
  행마다 합이 100 에 가까워야 한다(±1.5 · 반올림).

## 단위 — 매출 · 비용(표 95~104)은 연간으로 읽는다
매출액 구간이 「1억~5억 원 미만」 71.6% · 「5억 원 이상」 8.2%라 월 기준일 수 없다. 화면은 ÷12 로 월을 낸다.

## 검산(실패하면 멈춘다)
- 행마다 매출 − 영업비용 = 영업이익, 비용 항목(식재료비 · 고용인 인건비 · 임차료 · 세금과 공과 · 가족 종사자 인건비 · 대표자 인건비 ·
  기타비용) 합 = 영업비용 — 둘 다 ±0.5만 원(반올림) 안.
- 저장소에 먼저 옮겨 둔 값(services/industry_benchmarks.ROWS · 표 25 · 67)과 같아야 한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "gold" / "mafra_dining_2025.json"

TABLES = {24: ("open_hours", "시간"), 25: ("open_days", "일"), 31: ("invest_total", "만원"), 32: ("invest_interior", "만원"),
          33: ("invest_kitchen", "만원"), 34: ("invest_hall", "만원"), 67: ("avg_ticket", "원"), 95: ("sales", "만원/년"),
          96: ("opex", "만원/년"), 97: ("food_cost", "만원/년"), 98: ("labor", "만원/년"), 99: ("rent", "만원/년"),
          100: ("tax", "만원/년"), 101: ("family_labor", "만원/년"), 102: ("owner_pay", "만원/년"), 103: ("other_cost", "만원/년"),
          104: ("profit", "만원/년")}
ROWS = ["■ 전체 ■", "한식", "중식 음식점업", "일식 음식점업", "서양식 음식점업", "기타 외국식 음식점업", "제과", "피자·햄버거·샌드위치",
        "치킨 전문점", "김밥 및 기타 간이음식점업", "간이 음식 포장 판매 전문점", "생맥주 전문점", "기타 주점업", "커피 전문점",
        "기타 비알코올 음료점업", "프랜차이즈", "비프랜차이즈"]
MENU_TABLES = {69: "한식", 70: "중식 음식점업", 71: "일식 음식점업", 72: "서양식 음식점업", 73: "기타 외국식 음식점업", 76: "제과",
               77: "피자·햄버거·샌드위치", 78: "치킨 전문점", 79: "김밥 및 기타 간이음식점업", 80: "간이 음식 포장 판매 전문점",
               83: "생맥주 전문점", 84: "기타 주점업", 85: "커피 전문점", 86: "기타 비알코올 음료점업"}
COST_PARTS = ["food_cost", "labor", "rent", "tax", "family_labor", "owner_pay", "other_cost"]
FOOD_MIX_TABLE = 105
FOOD_MIX_COLUMNS = ["쌀", "곡류(쌀 제외)", "채소", "과일", "육류", "수산물", "가공식품(공산품)", "기타", "주류"]
NUM = r"-?[\d,]+(?:\.\d+)?"
SEG = re.compile(r"([^\d\s][^\d]*?)\s+(\d[\d,]*)\s+(\d[\d,]*)(?=\s|$)")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _pages(pdf: Path) -> list[str]:
    """쪽별 텍스트(pdftotext -layout). 표 머리는 쪽마다 다시 찍히므로 쪽 단위로 다룬다."""
    with tempfile.TemporaryDirectory() as tmp:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        n = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
        out = []
        for p in range(1, n + 1):
            dst = Path(tmp) / f"p{p}.txt"
            subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), str(dst)], check=True)
            out.append(dst.read_text(encoding="utf-8"))
        return out


def _index(pages: list[str]) -> dict[int, list[tuple[int, str, int]]]:
    """표 번호 → [(PDF 쪽, 제목, 인쇄 쪽)]. 앞쪽 목차(25쪽 전)는 건너뛴다."""
    idx: dict[int, list[tuple[int, str, int]]] = {}
    for i, text in enumerate(pages, start=1):
        if i < 25:
            continue
        printed = re.findall(r"^\s*(\d{1,3})\s*$", text, re.M)
        for m in re.finditer(r"<표 (\d+)>\s*([^\n]*)", text):
            idx.setdefault(int(m.group(1)), []).append((i, m.group(2).strip(), int(printed[-1]) if printed else 0))
    return idx


def _row_all(lines: list[str], label: str) -> list[float] | None:
    """그 행의 수 전부(사례수 다음 칸들). 「피자·햄버거·샌드위치」는 수가 가운데 「음식점」 줄에 있다."""
    if label == "피자·햄버거·샌드위치":
        for i, ln in enumerate(lines):
            if label in ln:
                for nxt in lines[i:i + 3]:
                    m = re.search(r"음식점\s+(" + NUM + r"(?:\s+" + NUM + r")+)\s*$", nxt)
                    if m:
                        return [_num(x) for x in re.findall(NUM, m.group(1))]
        return None
    pat = (r"(?<!비)" if label == "프랜차이즈" else "") + re.escape(label) + r"\s+(" + NUM + r"(?:\s+" + NUM + r")+)\s*$"
    for ln in lines:
        m = re.search(pat, ln)
        if m and not re.search(re.escape(label) + r"\s+\S*[가-힣]", ln):
            return [_num(x) for x in re.findall(NUM, m.group(1))]
    return None


def _row(lines: list[str], label: str) -> tuple[float, float] | None:
    """(사례수, 평균) — 평균은 그 줄의 마지막 수다. 「한식 일반음식점업」 같은 세분류 줄은 고르지 않는다."""
    if label == "피자·햄버거·샌드위치":           # 이름이 세 줄로 접히고 수는 가운데 「음식점」 줄에 있다
        for i, ln in enumerate(lines):
            if label in ln:
                for nxt in lines[i:i + 3]:
                    m = re.search(r"음식점\s+(" + NUM + r")((?:\s+" + NUM + r")+)\s*$", nxt)
                    if m:
                        return _num(m.group(1)), _num(re.findall(NUM, m.group(2))[-1])
        return None
    pat = (r"(?<!비)" if label == "프랜차이즈" else "") + re.escape(label) + r"\s+(" + NUM + r")((?:\s+" + NUM + r")+)\s*$"
    for ln in lines:
        m = re.search(pat, ln)
        if m and not re.search(re.escape(label) + r"\s+\S*[가-힣]", ln):
            return _num(m.group(1)), _num(re.findall(NUM, m.group(2))[-1])
    return None


def build(pdf: Path) -> dict:
    pages = _pages(pdf)
    idx = _index(pages)
    tables = {}
    for n, (key, unit) in TABLES.items():
        pdf_page, title, printed = idx[n][0]
        lines = pages[pdf_page - 1].splitlines()
        rows = {}
        for label in ROWS:
            got = _row(lines, label)
            if got is None:
                raise SystemExit(f"표 {n} 「{label}」 행을 찾지 못했다")
            rows[label] = {"n": int(got[0]), "mean": got[1]}
        tables[key] = {"table": n, "title": title, "page": printed, "unit": unit, "rows": rows}

    menus = {}
    for n, label in MENU_TABLES.items():
        items: dict[str, dict] = {}
        for pdf_page, _t, _p in idx[n]:
            for ln in pages[pdf_page - 1].splitlines():
                if "단위" in ln or "<표" in ln or "외식업체 경영실태" in ln:
                    continue
                for m in SEG.finditer(ln):
                    name = re.sub(r"\s+", " ", m.group(1)).strip()
                    if name and "전체" not in name and name not in ("메뉴", "사례수", "평균"):
                        items[name] = {"name": name, "n": int(m.group(2).replace(",", "")), "price": int(m.group(3).replace(",", ""))}
        pdf_page, title, printed = idx[n][0]
        total = re.search(r"■ 전체 ■\s+([\d,]+)\s+([\d,]+)", pages[pdf_page - 1])
        menus[label] = {"table": n, "title": title, "page": printed,
                        "total": {"n": int(total.group(1).replace(",", "")), "price": int(total.group(2).replace(",", ""))},
                        "items": sorted(items.values(), key=lambda it: (-it["n"], it["name"]))}

    # 표 105 — 품목별 식재료비 비중(%) · 행마다 9칸
    pdf_page, title, printed = idx[FOOD_MIX_TABLE][0]
    lines = pages[pdf_page - 1].splitlines()
    mix_rows = {}
    for label in ROWS:
        got = _row_all(lines, label)
        if got is None or len(got) != 1 + len(FOOD_MIX_COLUMNS):
            raise SystemExit(f"표 {FOOD_MIX_TABLE} 「{label}」 행을 읽지 못했다: {got}")
        values = got[1:]
        if abs(sum(values) - 100) > 1.5:
            raise SystemExit(f"표 {FOOD_MIX_TABLE} 「{label}」 합 {sum(values):.1f}% — 100 에서 너무 멀다")
        mix_rows[label] = {"n": int(got[0]), "values": values}
    food_mix = {"table": FOOD_MIX_TABLE, "title": title, "page": printed, "unit": "%", "columns": FOOD_MIX_COLUMNS, "rows": mix_rows}

    # 검산 — 행마다 회계 항등식
    worst = 0.0
    for label in ROWS:
        g = lambda k: tables[k]["rows"][label]["mean"]  # noqa: E731
        gap1 = abs(g("sales") - g("opex") - g("profit"))
        gap2 = abs(sum(g(k) for k in COST_PARTS) - g("opex"))
        worst = max(worst, gap1, gap2)
        if gap1 > 0.5 or gap2 > 0.5:
            raise SystemExit(f"「{label}」 검산 실패: 매출−비용−이익 {gap1:.2f} · 항목합−영업비용 {gap2:.2f}")

    return {
        "source": {
            "title": "2025 외식업체 경영실태 조사 통계보고서", "org": "농림축산식품부",
            "url": "https://www.mafra.go.kr/bbs/home/798/595247/download.do",
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "pdf_pages": len(pages),
            "sample_n": tables["open_days"]["rows"]["■ 전체 ■"]["n"], "geography": "전국",
            "ownership": {"비프랜차이즈": "독립운영(개인경영권)", "프랜차이즈": "프랜차이즈 가맹점 + 본사직영(표 30)"},
            "note": ("표마다 한 축(업종 · 운영형태 · 지역 …)으로만 나눈다 — 업종 × 운영형태 교차는 없다. "
                     "매출 · 비용(표 95~104)은 연간 금액이다(매출액 구간 「1억~5억 원 미만」이 71.6%)."),
        },
        "checks": {"accounting_identity_max_gap_manwon": round(worst, 2)},
        "tables": tables,
        "menus": menus,
        "food_mix": food_mix,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = build(Path(sys.argv[1]))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"→ {OUT.relative_to(ROOT)} · 표 {len(out['tables'])}개 · 메뉴표 {len(out['menus'])}개 · 식재료 구성 {len(out['food_mix']['rows'])}행"
          f" · 검산 최대 차 {out['checks']['accounting_identity_max_gap_manwon']}만원")


if __name__ == "__main__":
    main()
