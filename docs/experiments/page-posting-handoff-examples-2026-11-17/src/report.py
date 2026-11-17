"""라운드 점수 계산 · 기록 · 비교 보고서 — python3 src/report.py <라운드 이름> [라운드 메모 JSON]

점수(100) — 원값은 harness.cjs 가 잰다. 기준은 라운드 사이에 바꾸지 않는다(바꾸면 history 의 모든 라운드를 다시 계산한다).
  완전성 25   = 25 × 들어 있는 사실 / 25
  첫 화면 20  = 10 × 폰 첫 화면 핵심 / 5 + 10 × PC 첫 화면 핵심 / 5
  탐색 비용 15 = 15 × (이번 라운드 최소 비용 / 이 유형 비용) · 비용 = 폰 스크롤 화면 수 + 0.5 × 펼치거나 넘겨야 보이는 블록 수
  모바일 15   = 5 × 넘침 없음 + 5 × 글자 크기(12px 이상이면 1, 9px 이면 0) + 5 × 터치 대상 32px 이상 비율
  접근성 15   = 5 × 글자 대비(라이트) + 4 × 글자 대비(다크) + 3 × 이름 있는 조작 요소 + 3 × 대체 텍스트
  안정성 10   = 5 × 오류 없음 + 3 × 링크가 살아 있는 비율 + 2 × 크기(300KB 이하면 1)
"""
import base64
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
X = SRC.parent
sys.path.insert(0, str(SRC))
from gen_common import CSS, TIP_JS, esc  # noqa: E402
from types_render import TYPES  # noqa: E402

C = X / "out" / "compare"
NAMES = {k: n for _f, k, n in TYPES}
FILES = {k: f for f, k, _n in TYPES}
CRIT = [("complete", "완전성", 25), ("first", "첫 화면", 20), ("nav", "탐색 비용", 15), ("mobile", "모바일", 15), ("a11y", "접근성", 15), ("stable", "안정성", 10)]
SERIES = {"A": ("#2a78d6", "#3987e5"), "B": ("#eb6834", "#d95926"), "C": ("#1baf7a", "#199e70"), "D": ("#eda100", "#c98500"), "E": ("#e87ba4", "#d55181")}


def score(metrics):
    t = metrics["types"]
    cost = {k: v["mobile"]["screens"] + 0.5 * (v["mobile"]["closedDetails"] + v["mobile"]["hiddenBlocks"]) for k, v in t.items()}
    mn = min(cost.values())
    out = {}
    for k, v in t.items():
        d, m, md = v["desktop"], v["mobile"], v["mobileDark"]
        n_facts = len(d["factsFound"]) / 25
        s = {
            "complete": 25 * n_facts,
            "first": 10 * len(m["coreAbove"]) / 5 + 10 * len(d["coreAbove"]) / 5,
            "nav": 15 * mn / cost[k],
            "mobile": 5 * (m["overflow"] <= 0) + 5 * max(0, min(1, (m["minFont"] - 9) / 3)) + 5 * m["tap"],
            "a11y": 5 * m["contrast"] + 4 * md["contrast"] + 3 * m["names"] + 3 * m["alt"],
            "stable": 5 * (len(v["errors"]) == 0) + 3 * (d["anchors"] + v["fileLinks"]) / 2 + 2 * min(1, 300000 / max(1, v["bytes"])),
        }
        s["total"] = sum(s[c] for c, _n, _w in CRIT)
        s["cost"] = cost[k]
        out[k] = {kk: round(vv, 2) for kk, vv in s.items()}
    return out


def line_chart(hist):
    rounds = [h["round"] for h in hist]
    W, H, L, R, T, B = 760, 300, 46, 120, 16, 34
    lo = max(0, min(h["scores"][k]["total"] for h in hist for k in h["scores"]) - 10)
    lo = int(lo // 10 * 10); hi = 100
    xs = (lambda i: L + (W - L - R) * (i / max(1, len(rounds) - 1))) if len(rounds) > 1 else (lambda i: L + (W - L - R) / 2)
    ys = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    g = [f'<line x1="{L}" x2="{W - R}" y1="{ys(v):.1f}" y2="{ys(v):.1f}" stroke="var(--line)"/><text x="{L - 8}" y="{ys(v) + 4:.1f}" text-anchor="end" font-size="12" fill="var(--muted)">{v}</text>'
         for v in range(lo, hi + 1, 10)]
    g += [f'<text x="{xs(i):.1f}" y="{H - 10}" text-anchor="middle" font-size="12" fill="var(--muted)">{esc(r)}</text>' for i, r in enumerate(rounds)]
    for k in NAMES:
        pts = [(xs(i), ys(h["scores"][k]["total"]), h["scores"][k]["total"], h["round"]) for i, h in enumerate(hist) if k in h["scores"]]
        if len(pts) > 1:
            g.append(f'<polyline fill="none" stroke="var(--s{k})" stroke-width="2" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y, _v, _r in pts)}"/>')
        for x, y, v, r in pts:
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="var(--s{k})" stroke="var(--surface)" stroke-width="2" tabindex="0" data-tip="{k} {NAMES[k]} · {esc(r)}: {v:.1f}점"/>')
        x, y, v, _r = pts[-1]
        g.append(f'<text x="{x + 10:.1f}" y="{y + 4:.1f}" font-size="12.5" fill="var(--fg)">{k} {NAMES[k]} {v:.1f}</text>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="라운드별 총점 — 아래 표와 같은 값" style="width:100%;height:auto;max-width:{W}px">{"".join(g)}</svg>'


def strengths(s):
    rel = sorted(((s[c] / w, n) for c, n, w in CRIT), reverse=True)
    best = " · ".join(n for r, n in rel if r >= rel[0][0] - 1e-9) if rel[0][0] >= 0.999 else rel[0][1]
    return (best, "없음(모든 기준 만점)") if rel[-1][0] >= 0.999 else (best, rel[-1][1])


def render(hist):
    cur = hist[-1]; sc = cur["scores"]; met = cur["metrics"]["types"]
    order = sorted(sc, key=lambda k: -sc[k]["total"])
    css = ":root{" + "".join(f"--s{k}:{lt};" for k, (lt, _dk) in SERIES.items()) + "}" + \
          "@media (prefers-color-scheme: dark){:root:not([data-theme=\"light\"]){" + "".join(f"--s{k}:{dk};" for k, (_lt, dk) in SERIES.items()) + "}}" + \
          ":root[data-theme=\"dark\"]{" + "".join(f"--s{k}:{dk};" for k, (_lt, dk) in SERIES.items()) + "}" + \
          ".shot{width:100%;max-width:220px;border:1px solid var(--line);border-radius:10px} .tcard{display:grid;grid-template-columns:200px minmax(0,1fr);gap:14px}" + \
          "@media (max-width:640px){.tcard{grid-template-columns:1fr}} .sw{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}"
    head = "".join(f'<th scope="col" class="num">{n}<br><span class="src">/{w}</span></th>' for _c, n, w in CRIT)
    rank = "".join(f'<tr><th scope="row"><span class="sw" style="background:var(--s{k})"></span>{i + 1}위 · {k} {NAMES[k]}</th><td class="num"><b>{sc[k]["total"]:.1f}</b></td>'
                   + "".join(f'<td class="num">{sc[k][c]:.1f}</td>' for c, _n, _w in CRIT) + "</tr>" for i, k in enumerate(order))
    hist_head = "".join(f'<th scope="col" class="num">{k} {NAMES[k]}</th>' for k in NAMES)
    hist_rows = "".join(f'<tr><th scope="row">{esc(h["round"])}<br><span class="src">{esc(h["at"][:16].replace("T", " "))} UTC</span></th>'
                        + "".join(f'<td class="num">{h["scores"][k]["total"]:.1f}</td>' for k in NAMES) + "</tr>" for h in hist)
    cards = []
    for k in order:
        m = met[k]; best, worst = strengths(sc[k])
        shot = C / "shots" / f"{k}-m.jpg"
        src = "data:image/jpeg;base64," + base64.b64encode(shot.read_bytes()).decode() if shot.exists() else f"shots/{k}-m.jpg"
        cards.append(f"""<div class="card tcard"><img class="shot" src="{src}" alt="{k} {NAMES[k]} 폰 첫 화면"><div>
<h3 style="margin-top:0"><span class="sw" style="background:var(--s{k})"></span>{k} {NAMES[k]} — {sc[k]["total"]:.1f}점</h3>
<p class="src">사실 {len(m["desktop"]["factsFound"])}/25 · 첫 화면 핵심 폰 {len(m["mobile"]["coreAbove"])}/5 · PC {len(m["desktop"]["coreAbove"])}/5 · 폰 {m["mobile"]["screens"]:.1f}화면 ·
펼치거나 넘겨야 보이는 블록 {m["mobile"]["closedDetails"] + m["mobile"]["hiddenBlocks"]} · 최소 글자 {m["mobile"]["minFont"]:.1f}px · 터치 대상 {m["mobile"]["tap"] * 100:.0f}% ·
대비 {m["mobile"]["contrast"] * 100:.0f}%/{m["mobileDark"]["contrast"] * 100:.0f}%(라이트/다크) · 오류 {len(m["errors"])} · {m["bytes"] / 1000:.0f}KB</p>
<p><b>강점</b> {best} · <b>약점</b> {worst}</p>
<p><b>검토 메모</b> {esc(cur.get("notes", {}).get(k, "—"))}</p>
<p><b>이번 라운드 개선</b> {esc(cur.get("changes", {}).get(k, "—"))}</p>
<p><a href="../types/{FILES[k]}">이 유형 열기</a></p></div></div>""")
    pick = {
        "빨리 파악(첫 화면 + 탐색 비용)": max(sc, key=lambda k: sc[k]["first"] + sc[k]["nav"]),
        "빠짐없이 근거까지(완전성 + 접근성 + 안정성)": max(sc, key=lambda k: sc[k]["complete"] + sc[k]["a11y"] + sc[k]["stable"]),
        "휴대폰으로(모바일 + 첫 화면)": max(sc, key=lambda k: sc[k]["mobile"] + sc[k]["first"]),
    }
    picks = "".join(f'<tr><th scope="row">{u}</th><td>{k} {NAMES[k]}</td></tr>' for u, k in pick.items())
    picks += '<tr><th scope="row">회의 발표</th><td>C 슬라이드형(형식상 — 점수와 별개)</td></tr>'
    state = cur.get("state", "")
    body = f"""<h1>표현 유형 비교 — {esc(cur["round"])}</h1>
<p class="lede">같은 내용(검증 · 결정 ①~④ · 전/후 · 메뉴 예시)을 다섯 가지 방식으로 그리고, 같은 자동 검증으로 점수를 매겼습니다. 매시간 유형마다 한 번씩 고치고 다시 잽니다.</p>
<div class="meta">{"".join(f'<span class="chip info">{k} {NAMES[k]}</span>' for k in NAMES)}<span>{esc(state)}</span></div>
<nav class="files" aria-label="유형 열기">{"".join(f'<a href="../types/{FILES[k]}">{k} · {NAMES[k]}</a>' for k in NAMES)}<a href="../set/placeos-00-verify.html">원본 7개 묶음</a></nav>
<div class="callout ok"><p><b>지금 1위: {order[0]} {NAMES[order[0]]}</b>({sc[order[0]]["total"]:.1f}점) · 2위 {order[1]} {NAMES[order[1]]}({sc[order[1]]["total"]:.1f}점).
점수는 자동 검증만으로 냈습니다 — 실제 독자 반응이 아니라, 같은 기준으로 잰 비교입니다.</p></div>
<h2>1. 이번 라운드 순위</h2>
<div class="tbl"><table><thead><tr><th scope="col">유형</th><th scope="col" class="num">총점</th>{head}</tr></thead><tbody>{rank}</tbody></table></div>
<h2>2. 라운드별 총점</h2>
<div class="legend" aria-hidden="true">{"".join(f'<span><i style="background:var(--s{k})"></i>{k} {NAMES[k]}</span>' for k in NAMES)}</div>
<div class="card">{line_chart(hist)}</div>
<div class="tbl"><table><caption>표로 보기 — 라운드별 총점</caption><thead><tr><th scope="col">라운드</th>{hist_head}</tr></thead><tbody>{hist_rows}</tbody></table></div>
<h2>3. 유형별 — 폰 첫 화면 · 강점 · 약점 · 이번 개선</h2>{"".join(cards)}
<h2>4. 용도별로 고르면</h2>
<div class="tbl"><table><thead><tr><th scope="col">용도</th><th scope="col">유형</th></tr></thead><tbody>{picks}</tbody></table></div>
<h2>5. 어떻게 쟀나</h2>
<ul>
<li><b>완전성 25</b> — 꼭 들어가야 할 사실 25개(296 · 836 · 35.4% · 14,517 · 7,472 · ③-a · 보류 · 48.8% · 주기 구매 · 개업 첫 주문 …)가 글자 그대로 있는가</li>
<li><b>첫 화면 20</b> — 폰(390×844)·PC(1280×800) 첫 화면에 핵심 5가지(「모두 사실」 · 296 · ③-a · 요구치 · 48.8%)가 그려졌는가</li>
<li><b>탐색 비용 15</b> — 폰에서 끝까지 보는 데 드는 스크롤 화면 수 + 펼치거나 넘겨야 보이는 블록 × 0.5. 이번 라운드 가장 싼 유형이 만점</li>
<li><b>모바일 15</b> — 가로 넘침 · 가장 작은 글자 · 터치 대상(32px 이상)</li>
<li><b>접근성 15</b> — 글자 대비(라이트·다크, WCAG 4.5:1 · 큰 글자 3:1) · 조작 요소 이름 · 그림 대체 텍스트</li>
<li><b>안정성 10</b> — 콘솔 오류 · 깨진 링크 · 파일 크기</li>
</ul>
<p class="src">원값: <code>out/compare/metrics-&lt;라운드&gt;.json</code> · 기록: <code>out/compare/history.json</code> · 다시 재기: <code>python3 src/build.py && node src/harness.cjs . &lt;라운드&gt; && python3 src/report.py &lt;라운드&gt;</code></p>
"""
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>표현 유형 비교</title><style>{CSS}{css}</style></head><body><div class="wrap">
<p class="eyebrow">PlaceOS · Page·Posting 인계 예시 · 표현 유형 비교</p>{body}
<footer>자동 검증 점수 · 기준은 라운드 사이에 바꾸지 않습니다. 숫자 내용의 기준: main 79890bc3 · 2026-11-17.</footer></div>
<script>{TIP_JS}</script></body></html>"""


if __name__ == "__main__":
    rnd = sys.argv[1]
    notes = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else {}
    metrics = json.loads((C / f"metrics-{rnd}.json").read_text())
    hp = C / "history.json"
    hist = json.loads(hp.read_text()) if hp.exists() else []
    hist = [h for h in hist if h["round"] != rnd]
    hist.append({"round": rnd, "at": metrics["at"], "scores": score(metrics), "metrics": metrics,
                 "changes": notes.get("changes", {}), "notes": notes.get("notes", {}), "state": notes.get("state", "")})
    hp.write_text(json.dumps(hist, ensure_ascii=False, indent=1))
    (C / "compare.html").write_text(render(hist), encoding="utf-8")
    for k, v in sorted(hist[-1]["scores"].items(), key=lambda kv: -kv[1]["total"]):
        print(k, NAMES[k], v["total"], {c: v[c] for c, _n, _w in CRIT})
