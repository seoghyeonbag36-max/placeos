# -*- coding: utf-8 -*-
"""PlaceOS 2개년 연구계획서(석사과정) .docx 생성기.

원고는 Markdown 이다 — 전체본 career_docs/placeos/10_research_plan_2y.md(표지 · 목차 · 그림 3) 와
축약본 11_research_plan_2y_short.md(3쪽). 원고 첫 줄이 `<!-- layout: compact -->` 면 표지·목차 없이
작은 판형으로 짠다. 문장이나 수치를 고치려면 원고를 고친다.

규칙
- 한글 폰트는 임베딩한다 — scripts/build_business_plan_docx.py 의 subset → odttf 경로를 그대로 쓴다.
- 그림 1 의 값(SKILL)은 원고 표 5와 같은 출처(scripts/kpi_baseline.py)다. 값이 원고에 그대로
  없으면 빌드를 멈춘다 — 그림과 본문이 다른 수를 말하는 일을 막는다.
- 글꼴에 없는 라틴 확장 글자(예: Fišar 의 š)는 그 글자만 Arial 런으로 쓴다. 그 밖의 글자가 없으면 멈춘다.

실행:
    python scripts/build_research_plan_docx.py                       # 전체본 Word
    python scripts/build_research_plan_docx.py --pdf career_docs/placeos/pdf
    python scripts/build_research_plan_docx.py --src career_docs/placeos/11_research_plan_2y_short.md \
        -o "career_docs/placeos/PlaceOS_석사_연구계획서_축약본_3쪽.docx" --pdf career_docs/placeos/pdf --max-pages 3
    옵션: [--fonts 폰트캐시디렉터리]
의존: python-docx · fontTools · matplotlib · (PDF) LibreOffice
"""
from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_business_plan_docx as bp  # noqa: E402  — 서식·임베딩 헬퍼를 같이 쓴다

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "career_docs" / "placeos" / "10_research_plan_2y.md"
OUT = ROOT / "career_docs" / "placeos" / "PlaceOS_석사_연구계획서_2개년.docx"
J, C, L = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT


@dataclass(frozen=True)
class Layout:
    """판형 — 전체본(표지·목차·그림)과 축약본(3쪽)이 여기서만 갈린다."""
    name: str
    lr: float            # 좌우 여백(cm)
    top: float
    bottom: float
    body: float          # 본문 글자 크기(pt)
    line: float          # 본문 줄 간격
    after: float         # 문단 뒤 간격(pt)
    table: float         # 표 글자 크기(4열 이하)
    table_wide: float    # 표 글자 크기(5열 이상)
    cell_v: int          # 표 칸 위·아래 여백(dxa)
    cell_h: int          # 표 칸 좌·우 여백(dxa)
    remark: float
    ref: float
    footer: str

    @property
    def text_w(self) -> float:
        return 21.0 - 2 * self.lr


FULL = Layout("full", 2.2, 2.2, 2.0, 10.2, 1.55, 6, 8.9, 8.4, 55, 90, 8.4, 8.8,
              "PlaceOS 2개년 연구계획서 · 석사과정")
COMPACT = Layout("compact", 1.8, 1.5, 1.4, 9.3, 1.36, 3, 7.9, 7.6, 30, 70, 7.5, 7.6,
                 "PlaceOS 2개년 연구계획서(축약본) · 석사과정")
LAY = FULL                # build() 가 원고 첫 줄을 보고 바꾼다

# ── 그림 색(dataviz 기준 팔레트 — 앞 세 칸은 전 쌍 검증 통과) ─────────────────
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
BLUE_LIGHT, BLUE_PALE = "#86b6ef", "#cde2fb"
INK, INK2, MUTED_C = "#0b0b0b", "#52514e", "#898781"
GRID, BASE_C, WASH = "#e1e0d9", "#c3c2b7", "#f0efec"

# 그림 1 — scripts/kpi_baseline.py (2026-10-22 실행). 원고에 같은 문자열이 있어야 빌드가 된다.
SKILL = [
    # (패널, 행 이름, 추정, 하한, 상한, 판정, 원고에 있어야 할 문자열)
    ("acc", "업종 모델 Top-3\n(GNN · test 18,087자리)", 3.63, 3.00, 4.25, "실력", "+3.63%p"),
    ("acc", "공실 대리변수 방향\n(LSTM · 홀드아웃 240)", 11.3, 5.4, 17.1, "참고", "+11.3%p"),
    ("err", "공실 대리변수 MAE\n(LSTM · 홀드아웃 240)", 17.6, 11.6, 24.5, "참고", "+17.6%"),
]
FLOOR_NOTE = ("빈 층 엄격 정밀도\n(458층 표본)", "라벨 0/458 · 검정불가 — 사전등록 2026-10-19", "0/458")


# ══════════════════════════════════════════════════════════════════════════
#  글자 · 인라인 서식
# ══════════════════════════════════════════════════════════════════════════
_CMAP: set[int] = set()
# 한글 글꼴에 없는 라틴 확장 글자(Fišar 의 š)는 그 글자만 이 글꼴 런으로 쓴다. 결합 문자(s + ̌)로 풀면
# 글꼴에 mark 위치 정보가 없어 다음 글자 위에 얹힌다(2026-10-22 LibreOffice 렌더에서 확인).
FALLBACK_LATIN = "Arial"


def _covered(ch: str) -> bool:
    return not _CMAP or ord(ch) <= 32 or ord(ch) in _CMAP


def glyph_safe(text: str) -> str:
    """런을 나누지 않는 자리(제목 · 캡션 · 목차) — 글꼴에 없는 글자가 있으면 멈춘다(□ 로 깨지는 것보다 낫다)."""
    bad = sorted({ch for ch in text if not _covered(ch)})
    if bad:
        raise SystemExit(f"[plan] 글꼴에 없는 글자: {bad} — 본문·표·참고문헌(rich)에만 쓸 수 있다")
    return text


def run_safe(p, text, **kw):
    """글꼴에 있는 글자는 그대로, 없는 라틴 확장 글자는 FALLBACK_LATIN 런으로 나눠 쓴다."""
    i = 0
    while i < len(text):
        ok = _covered(text[i])
        j = i
        while j < len(text) and _covered(text[j]) == ok:
            j += 1
        seg = text[i:j]
        r = bp.run(p, seg, **kw)
        if not ok:
            if not all(0x80 <= ord(c) <= 0x24F for c in seg):
                raise SystemExit(f"[plan] 글꼴에 없는 글자: {seg!r} — 라틴 확장 밖이라 대체 글꼴로도 못 쓴다")
            rf = r._element.get_or_add_rPr().get_or_add_rFonts()
            rf.set(qn("w:ascii"), FALLBACK_LATIN)
            rf.set(qn("w:hAnsi"), FALLBACK_LATIN)
        i = j


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*?\*)")


def rich(p, text, *, size=10.5, color=bp.INK, bold=False):
    """`**굵게**` · `*기울임*` · `코드` 를 런으로 나눠 쓴다."""
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run_safe(p, part[2:-2], size=size, bold=True, color=bp.NAVY if color == bp.INK else color)
        elif part.startswith("`") and part.endswith("`"):
            run_safe(p, part[1:-1], size=size * 0.95, bold=bold, color=bp.NAVY)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            run_safe(p, part[1:-1], size=size, bold=bold, color=color, italic=True)
        else:
            run_safe(p, part, size=size, bold=bold, color=color)


def outline(p, level: int) -> None:
    """탐색 창에 보이게 개요 수준을 단다(CT_PPr 순서상 divId 앞)."""
    pPr = p._p.get_or_add_pPr()
    pPr.insert_element_before(bp._el("w:outlineLvl", val=level),
                              "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange")


# ══════════════════════════════════════════════════════════════════════════
#  Markdown → 블록
# ══════════════════════════════════════════════════════════════════════════
def parse(md: str) -> list[tuple]:
    blocks: list[tuple] = []
    lines = md.splitlines()
    widths = None
    i = 0
    while i < len(lines):
        s = lines[i].rstrip()
        i += 1
        if not s.strip():
            continue
        if s.startswith("<!--"):
            if "pagebreak" in s:
                blocks.append(("pagebreak",))
            m = re.match(r"<!--\s*widths:\s*([\d.,\s]+)-->", s)
            if m:
                widths = [float(x) for x in m.group(1).split(",")]
            continue
        if s.startswith("|"):
            rows = [s]
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i].rstrip())
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows
                     if not re.fullmatch(r"\|[\s:|-]+\|", r)]
            blocks.append(("table", cells, widths))
            widths = None
            continue
        if s.startswith("# "):
            blocks.append(("title", s[2:].strip()))
        elif s.startswith("## "):
            m = re.match(r"(\d+)\.\s+(.*)", s[3:].strip())
            blocks.append(("h1", m.group(1), m.group(2)) if m else ("h1", "", s[3:].strip()))
        elif s.startswith("### "):
            m = re.match(r"(\d+\.\d+)\s+(.*)", s[4:].strip())
            blocks.append(("h2", m.group(1), m.group(2)) if m else ("h2", "", s[4:].strip()))
        elif s.startswith("> "):
            note = [s[2:].strip()]
            while i < len(lines) and lines[i].startswith("> "):
                note.append(lines[i][2:].strip())
                i += 1
            blocks.append(("note", note))
        elif s.startswith("- "):
            blocks.append(("bullet", s[2:].strip()))
        elif s.startswith("!["):
            m = re.match(r"!\[(.*)\]\(fig:(\w+)\)", s)
            blocks.append(("fig", m.group(2), m.group(1)))
        elif re.match(r"표 \d+\.", s):
            blocks.append(("table_title", s))
        elif s.startswith("※"):
            blocks.append(("remark", s))
        else:
            blocks.append(("p", s))
    return blocks


# ══════════════════════════════════════════════════════════════════════════
#  그림
# ══════════════════════════════════════════════════════════════════════════
def _mpl(font_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    for f in sorted(font_dir.glob("NotoSansKR-*.ttf")):
        fm.fontManager.addfont(str(f))
    plt.rcParams.update({
        "font.family": "Noto Sans KR", "font.size": 7.5, "axes.unicode_minus": False,
        "axes.edgecolor": BASE_C, "axes.labelcolor": INK2, "xtick.color": INK2,
        "ytick.color": INK, "text.color": INK, "axes.linewidth": 0.6,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })
    return plt


def fig_skill(plt, path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.55),
                                   gridspec_kw={"width_ratios": [1.55, 1.0], "wspace": 0.55})
    colors = {"실력": BLUE, "참고": BLUE_LIGHT}
    tags = {"실력": "실력", "참고": "참고 판정 · 확정 전"}

    def draw(ax, rows, xlim, xlabel, title, extra=None):
        labels = []
        n = len(rows) + (1 if extra else 0)
        for k, (_, name, est, lo, hi, verdict, _) in enumerate(rows):
            y = n - 1 - k
            c = colors[verdict]
            ax.plot([lo, hi], [y, y], color=c, lw=2.2, solid_capstyle="round", zorder=3)
            ax.plot([lo, lo], [y - 0.13, y + 0.13], color=c, lw=1.4, zorder=3)
            ax.plot([hi, hi], [y - 0.13, y + 0.13], color=c, lw=1.4, zorder=3)
            ax.scatter([est], [y], s=34, color=c, edgecolor="white", linewidth=1.2, zorder=4)
            ax.text(est, y + 0.3, f"{est:+.2f}".rstrip("0").rstrip(".") if est < 10 else f"{est:+.1f}",
                    ha="center", va="bottom", fontsize=7.2, color=INK, fontweight="bold")
            ax.text(hi + (xlim[1] - xlim[0]) * 0.03, y, f"[{lo:+.2f}, {hi:+.2f}]\n{tags[verdict]}"
                    if est < 10 else f"[{lo:+.1f}, {hi:+.1f}]\n{tags[verdict]}",
                    ha="left", va="center", fontsize=6.4, color=INK2, linespacing=1.25)
            labels.append((y, name))
        if extra:
            ax.text(1.1, 0, extra[1], ha="left", va="center", fontsize=6.6, color=MUTED_C)
            ax.scatter([0], [0], s=30, facecolor="white", edgecolor=MUTED_C, linewidth=1.0, zorder=4)
            labels.append((0, extra[0]))
        ax.axvline(0, color=BASE_C, lw=1.0, zorder=1)
        ax.set_xlim(*xlim)
        ax.set_ylim(-0.7, n - 0.25)
        ax.set_yticks([y for y, _ in labels], [t for _, t in labels], fontsize=6.9, linespacing=1.2)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=6.6, length=2, width=0.5)
        ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.set_xlabel(xlabel, fontsize=6.8, labelpad=3)
        ax.set_title(title, loc="left", fontsize=7.8, fontweight="bold", color=INK, pad=6)

    draw(ax1, [r for r in SKILL if r[0] == "acc"], (-3, 26), "무정보 기준 대비 차이 (%p) — 0 = 기준과 같음",
         "A. 정확도 차이", extra=FLOOR_NOTE)
    draw(ax2, [r for r in SKILL if r[0] == "err"], (-3, 40), "기술점수 (%, 거점 평균 규칙 대비 MAE)",
         "B. 오차 기술점수")
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], color=BLUE, lw=2.2, marker="o", markersize=4.5, label="실력(판정 확정)"),
               Line2D([0], [0], color=BLUE_LIGHT, lw=2.2, marker="o", markersize=4.5,
                      label="참고 판정(2026년 3분기 이후 표본으로 확정 전)"),
               Line2D([0], [0], color=MUTED_C, lw=0, marker="o", markerfacecolor="white", markersize=4.5,
                      label="검정불가(라벨 없음)")]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=6.6,
               bbox_to_anchor=(0.5, 1.02), handlelength=1.8, columnspacing=1.6)
    fig.subplots_adjust(left=0.19, right=0.97, top=0.80, bottom=0.2)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def fig_framework(plt, path: Path) -> None:
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = plt.subplots(figsize=(6.6, 3.85))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, head, sub, *, fill="white", edge=BASE_C, lw=0.8, hc=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                    facecolor=fill, edgecolor=edge, linewidth=lw, zorder=2))
        ax.text(x + 1.4, y + h - 1.6, head, ha="left", va="top", fontsize=7.3, fontweight="bold",
                color=hc, zorder=3)
        ax.text(x + 1.4, y + h - 4.3, sub, ha="left", va="top", fontsize=6.2, color=INK2, zorder=3,
                linespacing=1.35)
        return (x, y, w, h)

    def arrow(p, q, color=MUTED_C, rad=0.0, lw=0.8):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color=color,
                                     lw=lw, connectionstyle=f"arc3,rad={rad}", zorder=1,
                                     shrinkA=2, shrinkB=2))

    for x, t in ((2, "산출물 — PlaceOS(PPPP)"), (37, "평가 회차 — FEDS"), (71, "최종 산출")):
        ax.text(x, 58.2, t, fontsize=7.8, fontweight="bold", color=INK, va="top")
        ax.plot([x, x + 27], [55.6, 55.6], color=INK, lw=0.6)

    tracks = [("Platform · 어떤 상권인가", "GNN 업종 모델 · LSTM 공실 대리변수"),
              ("Page · 어느 건물 몇 층이 비었나", "빈 층 판정 · 층별 매물 · 거리뷰"),
              ("Posting · 월 얼마, 몇 달이면 본전", "3-Tier 비용-효용 시나리오"),
              ("Program · 작게 먼저 확인", "팝업 · 가오픈 · MVP 검증 program")]
    evals = [("E1 계산 재현성 · 데이터 품질", "인공 · 형성\n재현 패키지(DOI)", False),
             ("E2 모델 실력(전향 평가)", "인공 · 총괄\n동결 모델 · 새 분기 채점", False),
             ("E3 빈 층 사전등록 현장 검증", "자연 · 총괄 · 핵심\n458층 블라인드 현장 라벨", True),
             ("E4 창업자 파일럿", "자연 · 총괄 · 탐색\nW4 · NPS · 지불 의향", False)]
    h, gap, top = 9.2, 3.0, 53.2
    tb, eb = [], []
    for k, (a, b) in enumerate(tracks):
        tb.append(box(2, top - h - k * (h + gap), 28, h, a, b))
    for k, (a, b, core) in enumerate(evals):
        eb.append(box(37, top - h - k * (h + gap), 28, h, a, b,
                      fill=BLUE_PALE if core else "white", edge=BLUE if core else BASE_C,
                      lw=1.2 if core else 0.8))
    thesis = box(71, 30.0, 27, 23.2, "석사학위 논문(과정 수료 후)",
                 "5장  E1 계산 재현성\n6장  E2 모델 실력\n7장  E3 빈 층 현장 검증\n8장  E4 창업자 파일럿\n"
                 "9장  논의 · 설계 원칙", edge=INK2)
    biz = box(71, 1.5, 27, 21.0, "산학협력 기술사업화(창업)",
              "배경 IP 정리 · 귀속 합의\n특허 · 상표 출원\n기술이전 또는 기술지주 자회사\n법인 설립 · 사업 개시",
              fill="#e8f6f0", edge=AQUA)

    def right(b, f=0.5):
        return (b[0] + b[2], b[1] + b[3] * f)

    def left(b, f=0.5):
        return (b[0], b[1] + b[3] * f)

    arrow(right(tb[0]), left(eb[1]), rad=-0.12)
    arrow(right(tb[1], 0.62), left(eb[0], 0.4), rad=0.12)
    arrow(right(tb[1], 0.38), left(eb[2], 0.6), rad=-0.12, color=BLUE, lw=1.1)
    arrow(right(tb[2]), left(eb[3], 0.62), rad=-0.1)
    arrow(right(tb[3]), left(eb[3], 0.38), rad=0.0)
    for k, b in enumerate(eb):
        arrow(right(b), left(thesis, 0.82 - k * 0.16), rad=0.0)
    arrow((84.5, 30.0), (84.5, 22.5), color=AQUA, lw=1.1)
    ax.text(85.6, 26.2, "실력으로 판정된\n기능만 사업화", fontsize=6.2, color=INK2, va="center",
            linespacing=1.2)
    ax.text(50, -0.4, "판정 규칙 — 무정보 기준과의 차이 · 95% 구간 · 결과 전 사전등록 · 선택 ≠ 보고",
            ha="center", va="bottom", fontsize=6.4, color=INK2)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.03)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _m(y: int, mo: int, end=False) -> float:
    """2026년 11월 1일 = 0 인 월 좌표. end=True 면 그달 말."""
    return (y - 2026) * 12 + (mo - 11) + (1.0 if end else 0.0)


def fig_gantt(plt, path: Path) -> None:
    rows = [
        ("학위 과정", ORANGE, [
            ("입학 준비 · 전형", (2026, 11), (2027, 2)),
            ("교과 이수(수료 학점)", (2027, 3), (2028, 6)),
            ("학위논문 계획서 · 발표", (2028, 1), (2028, 6)),
            ("논문 집필 · 심사 · 인준", (2028, 7), (2029, 2)),
        ]),
        ("연구", BLUE, [
            ("E3 1차 라벨 · 채점", (2026, 11), (2027, 8)),
            ("E2 전향 채점(분기마다)", (2026, 11), (2028, 9)),
            ("E1 재현 패키지(DOI)", (2027, 3), (2027, 6)),
            ("E4 창업자 파일럿", (2027, 9), (2028, 6)),
            ("E3 2차 표본(v2 규칙)", (2028, 1), (2028, 6)),
            ("투고 · 리뷰 대응", (2027, 7), (2028, 8)),
        ]),
        ("기술사업화", AQUA, [
            ("배경 IP · 귀속 합의", (2026, 12), (2027, 6)),
            ("창업동아리 · 교내 프로그램", (2027, 3), (2027, 12)),
            ("특허 선행조사 · 특허·상표 출원", (2027, 9), (2028, 6)),
            ("기술이전 협상 · 가치평가", (2028, 3), (2028, 9)),
            ("법인 설립 · 사업 개시", (2028, 9), (2029, 2)),
        ]),
    ]
    # (행, 시점, 이름, 글자 정렬) — 윗줄 막대와 겹치는 자리는 왼쪽으로 붙인다
    marks = [("E3 1차 라벨 · 채점", (2027, 8), "1차 판정", "center"),
             ("투고 · 리뷰 대응", (2027, 12), "G1~G5 채점", "right"),
             ("교과 이수(수료 학점)", (2028, 6), "수료", "center"),
             ("논문 집필 · 심사 · 인준", (2029, 2), "학위", "right"),
             ("법인 설립 · 사업 개시", (2028, 12), "법인", "center")]
    n = sum(len(r[2]) for r in rows) + len(rows)
    fig, ax = plt.subplots(figsize=(6.6, 4.7))
    xmax = _m(2029, 2, end=True)
    terms = [("준비기", (2026, 11), (2027, 2)), ("1학기", (2027, 3), (2027, 6)), ("2학기", (2027, 9), (2027, 12)),
             ("3학기", (2028, 3), (2028, 6)), ("4학기", (2028, 9), (2028, 12)), ("졸업", (2029, 1), (2029, 2))]
    for k, (t, a, b) in enumerate(terms):
        x0, x1 = _m(*a), _m(*b, end=True)
        if t not in ("준비기", "졸업"):
            ax.axvspan(x0, x1, color=WASH, zorder=0, lw=0)
        ax.text((x0 + x1) / 2, n + 0.15, t, ha="center", va="bottom", fontsize=6.9,
                color=INK if "학기" in t else INK2, fontweight="bold" if "학기" in t else "normal")
    y = n - 0.5
    ypos = {}
    yticks, ylabels = [], []
    for lane, color, items in rows:
        ax.text(-0.4, y, lane, ha="right", va="center", fontsize=7.4, fontweight="bold", color=INK)
        y -= 1
        for label, a, b in items:
            x0, x1 = _m(*a), _m(*b, end=True)
            ax.barh(y, x1 - x0, left=x0, height=0.56, color=color, edgecolor="white", linewidth=1.0,
                    zorder=3)
            ypos[label] = y
            yticks.append(y)
            ylabels.append(label)
            y -= 1
    for label, (yy, mo), text, ha in marks:
        x = _m(yy, mo, end=True)
        ax.scatter([x], [ypos[label]], marker="D", s=26, color=INK, edgecolor="white", linewidth=0.8,
                   zorder=5)
        ax.text(x - (0.25 if ha == "right" else 0), ypos[label] + 0.42, text, ha=ha, va="bottom",
                fontsize=6.3, color=INK, fontweight="bold", zorder=5)
    ticks = [(2026, 11), (2027, 3), (2027, 9), (2028, 3), (2028, 9), (2029, 2)]
    ax.set_xticks([_m(*t) for t in ticks], [f"{t[0]}.{t[1]:02d}" for t in ticks], fontsize=6.7)
    ax.set_yticks(yticks, ylabels, fontsize=6.7)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.tick_params(axis="x", length=2, width=0.5)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.3, n + 0.9)
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=1)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ORANGE, label="학위 과정"), Patch(color=BLUE, label="연구(E1~E4 · 투고)"),
                       Patch(color=AQUA, label="기술사업화")],
              loc="lower right", frameon=False, fontsize=6.6, ncol=3, bbox_to_anchor=(1.0, -0.13))
    fig.subplots_adjust(left=0.30, right=0.985, top=0.95, bottom=0.12)
    fig.savefig(path, dpi=220)
    plt.close(fig)


FIGS = {"skill": fig_skill, "framework": fig_framework, "gantt": fig_gantt}
BREAK_BEFORE = {"1", "5", "8", "12"}   # 이 번호의 장은 새 쪽에서 시작한다(요약·방법·사업화·참고문헌)
KEEP_CM = 9.0                          # 추정 높이가 이보다 낮은 표는 쪽을 넘기지 않게 묶는다


# ══════════════════════════════════════════════════════════════════════════
#  렌더링
# ══════════════════════════════════════════════════════════════════════════
def _est_height_cm(rows, widths, size) -> float:
    """표 높이 어림 — 한 글자 폭을 글자 크기로 보고(라틴은 더 좁아 넉넉한 쪽으로 틀린다) 줄 수를 센다."""
    char_w = size * 0.0353 * 0.92
    line_h = size * 0.0353 * 1.28 * 1.15
    total = 0.0
    for row in rows:
        lines = 1
        for val, w in zip(row, widths):
            cap = max(1.0, (w - 0.32) / char_w)
            lines = max(lines, math.ceil(len(re.sub(r"[*`]", "", val)) / cap))
        total += lines * line_h + 0.2
    return total


def table(doc, rows, widths):
    n = len(rows[0])
    if widths is None or len(widths) != n:
        widths = [1.0] * n
    widths = [w * LAY.text_w / sum(widths) for w in widths]   # 원고의 비율을 판형 너비에 맞춘다
    size = LAY.table_wide if n >= 5 else LAY.table
    num = re.compile(r"^[\d,.\s%~+−\-—]+$")
    aligns = []
    for j in range(n):
        body_cells = [r[j] for r in rows[1:]]
        aligns.append(C if body_cells and all(num.match(c) for c in body_cells) else L)
    short = _est_height_cm(rows, widths, size) <= KEEP_CM
    t = doc.add_table(rows=len(rows), cols=n)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(bp._el(f"w:{edge}", val="single", sz=4, space=0, color=bp.RULE))
    tblPr.insert_element_before(borders, "w:shd", "w:tblLayout", "w:tblCellMar",
                                "w:tblLook", "w:tblCaption", "w:tblDescription")
    grid = t._tbl.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 567)))
    for ri, row in enumerate(rows):
        head = ri == 0
        trPr = t.rows[ri]._tr.get_or_add_trPr()
        if head:
            trPr.append(bp._el("w:tblHeader", val="true"))
        trPr.append(bp._el("w:cantSplit", val="true"))
        keep = short and ri < len(rows) - 1   # 짧은 표는 한 쪽에 둔다 — 긴 표까지 묶으면 앞 쪽이 빈다
        for ci in range(n):
            val = row[ci] if ci < len(row) else ""
            cell = t.cell(ri, ci)
            cell.width = Cm(widths[ci])
            bp.cell_margins(cell, top=LAY.cell_v, bottom=LAY.cell_v, left=LAY.cell_h, right=LAY.cell_h)
            if head:
                bp.cell_shade(cell, bp.HEADFILL)
            elif ri % 2 == 0:
                bp.cell_shade(cell, bp.ZEBRA)
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
            p = bp.para(cell, line=1.28 if LAY is FULL else 1.18, align=(C if head else aligns[ci]))
            if keep:
                bp.keep_with_next(p)
            if head:
                rich(p, val, size=size, color=bp.NAVY, bold=True)
            else:
                rich(p, val, size=size, color=bp.INK, bold=(ci == 0))
    gap = doc.add_paragraph()
    gap.paragraph_format.space_after = Pt(2 if LAY is FULL else 0)
    if LAY is COMPACT:
        gap.paragraph_format.line_spacing = Pt(4)
    return t


def cover(doc, blocks):
    """표지 — 원고의 첫 '## ' 앞 블록(제목 · 국문 부제 · 영문 부제 · 정보 표 · 최종 목표)."""
    title, sub_ko, sub_en = blocks[0][1], blocks[1][1], blocks[2][1]
    p = bp.para(doc, before=70, after=0, line=1.2)
    bp.run(p, "석사과정 연구계획서 · 2027–2029", size=11, bold=True, color=bp.ACCENT)
    p = bp.para(doc, before=6, after=0, line=1.1)
    bp.run(p, glyph_safe(title), size=30, bold=True, color=bp.NAVY, spacing=-10)
    p = bp.para(doc, before=18, after=0, line=1.45)
    bp.para_border(p, ("top",), color=bp.ACCENT, sz=18, space=14)
    bp.run(p, glyph_safe(sub_ko), size=14, bold=True, color=bp.INK)
    p = bp.para(doc, before=8, after=22, line=1.4)
    bp.run(p, glyph_safe(sub_en), size=9.5, color=bp.MUTED, italic=True)
    for b in blocks[3:]:
        if b[0] == "table":
            table(doc, b[1], b[2])
        elif b[0] == "note":
            note(doc, b[1], fill="F1F5F9", border=bp.NAVY)


def note(doc, lines, *, fill=bp.NOTEFILL, border=bp.ACCENT):
    """`> **제목**` 줄은 굵게, 나머지는 본문으로 — 박스는 위·아래 테두리만(4면은 스키마 위반)."""
    out = []
    for ln in lines:
        m = re.fullmatch(r"\*\*(.+)\*\*", ln)
        out.append((glyph_safe(m.group(1)), True) if m else (glyph_safe(ln.replace("**", "")), False))
    bp.note_box(doc, out, fill=fill, border=border)


def toc(doc, blocks):
    """정적 목차 — 장마다 한 줄, 절은 그 아래 한 문단으로 잇는다(쪽 번호는 넣지 않는다)."""
    p = bp.para(doc, before=4, after=10, line=1.15)
    bp.run(p, "목차", size=17, bold=True, color=bp.NAVY)
    bp.para_border(p, ("bottom",), color=bp.NAVY, sz=10, space=6)
    subs: list[str] = []

    def flush():
        if subs:
            p = bp.para(doc, before=0, after=3, line=1.35, indent=0.75)
            bp.run(p, glyph_safe("  ·  ".join(subs)), size=8.6, color=bp.INK)
            subs.clear()

    for b in blocks:
        if b[0] == "h1":
            flush()
            p = bp.para(doc, before=7, after=1, line=1.2)
            bp.run(p, f"{b[1]}.  " if b[1] else "", size=10.5, bold=True, color=bp.ACCENT)
            bp.run(p, glyph_safe(b[2]), size=10.5, bold=True, color=bp.NAVY)
        elif b[0] == "h2":
            subs.append(f"{b[1]} {b[2]}")
    flush()


def page_break(doc):
    p = bp.para(doc, before=0, after=0)
    bp.run(p, "").add_break(WD_BREAK.PAGE)


def header_block(doc, blocks):
    """축약본 머리 — 표지·목차 대신 첫 쪽 위에 제목 · 부제 · 정보 표를 둔다."""
    title, sub_ko = blocks[0][1], blocks[1][1]
    p = bp.para(doc, before=0, after=0, line=1.15)
    bp.run(p, "석사과정 연구계획서(축약본) · 2027–2029", size=8.5, bold=True, color=bp.ACCENT)
    p = bp.para(doc, before=1, after=0, line=1.1)
    bp.run(p, glyph_safe(title), size=16, bold=True, color=bp.NAVY)
    p = bp.para(doc, before=5, after=5, line=1.3)
    bp.para_border(p, ("top",), color=bp.ACCENT, sz=12, space=6)
    bp.run(p, glyph_safe(sub_ko), size=10.2, bold=True, color=bp.INK)
    for b in blocks[2:]:
        if b[0] == "table":
            table(doc, b[1], b[2])


def h1_compact(doc, num, title):
    p = bp.para(doc, before=6, after=2, line=1.1)
    if num:
        bp.run(p, f"{num}  ", size=11, bold=True, color=bp.ACCENT)
    bp.run(p, glyph_safe(title), size=11, bold=True, color=bp.NAVY)
    bp.para_border(p, ("bottom",), color=bp.RULE, sz=6, space=2)
    bp.keep_with_next(p)
    return p


def render(doc, blocks, fig_paths):
    head = [b for b in blocks if b[0] != "pagebreak"]
    k = next(i for i, b in enumerate(head) if b[0] == "h1")
    if LAY is COMPACT:
        header_block(doc, head[:k])
    else:
        cover(doc, head[:k])
        page_break(doc)
        toc(doc, head[k:])
        page_break(doc)

    size, in_refs = LAY.body, False
    for b in head[k:]:
        kind = b[0]
        if kind == "h1":
            if LAY is FULL and b[1] in BREAK_BEFORE:
                page_break(doc)
            in_refs = b[2].startswith("참고문헌")
            if LAY is COMPACT:
                p = h1_compact(doc, b[1], b[2])
            else:
                p = bp.h1(doc, b[1], glyph_safe(b[2])) if b[1] else _h1_plain(doc, b[2])
            outline(p, 0)
        elif kind == "h2":
            p = bp.h2(doc, b[1], glyph_safe(b[2]))
            outline(p, 1)
        elif kind == "p":
            p = bp.para(doc, after=LAY.after, line=LAY.line, align=J)
            rich(p, b[1], size=size)
        elif kind == "bullet" and in_refs:
            # 참고문헌 — 양쪽 정렬하면 DOI·영문 제목에서 낱말 사이가 벌어진다. 왼쪽 정렬 + 내어쓰기.
            p = bp.para(doc, after=3 if LAY is FULL else 1, line=1.3 if LAY is FULL else 1.15,
                        indent=0.75, align=L)
            p.paragraph_format.first_line_indent = Cm(-0.75)
            rich(p, b[1], size=LAY.ref)
        elif kind == "bullet":
            p = bp.para(doc, after=4 if LAY is FULL else 2, line=LAY.line - 0.05, indent=0.55, align=J)
            p.paragraph_format.first_line_indent = Cm(-0.4)
            bp.run(p, "·  ", size=size, bold=True, color=bp.ACCENT)
            rich(p, b[1], size=size)
        elif kind == "note":
            note(doc, b[1])
        elif kind == "table_title":
            if LAY is COMPACT:
                p = bp.para(doc, before=3, after=2, line=1.1)
                bp.run(p, glyph_safe(b[1].replace("`", "")), size=8.6, bold=True, color=bp.NAVY)
                bp.keep_with_next(p)
            else:
                bp.table_title(doc, glyph_safe(b[1].replace("`", "")))
        elif kind == "table":
            table(doc, b[1], b[2])
        elif kind == "remark":
            p = bp.para(doc, before=0, after=8 if LAY is FULL else 0, line=1.4 if LAY is FULL else 1.2)
            rich(p, b[1], size=LAY.remark, color=bp.MUTED)
        elif kind == "fig":
            p = bp.para(doc, before=6, after=2, line=1.0, align=C)
            bp.keep_with_next(p)
            p.add_run().add_picture(str(fig_paths[b[1]]), width=Cm(LAY.text_w))
            bp.caption(doc, glyph_safe(b[2]))


def _h1_plain(doc, title):
    p = bp.para(doc, before=12, after=2, line=1.15)
    bp.run(p, glyph_safe(title), size=17, bold=True, color=bp.NAVY)
    bp.para_border(p, ("bottom",), color=bp.NAVY, sz=10, space=6)
    bp.keep_with_next(p)
    return p


def build(src: Path, out: Path, fonts: dict[str, Path], work: Path) -> None:
    global LAY
    from fontTools.ttLib import TTFont
    _CMAP.update(TTFont(str(fonts["regular"])).getBestCmap())
    md = src.read_text(encoding="utf-8")
    LAY = COMPACT if md.lstrip().startswith("<!-- layout: compact -->") else FULL
    used = set(re.findall(r"\(fig:(\w+)\)", md))
    if "skill" in used:
        for *_, needle in SKILL:
            if needle not in md:
                raise SystemExit(f"[plan] 그림 1 의 값 {needle} 이 원고에 없다 — SKILL 과 원고를 맞출 것")
        if FLOOR_NOTE[2] not in md:
            raise SystemExit("[plan] 빈 층 판정 상태가 원고와 다르다")
    fig_paths = {}
    if used:
        plt = _mpl(fonts["regular"].parent)
        for name in sorted(used):
            fig_paths[name] = work / f"fig_{name}.png"
            FIGS[name](plt, fig_paths[name])
    blocks = parse(md)

    doc = Document()
    bp.setup(doc)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(LAY.lr)
    sec.top_margin, sec.bottom_margin = Cm(LAY.top), Cm(LAY.bottom)
    sec.footer_distance = Cm(1.2 if LAY is FULL else 0.7)
    bp.add_footer(sec, LAY.footer)
    cp = doc.core_properties
    cp.title = "PlaceOS 2개년 연구계획서" + ("(축약본)" if LAY is COMPACT else "")
    cp.author, cp.subject = "PlaceOS", "석사과정 연구계획서"
    render(doc, blocks, fig_paths)
    doc.save(out)


def to_pdf(docx: Path, outdir: Path) -> Path:
    """LibreOffice 로 PDF 를 만든다 — 문서에 임베딩한 한글 글꼴을 그대로 쓴다(시스템 글꼴 설치 불필요)."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise SystemExit("[plan] LibreOffice(soffice)가 없다 — Word 의 'PDF로 저장'으로 만들 것")
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lo_profile_") as prof:   # 사용자 프로필 잠금을 피한다
        r = subprocess.run([exe, f"-env:UserInstallation={Path(prof).as_uri()}", "--headless",
                            "--convert-to", "pdf", "--outdir", str(outdir), str(docx)],
                           env=dict(os.environ, SAL_USE_VCLPLUGIN="svp"),
                           capture_output=True, text=True, timeout=300)
    pdf = outdir / f"{docx.stem}.pdf"
    if r.returncode != 0 or not pdf.exists():
        raise SystemExit(f"[plan] PDF 변환 실패: {(r.stderr or r.stdout)[-400:]}")
    return pdf


def pdf_pages(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf.read_bytes()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC), help="원고 Markdown(기본: 전체본)")
    ap.add_argument("-o", "--out", default=str(OUT))
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리(기본: 임시 디렉터리)")
    ap.add_argument("--pdf", default=None, help="PDF 를 만들 디렉터리(LibreOffice 필요)")
    ap.add_argument("--max-pages", type=int, default=None, help="PDF 쪽수 상한 — 넘으면 실패")
    args = ap.parse_args()
    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        fonts = bp.fetch_fonts(cache)
        print("1) 문서 생성")
        build(src, out, fonts, work)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("2) 한글 폰트 임베딩")
        bp.embed_fonts(out, fonts, work)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("3) 검증")
        bp.verify_embedding(out)
    if args.pdf:
        pdf = to_pdf(out, Path(args.pdf).resolve())
        pages = pdf_pages(pdf)
        print(f"4) PDF → {pdf.name} ({pages}쪽)")
        if args.max_pages and pages > args.max_pages:
            raise SystemExit(f"[plan] {pages}쪽 — 목표 {args.max_pages}쪽을 넘는다. 원고를 줄일 것")
    print(f"\n완료: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
