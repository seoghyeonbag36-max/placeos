# -*- coding: utf-8 -*-
"""Program 리뉴얼 보고서 .docx 생성기 — 원본은 docs/renewal-program-2026-11-07.md 하나다.

같은 내용을 두 벌로 쓰면 반드시 어긋난다. 그래서 마크다운을 읽어 Word 로 옮기기만 한다.
읽는 문법(이 보고서가 쓰는 것만): `#` 제목 · `##` 장 · `###` 절 · 문단 · `- ` 목록 · `> ` 상자 ·
파이프 표 · `![캡션](경로)` 그림 · `<!-- pagebreak -->` · 문장 안 `**굵게**` 와 `코드`.

한글 폰트 임베딩·검증은 scripts/build_business_plan_docx.py 의 함수를 그대로 쓴다
(Noto Sans KR subset → ECMA-376 §17.8.1 난독화 → fontTable 배선 · 구조 검증).

실행:
    python scripts/build_program_renewal_docx.py [-o 출력.docx] [--fonts 폰트캐시]
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_business_plan_docx as bp  # noqa: E402  — 서식·임베딩 헬퍼 재사용

SRC = ROOT / "docs" / "renewal-program-2026-11-07.md"
OUT = ROOT / "PlaceOS_Program_리뉴얼_보고서_2026-11-07.docx"
FOOTER = "PlaceOS · Program 리뉴얼 보고서 · 2026-11-07"
TEXT_W = 16.2  # A4 21cm − 좌우 여백 2.4cm×2

_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def inline(p, text: str, *, size=10.5, color=bp.INK, bold=False):
    """문장 안 **굵게**·`코드` 를 런으로 나눠 쓴다(코드는 글꼴을 바꾸지 않고 색만 — 임베딩 글꼴 하나로 간다)."""
    for tok in _INLINE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            bp.run(p, tok[2:-2], size=size, bold=True, color=bp.NAVY if not bold else color)
        elif tok.startswith("`") and tok.endswith("`"):
            bp.run(p, tok[1:-1], size=size * 0.95, bold=bold, color=bp.NAVY)
        else:
            bp.run(p, tok, size=size, bold=bold, color=color)


BODY = 10.0   # 본문 글자 크기 — 표·코드가 많은 문서라 사업 기획안(10.5)보다 한 단계 작다


def paragraph(doc, text: str):
    # 왼쪽 정렬 — 양쪽 정렬은 긴 코드·URL 이 낀 줄의 글자 사이를 벌려 놓는다(2026-11-07 미리보기에서 확인)
    p = bp.para(doc, before=0, after=6, line=1.42, align=WD_ALIGN_PARAGRAPH.LEFT)
    inline(p, text, size=BODY)


def bullets(doc, items: list[str]):
    for it in items:
        p = bp.para(doc, after=4, line=1.4, indent=0.5, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        bp.run(p, "—  ", size=BODY, bold=True, color=bp.ACCENT)
        inline(p, it, size=BODY)


def note(doc, lines: list[str]):
    """전제·경고 상자 — 위아래 테두리만(4면 지정은 OOXML 스키마 위반)."""
    for i, line in enumerate(lines):
        p = bp.para(doc, before=(9 if i == 0 else 0), after=(9 if i == len(lines) - 1 else 3),
                    line=1.45, indent=0.32, right=0.32)
        whole_bold = line.startswith("**") and line.endswith("**") and line.count("**") == 2
        inline(p, line[2:-2] if whole_bold else line, size=9.5, bold=whole_bold)
        bp.para_shade(p, bp.NOTEFILL)
        if i == 0:
            bp.para_border(p, ("top",), color=bp.ACCENT, sz=12, space=8)
        if i == len(lines) - 1:
            bp.para_border(p, ("bottom",), color=bp.ACCENT, sz=12, space=8)
        else:
            bp.keep_with_next(p)


def _disp_len(s: str) -> float:
    s = re.sub(r"\*\*|`", "", s)
    return sum(1.0 if ord(c) > 0x2E7F else 0.55 for c in s)


def widths(rows: list[list[str]]) -> list[float]:
    n = len(rows[0])
    weight = []
    for c in range(n):
        lens = [_disp_len(r[c]) for r in rows if c < len(r)]
        longest = max(lens)
        typical = sorted(lens)[len(lens) // 2]
        weight.append(max(4.0, min(60.0, 0.6 * longest + 0.4 * typical)))
    total = sum(weight)
    w = [max(1.7, TEXT_W * x / total) for x in weight]
    scale = TEXT_W / sum(w)
    return [round(x * scale, 2) for x in w]


def table(doc, rows: list[list[str]]):
    """bp.make_table 과 같은 모양 — 칸 안에서도 **굵게**·`코드` 를 살린다."""
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    n = len(rows[0])
    rows = [r + [""] * (n - len(r)) for r in rows]
    wcm = widths(rows)
    size = 8.5 if n >= 5 else 9.0
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
    for gc, w in zip(grid.findall(qn("w:gridCol")), wcm):
        gc.set(qn("w:w"), str(int(w * 567)))
    for ri, row in enumerate(rows):
        head = ri == 0
        tr = t.rows[ri]
        trPr = tr._tr.get_or_add_trPr()
        if head:
            trPr.append(bp._el("w:tblHeader", val="true"))
        trPr.append(bp._el("w:cantSplit", val="true"))
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            cell.width = Cm(wcm[ci])
            bp.cell_margins(cell)
            if head:
                bp.cell_shade(cell, bp.HEADFILL)
            elif ri % 2 == 0:
                bp.cell_shade(cell, bp.ZEBRA)
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
            p = bp.para(cell, before=0, after=0, line=1.25)
            if head:
                bp.run(p, re.sub(r"\*\*|`", "", val), size=size, bold=True, color=bp.NAVY)
            else:
                inline(p, val, size=size, bold=(ci == 0 and n > 2 and _disp_len(val) < 14))
    doc.add_paragraph().paragraph_format.space_after = bp.Pt(4)


def figure(doc, caption: str, rel: str):
    path = (SRC.parent / rel).resolve()
    if not path.exists():
        raise SystemExit(f"그림이 없다: {path} — scripts/program_renewal_charts.py 를 먼저 돌린다")
    p = bp.para(doc, before=8, after=0, line=1.0, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.add_run().add_picture(str(path), width=Cm(15.6))
    bp.keep_with_next(p)
    bp.caption(doc, caption)


def page_break(doc):
    p = bp.para(doc, before=0, after=0)
    bp.run(p, "").add_break(WD_BREAK.PAGE)


def cover(doc, title: str, intro: list[str]):
    p = bp.para(doc, before=90, after=0, line=1.1)
    bp.run(p, "PlaceOS", size=40, bold=True, color=bp.NAVY, spacing=-20)
    p = bp.para(doc, before=2, after=0, line=1.25)
    bp.run(p, "창업자를 위한 부동산 앱 · PPPP — Program", size=13, color=bp.MUTED)
    p = bp.para(doc, before=24, after=0, line=1.2)
    bp.para_border(p, ("top",), color=bp.ACCENT, sz=18, space=14)
    main, _, sub = title.partition(" — ")
    bp.run(p, main, size=24, bold=True, color=bp.INK)
    if sub:
        p = bp.para(doc, before=2, after=0, line=1.35)
        bp.run(p, sub, size=13, bold=True, color=bp.ACCENT)
    p = bp.para(doc, before=18, after=4, line=1.4)
    bp.run(p, "기능 네 가지 ", size=10, bold=True, color=bp.MUTED)
    bp.run(p, "네트워킹 · 지원 프로그램 · 오프라인 마케팅 솔루션 · 가설 검증", size=11.5, bold=True, color=bp.NAVY)
    note(doc, intro)


def build(out: Path) -> Path:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, FOOTER)

    title, intro, i = "", [], 0
    while i < len(lines) and not lines[i].startswith("## "):   # 첫 장 앞 = 표지
        s = lines[i].strip()
        if s.startswith("# "):
            title = s[2:].strip()
        elif s:
            intro.append(s)
        i += 1
    cover(doc, title, intro)
    page_break(doc)

    buf: list[str] = []
    table_rows: list[list[str]] = []
    quote: list[str] = []
    items: list[str] = []

    def flush():
        nonlocal buf, table_rows, quote, items
        if buf:
            paragraph(doc, " ".join(buf)); buf = []
        if table_rows:
            table(doc, table_rows); table_rows = []
        if quote:
            note(doc, quote); quote = []
        if items:
            bullets(doc, items); items = []

    for raw in lines[i:]:
        s = raw.rstrip()
        if not s.strip():
            flush(); continue
        if s.strip() == "<!-- pagebreak -->":
            flush(); page_break(doc); continue
        if s.startswith("## "):
            flush()
            m = re.match(r"^##\s+(.+?)\.\s+(.*)$", s)
            num, head = (m.group(1), m.group(2)) if m else ("", s[3:])
            bp.h1(doc, num, head); continue
        if s.startswith("### "):
            flush()
            m = re.match(r"^###\s+(\S*\d\S*)\s+(.*)$", s)
            num, head = (m.group(1), m.group(2)) if m else ("", s[4:])
            bp.h2(doc, num, head); continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)$", s.strip())
        if m:
            flush(); figure(doc, m.group(1), m.group(2)); continue
        if s.startswith("|"):
            if buf or quote or items:
                flush()
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            table_rows.append(cells); continue
        if s.startswith("> "):
            if buf or table_rows or items:
                flush()
            quote.append(s[2:].strip()); continue
        if s.startswith("- "):
            if buf or table_rows or quote:
                flush()
            items.append(s[2:].strip()); continue
        if table_rows or quote or items:
            flush()
        buf.append(s.strip())
    flush()
    doc.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(OUT))
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리(기본: 임시 디렉터리)")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        print("1) 문서 생성")
        build(out)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("2) 한글 폰트 임베딩")
        bp.embed_fonts(out, bp.fetch_fonts(cache), work)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("3) 검증")
        bp.verify_embedding(out)
    print(f"\n완료: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
