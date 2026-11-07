# -*- coding: utf-8 -*-
"""Program 리뉴얼 보고서 그림 3장 — `reports/program_renewal_probe_*.json` 만 읽는다(숫자를 여기 적지 않는다).

⚠ matplotlib 이 필요하다(requirements 밖). 서빙·CI 와 무관한 문서용이라 의존성에 넣지 않았다.
   설치 예: pip install --target <임시폴더> matplotlib  →  PYTHONPATH=<임시폴더> python scripts/program_renewal_charts.py …

색은 dataviz 기본 팔레트에서 골랐고 검증기를 통과한 조합만 쓴다(2026-11-07):
  범주 2색 #2a78d6·#eb6834 — 인접 CVD ΔE 24.7 · 정상시 ΔE 33.6 · 대비 3:1 이상
  서열 2단 #86b6ef→#2a78d6 — 단조 · 밝은 끝 2.06:1
  「자료 없음」·「끝남」은 범주색이 아니라 회색(#c3c2b7)이다.

실행:
    python scripts/program_renewal_charts.py reports/program_renewal_probe_2026-11-07.json \
        --out docs/renewal-program-2026-11-07 --fonts <폰트 캐시>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

BLUE, ORANGE, BLUE_LIGHT, GRAY = "#2a78d6", "#eb6834", "#86b6ef", "#c3c2b7"
INK, INK2, MUTED, GRID, BASE, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
DPI = 200
PX = 1 / 96          # CSS px → inch (마크 규격은 CSS px 로 적혀 있다)
BAR_IN = 18 * PX     # 막대 두께 ≤24px
GAP_IN = 2 * PX      # 맞닿는 마크 사이 표면색 틈
ROUND_IN = 4 * PX    # 데이터 끝 둥글기(기준선 쪽은 각지게)


def setup_fonts(cache: Path) -> None:
    import matplotlib
    from matplotlib import font_manager

    import build_business_plan_docx as bp

    fonts = bp.fetch_fonts(cache)
    for p in fonts.values():
        font_manager.fontManager.addfont(str(p))
    name = font_manager.FontProperties(fname=str(fonts["regular"])).get_name()
    matplotlib.rcParams.update({"font.family": name, "font.size": 9, "axes.unicode_minus": False})


def _axes(fig, left_in, bottom_in, width_in, height_in):
    W, H = fig.get_size_inches()
    ax = fig.add_axes([left_in / W, bottom_in / H, width_in / W, height_in / H])
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="both", length=0, colors=MUTED, labelsize=8.5)
    return ax


def _units(ax):
    """1 inch 가 x·y 데이터 단위로 얼마인가 — 축 크기·범위를 고정한 뒤에 부른다."""
    fig = ax.figure
    bb = ax.get_position()
    W, H = fig.get_size_inches()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return (x1 - x0) / (bb.width * W), abs(y1 - y0) / (bb.height * H)


def hbar(ax, y, left, width, color, *, round_end=True):
    """가로 막대 한 칸 — 기준선 쪽은 각지고 데이터 끝만 4px 둥글다."""
    from matplotlib.patches import FancyBboxPatch, Rectangle

    ux, uy = _units(ax)
    h = BAR_IN * uy
    r = ROUND_IN * ux
    if width <= 0:
        return
    if not round_end or width <= 2 * r:
        ax.add_patch(Rectangle((left, y - h / 2), width, h, facecolor=color, edgecolor="none", lw=0))
        return
    ax.add_patch(Rectangle((left, y - h / 2), width - r, h, facecolor=color, edgecolor="none", lw=0))
    ax.add_patch(FancyBboxPatch((left + width - 2 * r, y - h / 2), 2 * r, h,
                                boxstyle=f"round,pad=0,rounding_size={r}", mutation_aspect=uy / ux,
                                facecolor=color, edgecolor="none", lw=0))


def _xgrid(ax, ticks):
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:,}" for t in ticks])
    for t in ticks:
        ax.axvline(t, color=GRID if t else BASE, lw=0.6, zorder=0)


def _legend(fig, items, x_in, y_in):
    """범례 — 글자는 잉크색, 색은 옆의 네모가 맡는다."""
    from matplotlib.patches import Rectangle

    W, H = fig.get_size_inches()
    x = x_in
    for color, label in items:
        fig.add_artist(Rectangle((x / W, (y_in - 0.035) / H), 0.11 / W, 0.11 / H,
                                 transform=fig.transFigure, facecolor=color, edgecolor="none"))
        t = fig.text((x + 0.16) / W, (y_in + 0.02) / H, label, color=INK2, fontsize=8.5, va="center")
        fig.canvas.draw()
        x += 0.16 + t.get_window_extent().width / DPI + 0.28


def fig_events_by_region(probe: dict, out: Path) -> Path:
    import matplotlib.pyplot as plt

    ev = probe["events"]
    order = [("서울특별시", "서울"), ("경기도", "경기"), ("전남광주통합특별시", "광주"), ("전북특별자치도", "전주")]
    total = probe["served_hubs_by_sido"]
    rows = []
    for key, short in order:
        rows.append((f"{short} ({total.get(key, 0)})", ev["hubs_with_events"].get(key, 0),
                     ev["hubs_loaded_zero"].get(key, 0), ev["hubs_not_in_gold"].get(key, 0)))
    fig = plt.figure(figsize=(6.4, 2.25), dpi=DPI, facecolor=SURFACE)
    ax = _axes(fig, 0.95, 0.32, 5.25, 1.45)
    xmax = max(sum(r[1:]) for r in rows)
    ax.set_xlim(0, xmax * 1.04)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    _xgrid(ax, [0, 20, 40, 60, 80])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], color=INK, fontsize=9)
    ux, _ = _units(ax)
    gap = GAP_IN * ux
    for i, (_, has, zero, none) in enumerate(rows):
        segs = [(has, BLUE, "#ffffff"), (zero, ORANGE, "#ffffff"), (none, GRAY, INK)]
        segs = [s for s in segs if s[0] > 0]
        left = 0.0
        for j, (v, color, ink) in enumerate(segs):
            last = j == len(segs) - 1
            w = v - (0 if last else gap)
            hbar(ax, i, left, w, color, round_end=last)
            label = f"{v}"
            if v * (1 / ux) > 0.28:          # 안에 들어갈 때만 안에 쓴다
                ax.text(left + 0.06 / (1 / ux), i, label, color=ink, fontsize=8.5, va="center", ha="left")
            left += v
    _legend(fig, [(BLUE, "행사 1건 이상"), (ORANGE, "적재됐고 0건"), (GRAY, "행사 자료 없음")], 0.95, 2.02)
    fig.text(6.2 / 6.4, 0.06 / 2.25, "단위: 서빙 거점 수", color=MUTED, fontsize=7.5, ha="right")
    path = out / "fig1_events_by_region.png"
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    return path


def fig_regional_fill(probe: dict, out: Path) -> Path:
    import matplotlib.pyplot as plt

    non_seoul = probe["served_hubs"] - probe["served_hubs_by_sido"].get("서울특별시", 0)
    prox = {p["probe"]: p["hub_proximity"] for p in probe["live_probes"] if "hub_proximity" in p}
    culture = next(v for k, v in prox.items() if k.startswith("문화포털"))
    tour = next(v for k, v in prox.items() if k.startswith("TourAPI"))

    def outside(d: dict) -> int:
        return sum(n for k, n in d.items() if k != "서울특별시")

    rows = [("문화포털", outside(culture["within_1000m"]), outside(culture["within_3000m"])),
            ("TourAPI", outside(tour["within_1000m"]), outside(tour["within_3000m"]))]
    fig = plt.figure(figsize=(6.4, 2.1), dpi=DPI, facecolor=SURFACE)
    ax = _axes(fig, 0.95, 0.32, 5.25, 1.30)
    ax.set_xlim(0, non_seoul * 1.06)
    ax.set_ylim(1.62, -0.62)
    _xgrid(ax, [0, 20, 40, 60])
    ax.axvline(non_seoul, color=INK2, lw=0.8, zorder=1)
    ax.text(non_seoul, -0.58, f"서울 밖 {non_seoul}거점", color=INK2, fontsize=8, ha="right", va="top")
    ax.set_yticks([0, 1])
    ax.set_yticklabels([r[0] for r in rows], color=INK, fontsize=9)
    ux, uy = _units(ax)
    off = (BAR_IN + GAP_IN) * uy / 2
    for i, (_, km1, km3) in enumerate(rows):
        for dy, v, color in ((-off, km1, BLUE), (off, km3, BLUE_LIGHT)):
            hbar(ax, i + dy, 0, v, color)
            ax.text(v + 0.05 * ux, i + dy, f"{v}", color=INK, fontsize=8.5, va="center", ha="left")
    _legend(fig, [(BLUE, "거점 중심 1km 안"), (BLUE_LIGHT, "3km 안")], 0.95, 1.86)
    fig.text(6.2 / 6.4, 0.06 / 2.1, "단위: 행사가 1건 이상 잡히는 거점 수", color=MUTED, fontsize=7.5, ha="right")
    path = out / "fig2_regional_fill.png"
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    return path


def fig_event_freshness(probe: dict, out: Path) -> Path:
    """한 전체(749건)를 두 부분으로 — 굵은 분할 막대(28px 이하), 몫은 막대 안에, 범례는 이름만."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    ev = probe["events"]
    total, ended = ev["events_total_served"], ev["events_ended_by_as_of"]
    alive = total - ended
    fig = plt.figure(figsize=(6.4, 1.15), dpi=DPI, facecolor=SURFACE)
    W, H = fig.get_size_inches()
    ax = fig.add_axes([0.15 / W, 0.40 / H, 6.1 / W, 0.30 / H])
    ax.set_xlim(0, total)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ux = total / 6.1
    uy = 1 / 0.30
    gap = GAP_IN * ux
    r = ROUND_IN * ux
    left = 0.0
    for v, color, ink, name in ((alive, BLUE, "#ffffff", "아직 안 끝남"), (ended, GRAY, INK, "이미 끝남")):
        w = v - gap if left == 0 else v
        ax.add_patch(FancyBboxPatch((left, 0), w, 1, boxstyle=f"round,pad=0,rounding_size={r}",
                                    mutation_aspect=uy / ux, facecolor=color, edgecolor="none"))
        ax.text(left + 0.08 * ux, 0.5, f"{v}건 · {v / total:.1%}", color=ink, fontsize=9, va="center", ha="left")
        left += v
    _legend(fig, [(BLUE, "아직 안 끝남"), (GRAY, "이미 끝남")], 0.15, 0.95)
    fig.text(6.25 / W, 0.12 / H, f"서빙 중 {total}건(거점 간 중복 포함) · 기준일 {probe['as_of']}",
             color=MUTED, fontsize=7.5, ha="right")
    path = out / "fig3_event_freshness.png"
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("probe", help="reports/program_renewal_probe_*.json")
    ap.add_argument("--out", default=str(ROOT / "docs" / "renewal-program-2026-11-07"))
    ap.add_argument("--fonts", required=True, help="Noto Sans KR 캐시 디렉터리")
    args = ap.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    setup_fonts(Path(args.fonts))
    probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (fig_events_by_region, fig_regional_fill, fig_event_freshness):
        print(f(probe, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
