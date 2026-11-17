"""표현 유형 5종 — 같은 내용(content.build)을 다섯 가지 방식으로 그린다.

A 보고서형 · B 대시보드형 · C 슬라이드형 · D 카드형 · E 질문 흐름형.
라운드마다 개선은 이 파일의 해당 유형 함수(그리고 TYPE_CSS)만 고친다 — 내용·숫자는 content.py 가 정한다.
"""
import sys
from pathlib import Path

from content import CORE_TOKENS, FACTS, MENU_LINK, SET_LINK, build  # noqa: F401 (FACTS 는 harness 가 읽는다)
from gen_common import CSS, TIP_JS, chip, esc, heat_table, status_bars
from content import BIN_LAB

TYPES = [("type-a-report.html", "A", "보고서형"), ("type-b-dashboard.html", "B", "대시보드형"), ("type-c-slides.html", "C", "슬라이드형"),
         ("type-d-cards.html", "D", "카드형"), ("type-e-qa.html", "E", "질문 흐름형")]
TN = {"premium": "고급화", "value": "가성비", "factory": "기능중심"}


def tnav(cur):
    cur_attr = ' aria-current="page"'
    items = "".join(f'<a href="{f}"{cur_attr if f == cur else ""}>{k} · {n}</a>' for f, k, n in TYPES)
    return (f'<nav class="files" aria-label="표현 유형">{items}<a href="../compare/compare.html">비교 보고서</a>'
            f'<a href="{SET_LINK}">원본 7개 묶음</a></nav>')


def shell(fname, title, eyebrow, body, css="", js=""):
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{CSS}{css}</style></head>
<body><div class="wrap">
<p class="eyebrow">{eyebrow}</p>
{body}
<footer>PlaceOS 내부 검토용 · 기준 main 79890bc3 · 재측정 2026-11-17 · 숫자는 낡습니다 — 인용 전 다시 재세요. 법률·세무 자문이 아닙니다.</footer>
</div><script>{TIP_JS}</script>{js}</body></html>"""


# ───────── 공통 조각
def core_list(c):
    return "<ul class=\"core\">" + "".join(f'<li><b>{x["tag"]}</b> · {x["head"]}</li>' for x in c["core"]) + "</ul>"


def claims_table(c):
    rows = "".join(f'<tr><th scope="row">{esc(a)}</th><td>{esc(b)}</td><td>{chip(v, k)}</td></tr>' for a, b, v, k in c["claims"])
    return f'<div class="tbl"><table><thead><tr><th scope="col">주장</th><th scope="col">확인한 것</th><th scope="col">판정</th></tr></thead><tbody>{rows}</tbody></table></div>'


def levers_tiles(c):
    return '<div class="tiles">' + "".join(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for k, v, s in c["levers"]) + "</div>"


def decisions_table(c):
    rows = "".join(f'<tr><th scope="row">{d["id"]} {esc(d["name"])}</th><td>{chip(d["status"], d["kind"])}</td><td>{esc(d["change"])}</td>'
                   f'<td><span class="src">전</span> {esc(d["before"])}<br><span class="src">후</span> {esc(d["after"])}</td><td>{esc(d["next"])}</td></tr>' for d in c["decisions"])
    return (f'<div class="tbl"><table><thead><tr><th scope="col">결정</th><th scope="col">상태</th><th scope="col">무엇이 바뀌나</th>'
            f'<th scope="col">예시(전/후)</th><th scope="col">다음</th></tr></thead><tbody>{rows}</tbody></table></div>')


def metrics_table(c):
    kinds = {"측정": "ok", "계산": "info", "설계": "v", "모름": "mute"}
    rows = "".join(f'<tr><th scope="row">{esc(n)}</th><td>{esc(b)}</td><td>{esc(a)}</td><td>{chip(k, kinds[k])}</td></tr>' for n, b, a, k in c["metrics"])
    return f'<div class="tbl"><table><thead><tr><th scope="col">작업</th><th scope="col">지금</th><th scope="col">바뀐 뒤(기대)</th><th scope="col">근거</th></tr></thead><tbody>{rows}</tbody></table></div>'


def scen_heat(c):
    return heat_table("추천 전략 회수기간 구간별 자리 수(836곳) — 투자비만 바꾼 재계산", BIN_LAB, c["scen"])


def hist_heat(c):
    return heat_table("요구 월매출이 서울 점포 평균의 몇 배인가(836곳)", [h[0] for h in c["hist"]], [("자리 수", [h[1] for h in c["hist"]], c["hist_note"])], row_head="")


def usecheck_bars(c):
    return status_bars(c["usecheck"], "빈 층 판정 분포 — 서울 빈 층 14,517곳 · 서술 통계(실력 아님) · 강남·송파·강동 3,943곳은 자료 부족")


def menu_table(c):
    rows = []
    for m in c["menu"]:
        for tk, t in m["tiers"].items():
            rows.append(f'<tr><th scope="row">{m["label"]} · {TN[tk]}</th><td class="num">{t["price"]:,.0f}원</td><td class="num">{t["rate"]*100:.1f}%</td>'
                        f'<td class="num">{t["daily"]:,}개</td><td class="num">{t["pm"]:.0f}만원</td><td class="num">{t["first"]:.0f}만원</td><td class="num">{t["pre"]:,.0f}만원</td></tr>')
    return (f'<div class="tbl"><table><caption>월세 414만원(추천 자리 중앙) · 최저임금 · 예시 값 — 직접 눌러 보기: <a href="{MENU_LINK}">메뉴 「예시 채우기」 v2</a></caption>'
            f'<thead><tr><th scope="col">업종 · 가격대</th><th scope="col" class="num">객단가</th><th scope="col" class="num">원가율</th><th scope="col" class="num">하루 판매</th>'
            f'<th scope="col" class="num">주기 구매(월)</th><th scope="col" class="num">개업 첫 주문</th><th scope="col" class="num">개업 전 필요한 돈</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def overlap_table(c):
    rows = "".join(f'<tr><th scope="row">{esc(a)}</th><td>{esc(b)}</td><td>{esc(d)}</td></tr>' for a, b, d in c["overlap"])
    return (f'<p>배포를 기다리는 <code>claude/twin-roads</code>(11개 기능)는 main 보다 <b>31커밋</b> 뒤에 있습니다. 인계 작업과 겹치는 곳:</p>'
            f'<div class="tbl"><table><thead><tr><th scope="col">브랜치 기능</th><th scope="col">닿는 작업</th><th scope="col">처리</th></tr></thead><tbody>{rows}</tbody></table></div>')


def sources_list(c):
    return "<ul class=\"src-list\">" + "".join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in c["sources"]) + "</ul>"


MENU_LINE = ("메뉴 「예시 채우기」 v2 — 판매가·비중·원가(재료·포장·수수료), 한 번 사는 준비물, <b>주기 구매</b>(식재료·포장 발주 계획 · 위생·청소·설비 유지·서비스), "
             "<b>개업 첫 주문</b>, 하루 몇 개 팔아야 하나까지 업종 6 × 가격대 3")

TYPE_CSS = {
    "A": """
.core{margin:0;padding-left:20px} .core li{margin:6px 0}
.toc{columns:2;column-gap:28px;font-size:15px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 16px 12px 34px}
@media (max-width:720px){.toc{columns:1}}
/* r1 — 폰에서 글 표는 행 단위 블록으로 쌓는다(열 이름은 칸 앞에). 숫자 표(메뉴·구간)는 그대로 */
@media (max-width:640px){
.stack .tbl{border:0;background:none;overflow:visible}
.stack table,.stack tbody,.stack tr,.stack th,.stack td{display:block;width:auto}
.stack thead{display:none}
.stack tr{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 10px}
.stack th,.stack td{border:0;padding:3px 0}
.stack tbody th{font-size:16px;min-width:0}
.stack td::before{display:inline-block;margin-right:8px;font-size:13px;font-weight:600;color:var(--muted)}
.st-claims td:nth-of-type(1)::before{content:"확인한 것"} .st-claims td:nth-of-type(2)::before{content:"판정"}
.st-dec td:nth-of-type(1)::before{content:"상태"} .st-dec td:nth-of-type(2)::before{content:"무엇이 바뀌나"}
.st-dec td:nth-of-type(3)::before{content:"예시"} .st-dec td:nth-of-type(4)::before{content:"다음"}
.st-met td:nth-of-type(1)::before{content:"지금"} .st-met td:nth-of-type(2)::before{content:"바뀐 뒤(기대)"} .st-met td:nth-of-type(3)::before{content:"근거"}
.st-ovl td:nth-of-type(1)::before{content:"닿는 작업"} .st-ovl td:nth-of-type(2)::before{content:"처리"}
}
/* r2 — 재현 줄의 코드 글자 11.4px → 본문 작은 글자와 같은 13px */
.src code{font-size:1em}
""",
    "B": """
.dash{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;margin:12px 0}
.dash>*{min-width:0}
.span4{grid-column:span 4} .span6{grid-column:span 6} .span8{grid-column:span 8} .span12{grid-column:span 12}
@media (max-width:900px){.span4,.span6,.span8{grid-column:span 12}}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi .k{font-size:13px;color:var(--muted)} .kpi .v{font-size:22px;font-weight:700;line-height:1.3;margin:4px 0}
.kpi .s{font-size:13px;color:var(--muted)}
.board{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
@media (max-width:900px){.board{grid-template-columns:1fr 1fr}} @media (max-width:520px){.board{grid-template-columns:1fr}}
.board .card{padding:10px 12px} .board .card h4{font-size:15px;margin:0 0 6px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.panel h3{margin:0 0 8px;font-size:16px}
/* r1 — 「열기」 줄을 누르기 쉬운 단추로(높이 44px) */
details>summary{display:flex;align-items:center;gap:8px;min-height:44px;padding:6px 14px;border:1px solid var(--line);border-radius:10px;background:var(--surface);list-style:none}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"▸";color:var(--muted)} details[open]>summary::before{content:"▾"}
details[open]>summary{margin-bottom:8px}
/* r2 — 결정 보드의 긴 상태 칩이 카드 밖으로 넘치지 않게(줄바꿈 허용) */
.board .chip{white-space:normal;max-width:100%;border-radius:10px}
""",
    "C": """
.deck{position:relative}
.slide{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin:10px 0}
.slide h2{border:0;margin:0 0 12px;padding:0;font-size:24px}
.slide .lead{font-size:18px}
.ctl{position:sticky;top:0;z-index:5;display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:var(--bg);padding:8px 0}
.ctl button{font:inherit;font-size:15px;padding:6px 14px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--fg);cursor:pointer}
.ctl button:disabled{opacity:.45;cursor:default}
.ctl #ctr{font-variant-numeric:tabular-nums;color:var(--muted)}
/* r2 — 원하는 장으로 바로 가는 목차 */
.ctl select{font:inherit;font-size:15px;padding:6px 10px;min-height:38px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--fg);flex:1 1 200px;min-width:0;max-width:100%}
.core{margin:0;padding-left:20px;font-size:17px} .core li{margin:8px 0}
@media (max-width:720px){.slide{padding:16px}}
""",
    "D": """
.col{max-width:540px;margin:0 auto}
.chipbar{position:sticky;top:0;z-index:5;display:flex;gap:6px;overflow-x:auto;background:var(--bg);padding:8px 0}
.chipbar a{flex:0 0 auto;font-size:13.5px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--fg);text-decoration:none}
.c{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin:10px 0}
.c .tag{font-size:12.5px;font-weight:700;color:var(--accent)}
.c .big{font-size:26px;font-weight:800;line-height:1.25;margin:4px 0}
.c .one{margin:0} .c .why{font-size:13px;color:var(--muted);margin:6px 0 0}
.sec{font-size:13px;color:var(--muted);font-weight:700;letter-spacing:.04em;margin:22px 0 4px}
.sumcard ul{margin:6px 0 0;padding-left:18px} .sumcard li{margin:4px 0}
/* r1 — 검증 카드는 판정을 크게, 주장은 본문 굵기로 */
.c .big.ok{color:var(--ok)} .c .big.warn{color:var(--warn)} .c .big.info{color:var(--accent)} .c .big.decide{color:var(--decide)}
.c .one.claim{font-weight:600}
/* r2 — 메뉴 예시 카드의 작은 표 */
.minibox{overflow-x:auto;margin-top:6px}
.c table.mini{font-size:13.5px}
.c table.mini th,.c table.mini td{padding:5px 5px;border-bottom:1px solid var(--line)}
.c table.mini thead th{font-size:12.5px;line-height:1.3;background:transparent;vertical-align:bottom}
.c table.mini tbody th{min-width:0;font-size:13.5px;white-space:nowrap}
.c table.mini tr:last-child th,.c table.mini tr:last-child td{border-bottom:0}
""",
    "E": """
.qindex{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 16px 10px 32px;font-size:15px}
details.qa{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:10px 0}
details.qa>summary{font-size:17px;font-weight:700;color:var(--fg);list-style:none;cursor:pointer}
details.qa>summary::-webkit-details-marker{display:none}
details.qa>summary::before{content:"Q. ";color:var(--accent)}
details.qa[open]>summary{margin-bottom:8px}
.ans::before{content:"A. ";font-weight:700;color:var(--ok)}
.core{margin:6px 0 0;padding-left:20px} .core li{margin:6px 0}
.qhead{font-size:14px;font-weight:700;color:var(--muted);margin:18px 0 4px}
/* r2 — 펼치기 줄(질문 · 표로 보기)을 손가락 크기(44px)로 */
details.qa>summary{display:flex;align-items:center;gap:6px;min-height:44px} details.qa>summary::before{content:"Q.";flex:none}
details:not(.qa)>summary{display:inline-flex;align-items:center;min-height:44px;padding:4px 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
""",
}


# ───────── A 보고서형
def render_a(c):
    toc = [("s1", "검증표"), ("s2", "새로 보인 것"), ("s3", "결정 ①~④"), ("s4", "전/후 기대값"), ("s5", "메뉴 예시 채우기"), ("s6", "브랜치 겹침"), ("s7", "출처")]
    body = f"""<h1>{c["title"]}</h1>
<div class="callout ok"><p><b>요약</b></p>{core_list(c)}</div>
{tnav("type-a-report.html")}
<ol class="toc">{"".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in toc)}</ol>
<h2 id="s1">1. 「왜 바꾸나」 검증표</h2><div class="stack st-claims">{claims_table(c)}</div>
<h2 id="s2">2. 새로 보인 것 — 회수기간이 짧게 나오는 두 지렛대</h2>{levers_tiles(c)}
<p>투자비만 서울 인테리어 평균으로 바꾸면 「1개월 미만」은 {c["base"]["lt1"]} → {c["s545"]["lt1"]}곳, 회수 중앙은 {c["base"]["median"]}개월 → {c["s545"]["median"]}개월입니다.</p>
<h2 id="s3">3. 결정 ①~④ — 정한 대로 하면</h2><div class="stack st-dec">{decisions_table(c)}</div>
<h2 id="s4">4. 전/후 기대값</h2><div class="stack st-met">{metrics_table(c)}</div>{scen_heat(c)}{hist_heat(c)}
<p>추천 자리의 <b>{c["p2"]["share_over_avg"]}%</b>는 월세만 감당하려 해도 서울 점포 평균 이상을, <b>{c["p2"]["share_over_2x"]}%</b>는 2배 이상을 팔아야 합니다.</p>
{usecheck_bars(c)}
<h2 id="s5">5. 메뉴 「예시 채우기」 v2</h2><p>{MENU_LINE}.</p>{menu_table(c)}
<h2 id="s6">6. 아직 배포 안 된 브랜치와 겹치는 곳</h2><div class="stack st-ovl">{overlap_table(c)}</div>
<h2 id="s7">7. 출처 · 다시 재는 법</h2>{sources_list(c)}
<p class="src">재현: <code>python scripts/posting_payback_snapshot.py</code> · 공정위 1콜 확인은 미실행(이 환경 권한).</p>"""
    return shell("type-a-report.html", "보고서형", "PlaceOS · Page·Posting 인계 · 표현 유형 A 보고서형", body, TYPE_CSS["A"])


# ───────── B 대시보드형
def render_b(c):
    kpis = [("결론", "세 원인 모두 사실", "숫자 두 곳만 고침 — 분모 836 · 대장 용도코드 값"),
            ("「한 달 안에 본전」", f'{c["base"]["lt1"]} → {c["x3"]["lt1"]}~{c["s545"]["lt1"]}곳', f'P1(투자비 실측) 계산 · 중앙 {c["base"]["median"]}개월 → {c["s545"]["median"]}개월'),
            ("남은 결정", "③-a 만 보류", "①②④·③-b 는 11-15 승인"),
            ("방향", "요구치(P2)", "회수기간 대신 「하루 몇 개」"),
            ("현실", f'{c["p2"]["share_over_avg"]}%', "추천 자리가 월세만으로 서울 평균 이상 팔아야")]
    kpi_html = "".join(f'<div class="kpi span4"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for k, v, s in kpis[:3]) + \
        "".join(f'<div class="kpi span6"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for k, v, s in kpis[3:])
    board = "".join(f'<div class="card"><h4>{d["id"]} {esc(d["name"])}</h4>{chip(d["status"], d["kind"])}<p class="src" style="margin:6px 0 0">{esc(d["next"])}</p></div>' for d in c["decisions"])
    body = f"""<h1 style="font-size:24px">{c["title"]} — 대시보드</h1>
{tnav("type-b-dashboard.html")}
<div class="dash">{kpi_html}</div>
<div class="panel"><h3>결정 보드</h3><div class="board">{board}</div></div>
<div class="dash">
<div class="panel span6"><h3>회수기간 분포 — P1 전/후</h3>{scen_heat(c)}</div>
<div class="panel span6"><h3>요구치(P2) 미리보기</h3>{hist_heat(c)}<p class="src">2배 이상 {c["p2"]["share_over_2x"]}%</p></div>
<div class="panel span8"><h3>Page — 「내 업종이 들어갈 수 있나」</h3>{usecheck_bars(c)}</div>
<div class="panel span4"><h3>두 지렛대</h3>{"".join(f'<p><b>{k}</b><br>{v} <span class="src">{s}</span></p>' for k, v, s in c["levers"])}</div>
</div>
<details><summary>검증표 열기</summary>{claims_table(c)}</details>
<details><summary>결정 ①~④ 전/후 예시 열기</summary>{decisions_table(c)}</details>
<details><summary>작업별 전/후 기대값 열기</summary>{metrics_table(c)}</details>
<details><summary>메뉴 「예시 채우기」 v2 요약 열기</summary><p>{MENU_LINE}.</p>{menu_table(c)}</details>
<details><summary>브랜치 겹침 열기</summary>{overlap_table(c)}</details>
<details><summary>출처 열기</summary>{sources_list(c)}</details>"""
    return shell("type-b-dashboard.html", "대시보드형", "PlaceOS · Page·Posting 인계 · 표현 유형 B 대시보드형", body, TYPE_CSS["B"])


# ───────── C 슬라이드형
def render_c(c):
    d = {x["id"]: x for x in c["decisions"]}
    slides = [
        ("핵심 다섯 가지", core_list(c)),
        ("「왜 바꾸나」 — 세 원인은 모두 사실", claims_table(c)),
        ("고칠 숫자 두 곳", f'<p class="lead">「296/891」 → <b>296/836(35.4%)</b> · 분모 891 은 재현 안 됨(셀 수 있는 분모 854 · 836)</p><p class="lead">Page 14,520 · 52% · 39% → <b>14,517 · 7,472(51.5%) · 5,989(41.3%)</b></p>'),
        ("회수기간이 짧게 나오는 두 지렛대", levers_tiles(c)),
        ("결정 현황 — ③-a 만 보류", decisions_table(c)),
        ("결정 ① — 투자비를 실측으로", f'<p class="lead">{esc(d["①"]["before"])}</p><p class="lead">→ {esc(d["①"]["after"])}</p>{scen_heat(c)}'),
        ("결정 ② — 머리 문장을 요구치로", f'<p class="lead">전 {esc(d["②"]["before"])}</p><p class="lead">후 {esc(d["②"]["after"])}</p>'),
        ("결정 ③ — 마케팅은 개업 뒤, 인테리어는 보류", f'<p class="lead">③-b {esc(d["③-b"]["after"])} (시행)</p><p class="lead">③-a {esc(d["③-a"]["change"])}</p><p>{esc(d["③-a"]["after"])}</p>'),
        ("결정 ④ — 처리방침 목적", f'<p class="lead">{esc(d["④"]["change"])}</p><p>{esc(d["④"]["after"])}</p>'),
        ("작업별 전/후 기대값", metrics_table(c)),
        ("요구치(P2)로 바꾸면", f'{hist_heat(c)}<p class="lead">추천 자리 <b>{c["p2"]["share_over_avg"]}%</b>가 서울 점포 평균 이상, <b>{c["p2"]["share_over_2x"]}%</b>가 2배 이상</p>'),
        ("Page — 「내 업종이 들어갈 수 있나」", usecheck_bars(c)),
        ("메뉴 「예시 채우기」 v2", f'<p>{MENU_LINE}.</p>{menu_table(c)}'),
        ("브랜치 겹침", overlap_table(c)),
        ("출처 · 다음 단계", f'{sources_list(c)}<p>다음: 공정위 15143711 1콜 확인(P1) · 결정이 필요 없는 P2·P3·P4·2-A 착수 · ③-a 결정</p>'),
    ]
    html = "".join(f'<section class="slide" aria-label="{i + 1}. {esc(t)}"{" hidden" if i else ""}><h2>{i + 1}. {t}</h2>{b}</section>' for i, (t, b) in enumerate(slides))
    jump = "".join(f'<option value="{i}">{i + 1}. {esc(t)}</option>' for i, (t, _b) in enumerate(slides))
    js = r"""<script>(()=>{const ss=[...document.querySelectorAll('.slide')];let i=0;const ctr=document.getElementById('ctr');const jp=document.getElementById('jump');
const show=n=>{i=Math.max(0,Math.min(ss.length-1,n));if(!document.body.classList.contains('show-all'))ss.forEach((s,j)=>s.hidden=j!==i);
ctr.textContent=(i+1)+' / '+ss.length;jp.value=String(i);document.getElementById('prev').disabled=i===0;document.getElementById('next').disabled=i===ss.length-1;};
document.getElementById('prev').onclick=()=>show(i-1);document.getElementById('next').onclick=()=>show(i+1);
jp.onchange=()=>{show(+jp.value);if(document.body.classList.contains('show-all'))window.scrollTo(0,ss[i].getBoundingClientRect().top+scrollY-document.querySelector('.ctl').offsetHeight-8);};
document.getElementById('all').onclick=e=>{const all=document.body.classList.toggle('show-all');e.target.setAttribute('aria-pressed',String(all));
e.target.textContent=all?'한 장씩 보기':'모두 펼치기';ss.forEach((s,j)=>s.hidden=all?false:j!==i);};
document.addEventListener('keydown',e=>{if(e.target.closest&&e.target.closest('input,select,textarea'))return;
if(e.key==='ArrowRight'||e.key==='PageDown')show(i+1);if(e.key==='ArrowLeft'||e.key==='PageUp')show(i-1);});show(0);})();</script>"""
    body = f"""<h1 style="font-size:22px">{c["title"]} — 발표용</h1>
{tnav("type-c-slides.html")}
<div class="ctl"><button type="button" id="prev">← 이전</button><span id="ctr" aria-live="polite"></span><button type="button" id="next">다음 →</button>
<select id="jump" aria-label="장으로 바로 가기">{jump}</select>
<button type="button" id="all" aria-pressed="false">모두 펼치기</button><span class="src">키보드 ← → 로 넘깁니다</span></div>
<div class="deck">{html}</div>"""
    return shell("type-c-slides.html", "슬라이드형", "PlaceOS · Page·Posting 인계 · 표현 유형 C 슬라이드형", body, TYPE_CSS["C"], js)


# ───────── D 카드형
def render_d(c):
    def card(tag, big, one, why="", bigcls="", onecls=""):
        return (f'<div class="c"><div class="tag">{tag}</div><div class="big{(" " + bigcls) if bigcls else ""}">{big}</div>'
                f'<p class="one{(" " + onecls) if onecls else ""}">{one}</p>{f"<p class=why>{why}</p>" if why else ""}</div>')
    secs = [("d-sum", "요약"), ("d-ver", "검증"), ("d-dec", "결정"), ("d-ba", "전/후"), ("d-menu", "메뉴"), ("d-br", "브랜치"), ("d-src", "출처")]
    sumcard = '<div class="c sumcard"><div class="tag">한눈에</div><ul>' + "".join(f'<li><b>{x["tag"]}</b> {x["head"]}</li>' for x in c["core"]) + "</ul></div>"
    # r1 — 검증 카드: 판정(짧다)을 크게, 주장(길다)은 본문으로, 확인한 것은 작게
    n_cl = len(c["claims"])
    ver = "".join(card(f"검증 {i + 1}/{n_cl}", esc(v), esc(a), esc(b), k, "claim") for i, (a, b, v, k) in enumerate(c["claims"]))
    lev = "".join(card("지렛대", v, k, s) for k, v, s in c["levers"])
    dec = "".join(card(f'결정 {d["id"]} · {d["status"]}', esc(d["name"]), esc(d["change"]), f'전 {esc(d["before"])} → 후 {esc(d["after"])}') for d in c["decisions"])
    ba = "".join(card(f"전/후 · {k}", esc(n), f"지금 {esc(b)}", f"바뀐 뒤 {esc(a)}") for n, b, a, k in c["metrics"])
    # r2 — 메뉴 예시 카드: 세 가격대를 이어 쓴 문장 두 줄 → 가격대 3행 작은 표(숫자를 세로로 맞춰 비교)
    def mini(m):
        rows = "".join(f'<tr><th scope="row">{TN[tk]}</th><td class="num">{t["price"]:,.0f}</td><td class="num">{t["rate"]*100:.0f}%</td>'
                       f'<td class="num">{t["daily"]:,}</td><td class="num">{t["pm"]:.0f}</td><td class="num">{t["first"]:.0f}</td></tr>' for tk, t in m["tiers"].items())
        return ('<div class="minibox"><table class="mini"><thead><tr><th scope="col">가격대</th><th scope="col" class="num">객단가<br>원</th>'
                '<th scope="col" class="num">원가율</th><th scope="col" class="num">하루<br>개</th><th scope="col" class="num">주기 구매<br>만원/월</th>'
                f'<th scope="col" class="num">첫 주문<br>만원</th></tr></thead><tbody>{rows}</tbody></table></div>')
    menu = "".join(f'<div class="c"><div class="tag">메뉴 예시 · {m["label"]}</div><div class="big">하루 {m["tiers"]["value"]["daily"]:,}개(가성비)</div>{mini(m)}</div>'
                   for m in c["menu"])
    br = "".join(card("브랜치 · " + b, esc(a), esc(d)) for a, b, d in c["overlap"])
    body = f"""<div class="col">
<h1 style="font-size:23px">{c["title"]}</h1>
{tnav("type-d-cards.html")}
<nav class="chipbar" aria-label="구역">{"".join(f'<a href="#{i}">{t}</a>' for i, t in secs)}</nav>
<div id="d-sum">{sumcard}</div>
<p class="sec" id="d-ver">검증</p>{ver}{lev}
<p class="sec" id="d-dec">결정</p>{dec}
<p class="sec" id="d-ba">전/후</p>{ba}
<div class="c"><div class="tag">회수기간 분포</div>{scen_heat(c)}</div>
<div class="c"><div class="tag">요구치(P2)</div>{hist_heat(c)}<p class="one">추천 자리 {c["p2"]["share_over_avg"]}% 서울 평균 이상 · {c["p2"]["share_over_2x"]}% 2배 이상</p></div>
<div class="c"><div class="tag">Page 판정 분포</div>{usecheck_bars(c)}</div>
<p class="sec" id="d-menu">메뉴</p><div class="c"><div class="tag">메뉴 「예시 채우기」 v2</div><p class="one">{MENU_LINE}. <a href="{MENU_LINK}">직접 눌러 보기</a></p></div>{menu}
<p class="sec" id="d-br">브랜치</p><div class="c"><div class="tag">브랜치</div><p class="one">claude/twin-roads 는 main 보다 <b>31커밋</b> 뒤</p></div>{br}
<p class="sec" id="d-src">출처</p><div class="c">{sources_list(c)}</div>
</div>"""
    return shell("type-d-cards.html", "카드형", "PlaceOS · Page·Posting 인계 · 표현 유형 D 카드형", body, TYPE_CSS["D"])


# ───────── E 질문 흐름형
def render_e(c):
    d = {x["id"]: x for x in c["decisions"]}
    qs = [
        ("결론이 뭐예요?", core_list(c)),
        ("296이라는 숫자는 맞아요?", f'<p>맞습니다 — 서빙 코드를 다시 돌려도 <b>{c["base"]["lt1"]}곳</b>, 중앙 {c["base"]["median"]}개월입니다. 다만 분모 891 은 재현되지 않아 <b>296/836(35.4%)</b>로 인용해야 합니다(셀 수 있는 분모 854 · 836).</p>{claims_table(c)}'),
        ("왜 회수기간이 그렇게 짧게 나와요?", f'{levers_tiles(c)}<p>투자비만 고치면 「1개월 미만」은 {c["s545"]["lt1"]}곳까지 줄지만 중앙 {c["s545"]["median"]}개월 — 매출 추정이 그대로라서입니다.</p>{scen_heat(c)}'),
        ("결정은 어디까지 정해졌어요?", decisions_table(c)),
        ("투자비를 바꾸면 화면이 어떻게 달라져요?", f'<p>{esc(d["①"]["before"])}</p><p>→ {esc(d["①"]["after"])}</p>'),
        ("질문 문구는 어떻게 바뀌어요?", f'<p>{esc(d["②"]["change"])}</p><p>전 {esc(d["②"]["before"])} → 후 {esc(d["②"]["after"])}</p>'),
        ("인테리어 3D 는 어디로 가요?", f'<p>{esc(d["③-a"]["change"])}</p><p>{esc(d["③-a"]["after"])} · 상태: 보류</p>'),
        ("처리방침은 뭘 고쳐요?", f'<p>{esc(d["④"]["change"])}</p><p>{esc(d["④"]["after"])}</p>'),
        ("작업을 끝내면 뭐가 달라져요?", f'{metrics_table(c)}{hist_heat(c)}<p>추천 자리 {c["p2"]["share_over_avg"]}% 서울 평균 이상 · {c["p2"]["share_over_2x"]}% 2배 이상</p>{usecheck_bars(c)}'),
        ("메뉴 예시 채우기에는 뭐가 들어가요?", f'<p>{MENU_LINE}. <a href="{MENU_LINK}">직접 눌러 보기</a></p>{menu_table(c)}'),
        ("아직 배포 안 된 브랜치는 어떻게 해요?", overlap_table(c)),
        ("출처는요?", sources_list(c)),
    ]
    # r1 — 첫 질문(결론)의 답을 맨 위에 두고, 질문 목록은 그 아래 「다른 질문」으로 — 폰 첫 화면에 결론이 들어오게
    idx = "".join(f'<li><a href="#q{i}">{q}</a></li>' for i, (q, _a) in enumerate(qs) if i)
    item = lambda i, q, a: f'<details class="qa" id="q{i}"{" open" if i == 0 else ""}><summary>{q}</summary><div class="ans">{a}</div></details>'
    first = item(0, *qs[0])
    rest = "".join(item(i, q, a) for i, (q, a) in enumerate(qs) if i)
    js = r"""<script>document.querySelectorAll('.qindex a').forEach(a=>a.addEventListener('click',()=>{const d=document.querySelector(a.getAttribute('href'));if(d)d.open=true;}));</script>"""
    body = f"""<h1 style="font-size:24px">{c["title"]} — 질문으로 보기</h1>
{tnav("type-e-qa.html")}
{first}
<p class="qhead">다른 질문</p><ol class="qindex" start="2">{idx}</ol>{rest}"""
    return shell("type-e-qa.html", "질문 흐름형", "PlaceOS · Page·Posting 인계 · 표현 유형 E 질문 흐름형", body, TYPE_CSS["E"], js)


RENDER = {"A": render_a, "B": render_b, "C": render_c, "D": render_d, "E": render_e}

if __name__ == "__main__":
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    c = build()
    for fname, key, _n in TYPES:
        (out / fname).write_text(RENDER[key](c), encoding="utf-8")
        print("wrote", fname)
