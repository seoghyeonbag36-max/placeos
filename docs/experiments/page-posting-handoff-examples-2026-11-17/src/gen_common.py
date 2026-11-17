"""공통 틀 — 토큰(라이트·다크), 머리·목차·꼬리, 칩, 툴팁, 표 차트 도우미. 외부 글꼴·스크립트 없이 오프라인으로 열린다."""
import html

BASE = "main 79890bc3(2026-11-15 머지분) · 재측정 2026-11-17"

FILES = [
    ("placeos-00-verify.html", "00", "「왜 바꾸나」 검증 · 목차"),
    ("placeos-01-invest.html", "01", "결정 ① 투자비 실측"),
    ("placeos-02-questions.html", "02", "결정 ② 네 질문·정체성"),
    ("placeos-03-interior-marketing.html", "03", "결정 ③ 인테리어·마케팅 칸"),
    ("placeos-04-privacy.html", "04", "결정 ④ 처리방침 목적"),
    ("placeos-05-before-after.html", "05", "전/후 기대값"),
    ("placeos-06-menu-fill.html", "06", "메뉴 「예시 채우기」"),
]

CSS = r"""
:root{
  --bg:#f6f6f3;--surface:#ffffff;--fg:#1c1e22;--muted:#5a606a;--line:#e2e3e7;--code-bg:#f0f1f3;
  --accent:#1d5fd6;--accent-bg:#e7effd;--violet:#6a4bb8;--violet-bg:#efeafa;
  --decide:#9a5600;--decide-bg:#fdf1df;--ok:#18794e;--ok-bg:#e5f4ec;--warn:#b42318;--warn-bg:#fdecea;
  --chart-surface:#fcfcfb;
  --seq-100:#cde2fb;--seq-200:#9ec5f4;--seq-300:#6da7ec;--seq-400:#3987e5;--seq-500:#256abf;--seq-600:#184f95;
  --st-good:#0ca30c;--st-warn:#fab219;--st-serious:#ec835a;--st-critical:#d03b3b;--st-none:#c9c7c0;
  --mock-bg:#f9f9fb;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#111316;--surface:#191c20;--fg:#e6e8eb;--muted:#a0a6af;--line:#2b2f35;--code-bg:#23272c;
    --accent:#86adff;--accent-bg:#1a2842;--violet:#bba6f6;--violet-bg:#28213d;
    --decide:#f1b864;--decide-bg:#382810;--ok:#6fd3a1;--ok-bg:#12301f;--warn:#ff9a8f;--warn-bg:#3a1714;
    --chart-surface:#1a1a19;--st-none:#55534e;--mock-bg:#15181c;
  }
}
:root[data-theme="dark"]{
  --bg:#111316;--surface:#191c20;--fg:#e6e8eb;--muted:#a0a6af;--line:#2b2f35;--code-bg:#23272c;
  --accent:#86adff;--accent-bg:#1a2842;--violet:#bba6f6;--violet-bg:#28213d;
  --decide:#f1b864;--decide-bg:#382810;--ok:#6fd3a1;--ok-bg:#12301f;--warn:#ff9a8f;--warn-bg:#3a1714;
  --chart-surface:#1a1a19;--st-none:#55534e;--mock-bg:#15181c;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,sans-serif;
  font-size:16px;line-height:1.7;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:960px;margin:0 auto;padding:28px 16px 80px}
.eyebrow{color:var(--muted);font-size:14px;margin:0 0 6px}
h1{font-size:29px;line-height:1.3;margin:0 0 12px;letter-spacing:-.01em}
h2{font-size:22px;line-height:1.35;margin:44px 0 12px;padding-top:10px;border-top:1px solid var(--line)}
h3{font-size:18px;margin:24px 0 8px}
h4{font-size:16px;margin:16px 0 6px}
p{margin:0 0 12px} ul,ol{margin:0 0 12px;padding-left:22px} li{margin:4px 0}
a{color:var(--accent)}
code{font-family:ui-monospace,"Cascadia Mono",Consolas,"D2Coding",monospace;font-size:.88em;background:var(--code-bg);padding:1px 5px;border-radius:4px;word-break:break-all}
pre{background:var(--code-bg);border-radius:8px;padding:12px 14px;overflow-x:auto;font-size:13.5px;line-height:1.6;margin:8px 0 14px}
pre code{background:none;padding:0;word-break:normal}
.lede{font-size:17px}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;color:var(--muted);font-size:14px;margin-top:8px}
.chip{display:inline-block;font-size:12.5px;font-weight:600;padding:2px 9px;border-radius:999px;white-space:nowrap;vertical-align:2px}
.chip.ok{background:var(--ok-bg);color:var(--ok)} .chip.warn{background:var(--warn-bg);color:var(--warn)}
.chip.decide{background:var(--decide-bg);color:var(--decide)} .chip.info{background:var(--accent-bg);color:var(--accent)}
.chip.v{background:var(--violet-bg);color:var(--violet)} .chip.mute{background:var(--code-bg);color:var(--muted)}
nav.files{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 6px;font-size:13.5px}
nav.files a{display:inline-block;padding:4px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--fg);text-decoration:none}
nav.files a[aria-current="page"]{background:var(--accent);border-color:var(--accent);color:#fff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) nav.files a[aria-current="page"]{color:#0b1220}}
:root[data-theme="dark"] nav.files a[aria-current="page"]{color:#0b1220}
.callout{border-left:4px solid var(--accent);background:var(--surface);border-radius:0 8px 8px 0;padding:12px 16px;margin:12px 0 16px}
.callout.decide{border-left-color:var(--decide)} .callout.warn{border-left-color:var(--warn)} .callout.ok{border-left-color:var(--ok)}
.callout>:last-child{margin-bottom:0}
.tbl{overflow-x:auto;margin:8px 0 16px;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:15px}
caption{caption-side:top;text-align:left;padding:10px 12px 0;color:var(--muted);font-size:13.5px}
th,td{text-align:left;vertical-align:top;padding:9px 11px;border-bottom:1px solid var(--line)}
th{font-size:13.5px;color:var(--muted);font-weight:600;background:var(--code-bg)}
tbody th{background:transparent;color:var(--fg);font-size:14.5px;min-width:7.5em}
tr:last-child td,tr:last-child th{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:10px 0 16px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.tile .k{color:var(--muted);font-size:13.5px}
.tile .v{font-size:26px;font-weight:700;line-height:1.25;margin:4px 0;font-variant-numeric:tabular-nums}
.tile .v small{font-size:15px;font-weight:600;color:var(--muted)}
.tile .s{font-size:13.5px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.grid2>*{min-width:0} .mock pre{max-width:100%}
@media (max-width:720px){.grid2{grid-template-columns:1fr} h1{font-size:24px}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card h4{margin-top:0}
.mock{background:var(--mock-bg);border:1px dashed var(--line);border-radius:12px;padding:14px}
.mock .label{font-size:12.5px;color:var(--muted);font-weight:600;letter-spacing:.02em;margin-bottom:6px}
.before{border-top:4px solid var(--st-none)} .after{border-top:4px solid var(--accent)}
.src{font-size:13px;color:var(--muted)}
footer{margin-top:52px;color:var(--muted);font-size:13.5px;border-top:1px solid var(--line);padding-top:14px}
details{margin:8px 0 14px} summary{cursor:pointer;color:var(--accent);font-weight:600}
.tip{position:absolute;z-index:50;display:none;max-width:300px;background:var(--fg);color:var(--bg);font-size:13px;line-height:1.5;padding:6px 9px;border-radius:6px;pointer-events:none;box-shadow:0 4px 14px rgba(0,0,0,.18)}
/* 차트: 구간 표(순차 파랑) */
.heat td.cell{text-align:center;font-variant-numeric:tabular-nums;font-weight:600;min-width:56px}
.heat td.cell:focus{outline:2px solid var(--fg);outline-offset:-2px}
/* 차트: 상태 100% 막대 */
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13.5px;color:var(--muted);margin:6px 0 10px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px}
.sbar-row{display:grid;grid-template-columns:150px minmax(0,1fr);gap:10px;align-items:center;margin:6px 0}
.sbar-row .nm{font-size:14px}
.sbar{display:flex;gap:2px;height:22px;background:var(--chart-surface);border-radius:4px}
.sbar b{display:block;height:100%;min-width:2px}
.sbar b:first-child{border-radius:4px 0 0 4px} .sbar b:last-child{border-radius:0 4px 4px 0}
.sbar b:focus{outline:2px solid var(--fg);outline-offset:1px}
@media (max-width:560px){.sbar-row{grid-template-columns:1fr}}
@media print{body{background:#fff;color:#000} nav.files{display:none} .card,.tbl,.tile{break-inside:avoid}}
"""

TIP_JS = r"""
(()=>{const tip=document.createElement('div');tip.className='tip';tip.setAttribute('role','tooltip');document.body.appendChild(tip);
function place(t){tip.textContent=t.getAttribute('data-tip');tip.style.display='block';const r=t.getBoundingClientRect();
const w=tip.offsetWidth,h=tip.offsetHeight;let x=r.left+r.width/2-w/2;x=Math.max(8,Math.min(window.innerWidth-w-8,x));
let y=r.top-h-8;if(y<8)y=r.bottom+8;tip.style.left=(x+window.scrollX)+'px';tip.style.top=(y+window.scrollY)+'px';}
const on=e=>{const t=e.target.closest&&e.target.closest('[data-tip]');if(t)place(t)};
const off=e=>{const t=e.target.closest&&e.target.closest('[data-tip]');if(t)tip.style.display='none'};
document.addEventListener('mouseover',on);document.addEventListener('mouseout',off);
document.addEventListener('focusin',on);document.addEventListener('focusout',off);})();
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def chip(text, kind="info"):
    return f'<span class="chip {kind}">{text}</span>'


def nav(current):
    cur = ' aria-current="page"'
    items = "".join(f'<a href="{f}"{cur if f == current else ""}>{n} · {t}</a>' for f, n, t in FILES)
    return f'<nav class="files" aria-label="예시 파일">{items}</nav>'


def page(fname, title, h1, lede, chips_html, body, extra_js=""):
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
<p class="eyebrow">PlaceOS · Page·Posting 인계 예시 · 2026-11-17</p>
<h1>{h1}</h1>
<p class="lede">{lede}</p>
<div class="meta">{chips_html}<span>기준: {BASE}</span></div>
{nav(fname)}
</header>
<main>
{body}
</main>
<footer>
PlaceOS 내부 검토용 예시 · 숫자는 기준일 값이라 낡습니다 — 인용 전에 <code>python scripts/pppp_status.py</code> ·
<code>python scripts/posting_payback_snapshot.py</code> 로 다시 재세요. 법률·세무 자문이 아닙니다.
</footer>
</div>
<script>{TIP_JS}</script>
{extra_js}
</body>
</html>
"""


SEQ = ["--seq-100", "--seq-200", "--seq-300", "--seq-400", "--seq-500", "--seq-600"]


def heat_table(caption, col_labels, rows, unit="곳", row_head="시나리오"):
    """rows: [(행 이름, [값...], 보조 텍스트)] — 칸 색은 값 크기(순차 파랑 한 색). 0 은 칠하지 않는다."""
    mx = max(v for _, vals, _ in rows for v in vals) or 1
    head = "".join(f'<th scope="col" class="num">{esc(c)}</th>' for c in col_labels)
    out = [f'<div class="tbl heat"><table><caption>{caption}</caption><thead><tr><th scope="col">{row_head}</th>{head}<th scope="col">비고</th></tr></thead><tbody>']
    for name, vals, note in rows:
        cells = []
        for c, v in zip(col_labels, vals):
            if v == 0:
                style = "background:transparent;color:var(--muted)"
            else:
                i = min(5, int((v / mx) * 6 - 1e-9))
                fg = "#ffffff" if i >= 3 else "#0b0b0b"
                style = f"background:var({SEQ[i]});color:{fg}"
            cells.append(f'<td class="cell" tabindex="0" style="{style}" data-tip="{esc(name)} · {esc(c)}: {v:,}{unit}">{v:,}</td>')
        out.append(f'<tr><th scope="row">{name}</th>{"".join(cells)}<td class="src">{note}</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


ST = [("ledger_ok", "대장상 가능", "--st-good", "✓"), ("needs_check", "확인 필요", "--st-warn", "?"),
      ("use_change_needed", "대장상 용도 변경 필요", "--st-serious", "↺"), ("zoning_prohibited", "용도지역상 금지", "--st-critical", "✕"),
      ("missing_inputs", "자료 부족", "--st-none", "…")]


def status_bars(rows, total_note):
    """rows: [(업종 이름, {status: n})] — 100% 막대. 상태 색은 상태에만 쓰고, 기호·이름을 함께 단다."""
    legend = "".join(f'<span><i style="background:var({c})"></i>{sym} {lab}</span>' for _k, lab, c, sym in ST)
    out = [f'<div class="legend" aria-hidden="true">{legend}</div>']
    for name, d in rows:
        tot = sum(d.values()) or 1
        segs = []
        for k, lab, c, sym in ST:
            v = d.get(k, 0)
            if not v:
                continue
            segs.append(f'<b tabindex="0" style="flex:{v} 0 0;background:var({c})" data-tip="{esc(name)} · {sym} {lab}: {v:,}곳 ({v / tot * 100:.1f}%)" '
                        f'aria-label="{esc(name)} {lab} {v:,}곳"></b>')
        out.append(f'<div class="sbar-row"><span class="nm">{name}</span><div class="sbar" role="img" aria-label="{esc(name)} 상태 분포">{"".join(segs)}</div></div>')
    # 표 보기
    head = "".join(f'<th scope="col" class="num">{sym} {lab}</th>' for _k, lab, _c, sym in ST)
    body = "".join(f'<tr><th scope="row">{n}</th>' + "".join(f'<td class="num">{d.get(k, 0):,}</td>' for k, *_ in ST) + "</tr>" for n, d in rows)
    out.append(f'<details><summary>표로 보기</summary><div class="tbl"><table><caption>{total_note}</caption><thead><tr><th scope="col">업종</th>{head}</tr></thead><tbody>{body}</tbody></table></div></details>')
    return "".join(out)


def won(v):
    return f"{round(v):,}원"


def man(v):
    return f"{round(v):,}만원"
