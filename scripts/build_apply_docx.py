"""docs/apply 제출본 Markdown 을 Word(.docx)로 변환한다 (제목·문단·굵게·목록·표만 지원).

사용: python scripts/build_apply_docx.py <입력.md> [출력.docx]
글꼴은 'Malgun Gothic' 이름만 지정한다. 폰트 파일이 없는 환경에서는 임베딩하지 않으므로,
Cowork 프리뷰에서 박스로 보이면 docs/papers/page-study/build_page_docx.py 의 embed_fonts 경로를 쓴다.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "Malgun Gothic"


def set_font(style_or_run):
    style_or_run.font.name = FONT
    rf = style_or_run.element.get_or_add_rPr().get_or_add_rFonts()
    for k in ("ascii", "hAnsi", "eastAsia", "cs"):
        rf.set(qn("w:" + k), FONT)
    for k in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rf.attrib.pop(qn("w:" + k), None)


def runs(par, text):
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not part:
            continue
        r = par.add_run(part)
        r.bold = i % 2 == 1
        set_font(r)


def borders(cell, top_bottom_only=True):
    tcPr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for side in ("top", "bottom"):  # 4면 지정은 OOXML 스키마 위반 소지 — top+bottom 만
        e = OxmlElement("w:" + side)
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), "999999")
        b.append(e)
    tcPr.append(b)


def build(src: Path, out: Path):
    lines = src.read_text(encoding="utf-8-sig").splitlines()
    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin = s.bottom_margin = Cm(2.2)
    s.left_margin = s.right_margin = Cm(2.3)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3", "List Bullet", "List Number"):
        st = doc.styles[name]
        set_font(st)
        st.font.color.rgb = RGBColor(0, 0, 0)
    n = doc.styles["Normal"]
    n.font.size = Pt(10.5)
    n.paragraph_format.line_spacing = 1.45
    n.paragraph_format.space_after = Pt(6)
    for name, size in (("Title", 18), ("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 11)):
        doc.styles[name].font.size = Pt(size)
        doc.styles[name].font.bold = True
    fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
    fp = s.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER; fp._p.append(fld)

    i = 0
    para = []

    def flush():
        if para:
            runs(doc.add_paragraph(), " ".join(x.strip() for x in para))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            w = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=w)
            for ri, r in enumerate(rows):
                for ci in range(w):
                    c = t.cell(ri, ci)
                    c.text = ""
                    p = c.paragraphs[0]
                    p.paragraph_format.space_after = Pt(2)
                    runs(p, r[ci] if ci < len(r) else "")
                    for run in p.runs:
                        run.font.size = Pt(9.5)
                        if ri == 0 and not rows[0][0] == "":
                            run.bold = True
                    borders(c)
            doc.add_paragraph()
            continue
        m = re.match(r"(#{1,3}) (.+)", ln)
        if m:
            flush()
            lvl = len(m.group(1))
            if lvl == 1:
                p = doc.add_paragraph(style="Title"); runs(p, m.group(2)); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p = doc.add_paragraph(style=f"Heading {lvl - 1}"); runs(p, m.group(2))
        elif re.match(r"\s*[-*] ", ln):
            flush(); runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*] ", "", ln))
        elif re.match(r"\d+\. ", ln):
            flush(); runs(doc.add_paragraph(), ln)  # 번호는 원문 그대로 둔다
        elif ln.strip() == "" or ln.strip() == "---":
            flush()
        elif ln.startswith("   ") and para == [] and False:
            pass
        else:
            para.append(ln)
        i += 1
    flush()
    doc.core_properties.author = ""
    doc.core_properties.title = lines[0].lstrip("# ").strip()
    doc.save(out)


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".docx")
    build(src, out)
    print(out)
