"""06 메뉴 「예시 채우기」 v2 — 주기별로 사는 것(발주 계획 · 위생·청소·설비 유지·서비스)과 개업 첫 주문을 더했다(2026-11-17)."""
import json
import sys
from pathlib import Path

import menu_data as MD
import menu_plan as MP
from gen_common import chip, page

OUT = Path(sys.argv[1])

PER = {i["key"]: {tk: MP.periodic_items(i, tk) for tk in ("premium", "value", "factory")} for i in MD.INDUSTRIES}
DATA = {
    "ING": MD.ING, "IND": MD.INDUSTRIES, "SRC": MD.SRC, "TN": MD.TIER_NAMES, "WAGE": MD.WAGE, "RENT": MD.DEFAULT_RENT,
    "BENCH": MD.FOOD_COST_BENCH, "INVEST_NOW": 1130, "FOOD_AVG": 9610, "INT_AVG": 5450,
    "ORDER": MP.ORDER, "CYL": MP.CYCLE_LABEL, "PER": PER, "UTIL": MP.UTIL,
}

STYLE = """<style>
.ctl{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:flex-end;margin:10px 0}
.ctl label{display:grid;gap:4px;font-size:13.5px;color:var(--muted)}
.ctl select,.ctl input,.grid-in input,.inl{font:inherit;font-size:15px;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--fg)}
.seg{display:inline-flex;flex-wrap:wrap;max-width:100%;border:1px solid var(--line);border-radius:999px;overflow:hidden}
.seg button{font:inherit;font-size:14px;padding:6px 12px;border:0;background:var(--surface);color:var(--fg);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--accent);color:#fff}
.btn{font:inherit;font-size:15px;font-weight:600;padding:8px 14px;border-radius:10px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
.btn.ghost{background:var(--surface);color:var(--accent)}
.btn.small{font-size:13.5px;padding:4px 10px;font-weight:500;white-space:nowrap}
.mt input{width:100%;min-width:64px;max-width:100%;font:inherit;font-size:14.5px;padding:5px 7px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--fg)}
.mt thead th{white-space:nowrap}
.mt td{vertical-align:middle}
.mt .x{border:0;background:none;color:var(--muted);font-size:18px;cursor:pointer}
.items{background:var(--mock-bg)} .items table{font-size:14px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.filters button{font:inherit;font-size:13.5px;padding:3px 10px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--fg);cursor:pointer}
.filters button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent);font-weight:600}
.grid-in{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.grid-in label{display:grid;gap:4px;font-size:13.5px;color:var(--muted)} .grid-in input{width:100%;min-width:0}
.ctl label,.ctl select{max-width:100%;min-width:0}
.big{font-size:22px;font-weight:700} .hint{font-size:13.5px;color:var(--muted)}
.badge-ex{font-size:12px;font-weight:600;color:var(--decide);background:var(--decide-bg);border-radius:999px;padding:1px 8px;margin-left:6px;white-space:nowrap}
.badge-me{font-size:12px;font-weight:600;color:var(--ok);background:var(--ok-bg);border-radius:999px;padding:1px 8px;margin-left:6px;white-space:nowrap}
.cyc{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:8px 0}
.cyc .card h4{margin:0 0 6px} .cyc ul{margin:0;padding-left:18px;font-size:14px}
.sub{font-size:16px;margin:18px 0 6px}
.nw{white-space:nowrap}
</style>"""

BODY = f"""
<div class="callout"><p><b>원칙</b> — 사이트의 메뉴 설정은 일부러 기본값을 넣지 않습니다(<code>lib/menuPlan.ts</code>). 그래서 예시는 <b>「예시 채우기」를 누를 때만</b> 들어가고,
줄마다 「예시」 표식과 출처가 붙고, 고치면 「직접 입력」으로 바뀝니다. 예시 값은 계산 결과 저장·KPI 에 쓰지 않습니다.</p></div>

<div class="card">
<div class="ctl">
<label>업종<select id="ind" aria-label="업종"></select></label>
<div><div class="hint" style="margin-bottom:4px">가격대</div><div class="seg" id="tier" role="group" aria-label="가격대"></div></div>
<div><div class="hint" style="margin-bottom:4px">채우기 방식</div><div class="seg" id="mode" role="group" aria-label="채우기 방식">
<button type="button" data-mode="recipe" aria-pressed="true">① 레시피 원가</button><button type="button" data-mode="rate" aria-pressed="false">② 업종 평균 원가율</button><button type="button" data-mode="blank" aria-pressed="false">③ 빈 표(직접)</button></div></div>
<button type="button" class="btn" id="fill">예시 채우기</button><button type="button" class="btn ghost" id="clear">비우기</button>
</div>
<p class="hint" id="concept"></p>
<p class="hint">① 재료마다 수량 × 단가로 원가를 쌓습니다(발주 계획까지 계산) · ② 판매가 × 외식업 평균 식재료비 비중 40.7%(농식품부 2025 조사)로 빠르게 잡습니다 · ③ 빈 표에서 직접 씁니다.</p>
</div>

<h2>1. 메뉴 — 판매가 · 판매 비중 · 원가</h2>
<div class="filters" id="itemFilter" role="group" aria-label="원가 항목 분류"></div>
<div class="tbl mt"><table><caption>메뉴 1개 = 판매 1건. 「항목」을 누르면 원가를 이루는 재료·포장·수수료가 보이고, 수량과 단가를 고칠 수 있습니다.</caption>
<thead><tr><th scope="col">메뉴</th><th scope="col" class="num">판매가(원)</th><th scope="col" class="num">판매 비중(%)</th><th scope="col" class="num">원가(원)</th><th scope="col" class="num">원가율</th><th scope="col">근거</th><th scope="col"><span class="hint">항목</span></th><th scope="col"><span class="hint">지우기</span></th></tr></thead>
<tbody id="rows"></tbody></table></div>
<button type="button" class="btn ghost small" id="add">+ 메뉴 더하기</button>
<div class="tiles" id="mixTiles" style="margin-top:14px"></div>

<h2>2. 준비물 ① — 한 번 사는 것</h2>
<p class="hint">식기 · 조리도구·주방 설비 · 매장 설비. 매달 나가는 돈이 아니라 초기 투자(회수기간의 분자)에 들어갑니다.</p>
<div class="filters" id="setupFilter" role="group" aria-label="한 번 사는 것 분류"></div>
<div class="tbl mt"><table><thead><tr><th scope="col">분류</th><th scope="col">이름</th><th scope="col" class="num">수량</th><th scope="col" class="num">단가(원)</th><th scope="col" class="num">금액(원)</th></tr></thead>
<tbody id="setup"></tbody></table></div>

<h2>3. 준비물 ② — 주기별로 사는 것</h2>
<h3 class="sub">3-1. 식재료 · 포장 발주 계획 <span class="chip mute">원가율에 이미 들어 있는 돈</span></h3>
<div class="ctl"><label>계획 판매량(하루, 개)<input id="plan-daily" class="inl" inputmode="numeric" placeholder="비우면 4번의 본전 판매량"></label>
<div class="seg" id="orderView" role="group" aria-label="발주 계획 보기"><button type="button" data-oview="table" aria-pressed="true">표로 보기</button><button type="button" data-oview="cycle" aria-pressed="false">주기별 묶음</button></div></div>
<div class="filters" id="orderFilter" role="group" aria-label="발주 품목 분류"></div>
<div id="order"></div>
<h3 class="sub">3-2. 위생·청소 · 주방 소모품 · 설비 유지 · 서비스 <span class="chip info">기타 월 고정비에 더함</span></h3>
<div class="filters" id="perFilter" role="group" aria-label="주기 구매 분류"></div>
<div class="tbl mt"><table><thead><tr><th scope="col">분류</th><th scope="col">이름</th><th scope="col">주기</th><th scope="col">1회</th><th scope="col" class="num">1회 금액(원)</th><th scope="col" class="num">월 환산(원)</th><th scope="col">개업 전 구입</th></tr></thead>
<tbody id="periodic"></tbody></table></div>
<div class="tiles" id="openTiles"></div>

<h2>4. 이 메뉴로 「하루 몇 개 팔아야 하나」(P2 미리보기)</h2>
<div class="card"><div class="grid-in">
<label>월세(만원)<input id="rq-rent" inputmode="numeric"></label>
<label>인원(명)<input id="rq-staff" inputmode="numeric"></label>
<label>1인 주당 근무시간<input id="rq-hours" inputmode="numeric"></label>
<label>시급(원)<input id="rq-wage" inputmode="numeric"></label>
<label>공과금 — 전기·가스·수도(만원)<input id="rq-util" inputmode="numeric"></label>
<label>그 밖의 월 고정비(만원)<input id="rq-etc" inputmode="numeric"></label>
<label>월 영업일<input id="rq-days" inputmode="numeric"></label>
</div>
<p class="hint" id="perLine"></p>
<div id="reqOut" style="margin-top:12px" aria-live="polite"></div>
<p class="hint">월세 기본값 {MD.DEFAULT_RENT}만원은 지금 서빙 중인 추천 자리 836곳의 월세 중앙(R-ONE 추정)입니다 — 고른 자리의 들은 월세로 바꾸세요.
시급은 2026년 최저임금, 월 유급시간은 주휴 포함 반올림(주 40시간 = 209시간). 사업주 부담 4대보험·퇴직금과 카드 외 결제 수수료는 넣지 않았습니다.</p></div>

<h2>5. 같은 업종, 세 가격대 나란히</h2>
<div class="tbl"><table id="tierCmp"></table></div>

<h2>6. 전체 예시 — 업종 6 × 가격대 3</h2>
<div id="allEx"></div>

<h2>7. 단가표 · 발주 단위 · 출처</h2>
<div class="tbl"><table id="ingTbl"></table></div>

<h2>8. 화면에 넣는다면</h2>
<ul>
<li>자리: Posting 「메뉴 설정」의 「+ 메뉴 더하기」 옆에 「예시 채우기」. 발주 계획과 주기 구매는 메뉴 표 아래 「펼치기」 두 칸으로.</li>
<li>데이터: <code>data/config/menu_examples.json</code> — 단가·발주 단위·보관·주기마다 출처와 기준일. 출처 없는 값은 <code>"basis": "example"</code>.</li>
<li>연결: 주기 구매 월 환산액 → 「기타 월 고정비」, 개업 첫 주문 + 한 번 사는 것 → 「초기 투자」(결정 ① · 견적 입력 P3 와 같은 칸).</li>
<li>테스트: ① 누르기 전엔 빈 표 ② 업종·가격대별 줄 수·합계 ③ 발주 = 하루 사용량 × 주기를 구매 단위로 올림 ④ 예시 값은 KPI·저장 집계에 들어가지 않음.</li>
</ul>
"""

JS = r"""
const D = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = v => Number.isFinite(v) ? Math.round(v).toLocaleString('ko-KR') : '—';
const man = v => Number.isFinite(v) ? (Math.round(v * 10) / 10).toLocaleString('ko-KR') + '만원' : '—';
const pctT = v => Number.isFinite(v) ? (v * 100).toFixed(1) + '%' : '—';
const num = s => { if (s === '' || s == null) return NaN; const n = Number(String(s).replace(/,/g, '')); return Number.isFinite(n) ? n : NaN; };
const SRCL = {kamis:'KAMIS', chamga:'참가격', chicken:'보도 가격대', mafra:'농식품부', card:'우대수수료', wage:'최저임금', guess:'예시(가정)'};
const srcChip = k => k ? `<span class="chip ${k === 'guess' ? 'mute' : 'info'}" tabindex="0" data-tip="${esc(D.SRC[k])}">${SRCL[k]}</span>` : '';
const CATS = ['식재료', '포장·일회용품', '기타 변동비'];
const SCATS = ['식기', '조리도구·주방 설비', '매장 설비'];
const PCATS = ['위생·청소', '주방 소모품', '설비 유지', '서비스·기타'];
const MAXROWS = 8;
const cyl = d => D.CYL[d] || `${d}일마다`;
const blank = () => ({name:'', price:'', share:'', kind:'manual', manual:'', items:[], pct:[], src:null, ex:false});
let st = {ind: D.IND[0].key, tier: 'value', mode: 'recipe', rows: [blank(), blank(), blank()], setup: [], periodic: [], filled: false,
          itemFilter: '전체', setupFilter: '전체', perFilter: '전체', orderFilter: '전체', oview: 'table', open: new Set()};
const ind = () => D.IND.find(i => i.key === st.ind);
const paidHours = h => Math.round((h + (h >= 15 ? h / 40 * 8 : 0)) * 365 / 7 / 12);

function exampleRows(indKey, tier, mode) {
  const t = D.IND.find(i => i.key === indKey).tiers[tier];
  return t.menus.map(m => {
    const base = {name: m.name, price: String(m.price), share: String(m.share), src: m.price_src, ex: true, manual: ''};
    if (mode === 'rate') return {...base, kind: 'rate', items: [], pct: [{name: '카드수수료(영세·신용 0.40%)', rate: 0.004, src: 'card'}]};
    return {...base, kind: 'items',
      items: m.lines.map(([k, q]) => { const g = D.ING[k]; return {key: k, cat: g[5], name: g[0], qty: q, unit: g[3], up: g[4], src: g[6]}; }),
      pct: m.pct.map(([n, r, s]) => ({name: n, rate: r, src: s}))};
  });
}
function rowCost(r) {
  const price = num(r.price);
  if (r.kind === 'manual') return {total: num(r.manual), by: null};
  const by = {'식재료': 0, '포장·일회용품': 0, '기타 변동비': 0};
  if (r.kind === 'rate') by['식재료'] = (price || 0) * D.BENCH;
  r.items.forEach(it => { by[it.cat] += (Number(it.qty) || 0) * (Number(it.up) || 0); });
  r.pct.forEach(p => { by['기타 변동비'] += (price || 0) * p.rate; });
  return {total: by['식재료'] + by['포장·일회용품'] + by['기타 변동비'], by};
}
// main 의 menuMix 와 같은 규칙 — 판매가 > 0 · 0 ≤ 원가 < 판매가 인 줄만, 비중은 모두 > 0 일 때만 가중
function mixOf(rows) {
  const used = rows.map(r => ({price: num(r.price), share: num(r.share), cost: rowCost(r).total}))
    .filter(r => r.price > 0 && Number.isFinite(r.cost) && r.cost >= 0 && r.cost < r.price);
  if (!used.length) return null;
  const weighted = used.every(r => r.share > 0);
  const w = used.map(r => weighted ? r.share : 1), tot = w.reduce((a, b) => a + b, 0);
  const avgP = used.reduce((t, r, i) => t + r.price * w[i], 0) / tot, avgC = used.reduce((t, r, i) => t + r.cost * w[i], 0) / tot;
  return {n: used.length, avgP, avgC, rate: avgC / avgP, weighted};
}
const perMonth = list => list.reduce((t, p) => t + (Number(p.amount) || 0) * 30 / p.cycle, 0);
function reqOf(m, v, pm) {
  if (!m || Object.values(v).some(x => !Number.isFinite(x)) || v.days < 1 || v.days > 31 || m.rate >= 1) return null;
  const labor = v.staff * paidHours(v.hours) * v.wage / 10000;
  const fixed = v.rent + labor + v.util + pm / 10000 + v.etc, bep = fixed / (1 - m.rate);
  return {labor, fixed, bep, daily: Math.ceil(bep * 10000 / m.avgP / v.days - 1e-9)};
}
function reqInputs() {
  return {rent: num($('#rq-rent').value), staff: num($('#rq-staff').value), hours: num($('#rq-hours').value), wage: num($('#rq-wage').value),
          util: num($('#rq-util').value), etc: num($('#rq-etc').value), days: num($('#rq-days').value)};
}
// 발주 계획 — 레시피 줄(kind=items)만. 하루 사용량 × 주기를 구매 단위로 올린다(menu_plan.order_plan 과 같은 식)
function orderPlanOf(rows, daily, days) {
  const used = rows.filter(r => r.kind === 'items' && num(r.price) > 0);
  const tot = used.reduce((t, r) => t + (num(r.share) > 0 ? num(r.share) : 0), 0);
  if (!used.length || !(tot > 0) || !(daily > 0)) return null;
  const use = {};
  used.forEach(r => { const cnt = daily * (num(r.share) > 0 ? num(r.share) : 0) / tot;
    r.items.forEach(it => { if (!it.key) return; const u = use[it.key] || (use[it.key] = {q: 0, cost: 0, it});
      u.q += cnt * (Number(it.qty) || 0); u.cost += cnt * (Number(it.qty) || 0) * (Number(it.up) || 0); }); });
  const out = [];
  Object.entries(use).forEach(([k, u]) => { const od = D.ORDER[k]; if (!od || u.q <= 0) return;
    const [pack, label, storage, cycle] = od, up = u.cost / u.q, packs = Math.max(1, Math.ceil(u.q * cycle / pack - 1e-9));
    out.push({key: k, name: u.it.name, cat: u.it.cat, storage, cycle, packs, label, order: packs * pack * up, month: u.cost * days, src: u.it.src}); });
  return out.sort((a, b) => a.cycle - b.cycle || a.cat.localeCompare(b.cat, 'ko') || a.name.localeCompare(b.name, 'ko'));
}
const setupTotal = list => list.reduce((t, s) => t + (Number(s.qty) || 0) * (Number(s.up) || 0), 0);
const openingSupplies = list => list.filter(p => p.opening).reduce((t, p) => t + (Number(p.amount) || 0), 0);

// 예시 데이터만으로 낸 요약(세 가격대 비교 · 전체 예시) — menu_plan.tier_summary 와 같은 결과
function summaryOf(indKey, tier, rent) {
  const i = D.IND.find(x => x.key === indKey), t = i.tiers[tier], rows = exampleRows(indKey, tier, 'recipe'), m = mixOf(rows);
  const per = D.PER[indKey][tier], pm = perMonth(per);
  const r = reqOf(m, {rent, staff: t.staff, hours: 40, wage: D.WAGE, util: D.UTIL[indKey], etc: 0, days: i.days}, pm);
  const plan = orderPlanOf(rows, r.daily, i.days) || [];
  const first = plan.reduce((a, p) => a + p.order, 0) + openingSupplies(per);
  const setup = setupTotal(t.setup.map(([n, c, q, p]) => ({qty: q, up: p})));
  return {t, m, r, pm, first, setup, pre: setup + first};
}

function fill() {
  const i = ind(), t = i.tiers[st.tier];
  if (st.mode === 'blank') { st.rows = [blank(), blank(), blank()]; st.setup = []; st.periodic = []; st.filled = false; render(); return; }
  st.rows = exampleRows(st.ind, st.tier, st.mode);
  st.setup = t.setup.map(([n, c, q, p]) => ({name: n, cat: c, qty: q, up: p, ex: true}));
  st.periodic = D.PER[st.ind][st.tier].map(p => ({...p}));
  st.filled = true; st.open = new Set();
  $('#rq-staff').value = t.staff; $('#rq-util').value = D.UTIL[st.ind]; $('#rq-days').value = i.days; $('#rq-etc').value = 0;
  if ($('#rq-rent').value === '') $('#rq-rent').value = D.RENT;
  render();
}

function renderRows() {
  const out = [];
  st.rows.forEach((r, i) => {
    const c = rowCost(r), price = num(r.price), rate = price > 0 ? c.total / price : NaN;
    const badge = r.ex ? '<span class="badge-ex">예시</span>' : (r.name || r.price ? '<span class="badge-me">직접 입력</span>' : '');
    const costCell = r.kind === 'manual'
      ? `<input id="m-${i}-manual" data-f="manual" data-r="${i}" inputmode="numeric" value="${esc(r.manual)}" aria-label="메뉴 ${i + 1} 원가" placeholder="원">`
      : `<b>${fmt(c.total)}</b>`;
    const open = st.open.has(i);
    out.push(`<tr><td><input id="m-${i}-name" data-f="name" data-r="${i}" value="${esc(r.name)}" aria-label="메뉴 ${i + 1} 이름" placeholder="메뉴 ${i + 1}">${badge}</td>
<td class="num"><input id="m-${i}-price" data-f="price" data-r="${i}" inputmode="numeric" value="${esc(r.price)}" aria-label="메뉴 ${i + 1} 판매가" placeholder="원"></td>
<td class="num"><input id="m-${i}-share" data-f="share" data-r="${i}" inputmode="numeric" value="${esc(r.share)}" aria-label="메뉴 ${i + 1} 판매 비중" placeholder="%"></td>
<td class="num">${costCell}</td><td class="num">${pctT(rate)}</td><td>${srcChip(r.src)}</td>
<td>${r.kind === 'manual' ? '' : `<button type="button" class="btn ghost small" data-act="open" data-r="${i}" aria-expanded="${open}">${open ? '접기' : '항목'}</button>`}</td>
<td>${st.rows.length > 1 ? `<button type="button" class="x" data-act="del" data-r="${i}" aria-label="메뉴 ${i + 1} 지우기">×</button>` : ''}</td></tr>`);
    if (open && r.kind !== 'manual') out.push(`<tr class="items"><td colspan="8">${renderItems(r, i, c)}</td></tr>`);
  });
  $('#rows').innerHTML = out.join('');
}
function renderItems(r, i, c) {
  const f = st.itemFilter, lines = [];
  if (r.kind === 'rate' && (f === '전체' || f === '식재료'))
    lines.push(`<tr><td>식재료</td><td>재료 전체(판매가 × 외식업 평균 식재료비 비중 40.7%)</td><td class="num">—</td><td class="num">—</td><td class="num">${fmt(c.by['식재료'])}</td><td>${srcChip('mafra')}</td></tr>`);
  r.items.forEach((it, j) => { if (f !== '전체' && f !== it.cat) return;
    lines.push(`<tr><td>${it.cat}</td><td>${esc(it.name)}</td>
<td class="num"><input id="i-${i}-${j}-qty" data-f="qty" data-r="${i}" data-i="${j}" inputmode="decimal" value="${it.qty}" aria-label="${esc(it.name)} 수량" style="max-width:84px"> <span class="hint">${esc(it.unit)}</span></td>
<td class="num"><input id="i-${i}-${j}-up" data-f="up" data-r="${i}" data-i="${j}" inputmode="decimal" value="${it.up}" aria-label="${esc(it.name)} 단가" style="max-width:96px"> <span class="hint">원/${esc(it.unit)}</span></td>
<td class="num">${fmt((Number(it.qty) || 0) * (Number(it.up) || 0))}</td><td>${srcChip(it.src)}</td></tr>`); });
  r.pct.forEach(p => { if (f !== '전체' && f !== '기타 변동비') return;
    lines.push(`<tr><td>기타 변동비</td><td>${esc(p.name)}</td><td class="num">판매가의 ${(p.rate * 100).toFixed(2)}%</td><td class="num">—</td><td class="num">${fmt((num(r.price) || 0) * p.rate)}</td><td>${srcChip(p.src)}</td></tr>`); });
  const by = c.by ? CATS.map(k => `${k} ${fmt(c.by[k])}원`).join(' · ') : '';
  return `<table><caption>${esc(r.name || '메뉴 ' + (i + 1))} 원가 구성 — ${by}</caption><thead><tr><th scope="col">분류</th><th scope="col">항목</th><th scope="col" class="num">수량</th><th scope="col" class="num">단가</th><th scope="col" class="num">금액(원)</th><th scope="col">근거</th></tr></thead><tbody>${lines.join('') || '<tr><td colspan="6" class="hint">이 분류의 항목이 없습니다</td></tr>'}</tbody></table>`;
}
const chips = (id, list, cur, attr) => { $(id).innerHTML = ['전체', ...list].map(k => `<button type="button" ${attr}="${k}" aria-pressed="${cur === k}">${k}</button>`).join(''); };
function renderSetup() {
  const f = st.setupFilter;
  const rows = st.setup.map((s, j) => (f !== '전체' && f !== s.cat) ? '' :
    `<tr><td>${s.cat}</td><td>${esc(s.name)}<span class="badge-ex">예시</span></td>
<td class="num"><input id="s-${j}-qty" data-f="sqty" data-s="${j}" inputmode="numeric" value="${s.qty}" aria-label="${esc(s.name)} 수량" style="max-width:76px"></td>
<td class="num"><input id="s-${j}-up" data-f="sup" data-s="${j}" inputmode="numeric" value="${s.up}" aria-label="${esc(s.name)} 단가" style="max-width:120px"></td>
<td class="num">${fmt((Number(s.qty) || 0) * (Number(s.up) || 0))}</td></tr>`).join('');
  const byCat = SCATS.map(k => `${k} ${fmt(setupTotal(st.setup.filter(s => s.cat === k)) / 10000)}만원`).join(' · ');
  $('#setup').innerHTML = rows ? rows + `<tr><th scope="row" colspan="4">합계 (${byCat})</th><td class="num"><b>${fmt(setupTotal(st.setup))}</b></td></tr>`
    : '<tr><td colspan="5" class="hint">「예시 채우기」를 누르면 업종·가격대별 준비물이 채워집니다</td></tr>';
}
function renderOrder(plan, D0) {
  if (!st.filled || st.mode === 'blank') { $('#order').innerHTML = '<p class="hint">「예시 채우기」(① 레시피 원가)를 누르면 레시피와 판매량으로 발주 계획을 냅니다.</p>'; return; }
  if (!plan) { $('#order').innerHTML = st.mode === 'rate' ? '<p class="hint">② 업종 평균 원가율 방식은 재료 목록이 없어 발주 계획을 내지 않습니다 — ① 레시피 원가로 채우세요.</p>'
    : '<p class="hint">판매 비중과 4번 입력을 채우면 하루 판매량으로 발주 계획을 냅니다.</p>'; return; }
  const f = st.orderFilter, list = plan.filter(p => f === '전체' || p.cat === f);
  const month = plan.reduce((a, p) => a + p.month, 0), first = plan.reduce((a, p) => a + p.order, 0);
  const head = `<p class="hint">하루 <b>${D0.toLocaleString('ko-KR')}개</b> 판다고 보고 계산 · 식재료·포장 월 사용액 <b>${fmt(month)}원</b>(원가율에 이미 들어 있어 고정비에 더하지 않음) · 한 주기분(개업 첫 주문) <b>${fmt(first)}원</b></p>`;
  if (st.oview === 'cycle') {
    const groups = {};
    list.forEach(p => (groups[p.cycle] = groups[p.cycle] || []).push(p));
    $('#order').innerHTML = head + '<div class="cyc">' + Object.keys(groups).sort((a, b) => a - b).map(c => `<div class="card"><h4>${cyl(+c)}</h4><ul>${groups[c].map(p =>
      `<li>${esc(p.name)} — ${esc(p.label)} × ${p.packs} · ${fmt(p.order)}원 <span class="hint">(${p.storage})</span></li>`).join('')}</ul></div>`).join('') + '</div>';
    return;
  }
  $('#order').innerHTML = head + `<div class="tbl"><table><thead><tr><th scope="col">주기</th><th scope="col">분류</th><th scope="col">품목</th><th scope="col">보관</th><th scope="col">1회 발주</th><th scope="col" class="num">1회 금액(원)</th><th scope="col" class="num">월 사용액(원)</th><th scope="col">근거</th></tr></thead><tbody>
${list.map(p => `<tr><td class="nw">${cyl(p.cycle)}</td><td class="nw">${p.cat}</td><td>${esc(p.name)}</td><td class="nw">${p.storage}</td><td>${esc(p.label)} × ${p.packs}</td><td class="num">${fmt(p.order)}</td><td class="num">${fmt(p.month)}</td><td>${srcChip(p.src)}</td></tr>`).join('')}
</tbody></table></div>`;
}
function renderPeriodic() {
  const f = st.perFilter;
  const rows = st.periodic.map((p, j) => (f !== '전체' && f !== p.cat) ? '' :
    `<tr><td class="nw">${p.cat}</td><td>${esc(p.name)}<span class="badge-ex">예시</span></td><td class="nw">${cyl(p.cycle)}</td><td>${esc(p.unit)}</td>
<td class="num"><input id="p-${j}-amt" data-f="pamt" data-p="${j}" inputmode="numeric" value="${p.amount}" aria-label="${esc(p.name)} 1회 금액" style="max-width:110px"></td>
<td class="num">${fmt((Number(p.amount) || 0) * 30 / p.cycle)}</td><td>${p.opening ? '✓ 1회분' : '—'}</td></tr>`).join('');
  $('#periodic').innerHTML = rows ? rows + `<tr><th scope="row" colspan="5">월 환산 합계 → 4번 「기타 월 고정비」에 자동으로 더함</th><td class="num"><b>${fmt(perMonth(st.periodic))}</b></td><td></td></tr>`
    : '<tr><td colspan="7" class="hint">「예시 채우기」를 누르면 업종별 주기 구매 품목이 채워집니다</td></tr>';
}
function render() {
  $('#tier').innerHTML = ['premium', 'value', 'factory'].map(k => `<button type="button" data-tier="${k}" aria-pressed="${st.tier === k}">${D.TN[k]}</button>`).join('');
  document.querySelectorAll('#mode [data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === st.mode)));
  document.querySelectorAll('#orderView [data-oview]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.oview === st.oview)));
  $('#concept').textContent = `${ind().label} · ${D.TN[st.tier]} — ${ind().tiers[st.tier].concept}`;
  chips('#itemFilter', CATS, st.itemFilter, 'data-ifilter'); chips('#setupFilter', SCATS, st.setupFilter, 'data-sfilter');
  chips('#perFilter', PCATS, st.perFilter, 'data-pfilter'); chips('#orderFilter', ['식재료', '포장·일회용품'], st.orderFilter, 'data-ofilter');
  renderRows(); renderSetup(); renderPeriodic();
  const m = mixOf(st.rows), v = reqInputs(), pm = perMonth(st.periodic), r = reqOf(m, v, pm);
  const planD = num($('#plan-daily').value) > 0 ? num($('#plan-daily').value) : (r ? r.daily : NaN);
  const plan = Number.isFinite(planD) ? orderPlanOf(st.rows, planD, Number.isFinite(v.days) ? v.days : ind().days) : null;
  renderOrder(plan, planD);
  const first = (plan || []).reduce((a, p) => a + p.order, 0) + openingSupplies(st.periodic), setup = setupTotal(st.setup);
  $('#openTiles').innerHTML = st.filled ? `
<div class="tile"><div class="k">개업 첫 주문(초도 물량)</div><div class="v">${fmt(first / 10000)}<small>만원</small></div><div class="s">식재료·포장 한 주기분 + 위생·청소·주방 소모품·유니폼 1회분</div></div>
<div class="tile"><div class="k">한 번 사는 것</div><div class="v">${fmt(setup / 10000)}<small>만원</small></div><div class="s">식기 · 조리도구·주방 설비 · 매장 설비</div></div>
<div class="tile"><div class="k">개업 전 필요한 돈(설비·물품)</div><div class="v">${fmt((first + setup) / 10000)}<small>만원</small></div><div class="s">인테리어·보증금·권리금 제외 · 지금 화면의 투자비(손 계수) 중앙 ${fmt(D.INVEST_NOW)}만원 · 서울 외식업 평균 창업비 ${fmt(D.FOOD_AVG)}만원</div></div>` : '';
  $('#perLine').textContent = `주기 구매(위생·청소·설비 유지·서비스) 월 ${fmt(pm / 10000)}만원 — 3-2 표에서 자동으로 더합니다.`;
  $('#mixTiles').innerHTML = m ? `
<div class="tile"><div class="k">평균 객단가</div><div class="v">${fmt(m.avgP)}<small>원</small></div><div class="s">${m.n}개 메뉴 · ${m.weighted ? '판매 비중으로 가중' : '비중이 비어 단순 평균'}</div></div>
<div class="tile"><div class="k">평균 원가율</div><div class="v">${pctT(m.rate)}</div><div class="s">식재료+포장+수수료 · ${m.rate > D.BENCH ? '외식업 평균보다 높음' : '외식업 평균보다 낮음'}(식재료비 40.7% · 농식품부)</div></div>
<div class="tile"><div class="k">메뉴 1개당 남는 돈(원가 뺀)</div><div class="v">${fmt(m.avgP - m.avgC)}<small>원</small></div><div class="s">여기서 월세·인건비·고정비를 감당합니다</div></div>`
    : '<p class="hint">판매가와 원가(판매가보다 작게)가 있는 줄이 하나라도 있으면 평균 객단가와 원가율을 냅니다.</p>';
  $('#reqOut').innerHTML = !m ? '<p class="hint">메뉴를 채우면 계산합니다.</p>' : !r ? '<p class="hint">월세·인원·근무시간·시급·공과금·그 밖의 고정비·영업일(1~31)을 모두 넣으면 계산합니다.</p>' :
    `<p class="big">하루 <b>${r.daily.toLocaleString('ko-KR')}개</b> 팔아야 월세와 인건비·고정비를 감당해요</p>
<p>요구 월매출 <b>${man(r.bep)}</b> = (월세 ${man(v.rent)} + 인건비 ${man(r.labor)} + 공과금 ${man(v.util)} + 주기 구매 ${man(pm / 10000)} + 그 밖 ${man(v.etc)}) ÷ (1 − 원가율 ${pctT(m.rate)})
<span class="hint">· 인건비 = 인원 × 월 유급 ${paidHours(v.hours)}시간 × 시급</span></p>`;
  tierCmp();
}
function tierCmp() {
  const i = ind(), v = reqInputs(), rent = Number.isFinite(v.rent) ? v.rent : D.RENT;
  const cols = ['premium', 'value', 'factory'].map(k => ({k, ...summaryOf(i.key, k, rent)}));
  const row = (lab, f) => `<tr><th scope="row">${lab}</th>${cols.map(c => `<td class="num">${f(c)}</td>`).join('')}</tr>`;
  $('#tierCmp').innerHTML = `<caption>${esc(i.label)} — 레시피 원가 예시 · 월세 ${fmt(rent)}만원 · 주 40시간 · 최저임금 · 공과금 ${D.UTIL[i.key]}만원 기준</caption>
<thead><tr><th scope="col">항목</th>${cols.map(c => `<th scope="col" class="num">${D.TN[c.k]}</th>`).join('')}</tr></thead><tbody>
${row('콘셉트', c => `<span class="hint">${esc(c.t.concept)}</span>`)}
${row('메뉴 수', c => c.t.menus.length)}${row('평균 객단가', c => fmt(c.m.avgP) + '원')}${row('평균 원가율', c => pctT(c.m.rate))}
${row('인원', c => c.t.staff + '명')}${row('주기 구매(월)', c => man(c.pm / 10000))}${row('요구 월매출', c => man(c.r.bep))}${row('하루 판매', c => c.r.daily.toLocaleString('ko-KR') + '개')}
${row('한 번 사는 것', c => man(c.setup / 10000))}${row('개업 첫 주문', c => man(c.first / 10000))}${row('개업 전 필요한 돈', c => '<b>' + man(c.pre / 10000) + '</b>')}</tbody>`;
}
function allEx() {
  $('#allEx').innerHTML = D.IND.map(i => `<details><summary>${esc(i.label)}</summary>${['premium', 'value', 'factory'].map(k => {
    const s = summaryOf(i.key, k, D.RENT), rows = exampleRows(i.key, k, 'recipe');
    return `<div class="tbl"><table><caption>${D.TN[k]} — ${esc(s.t.concept)} · 객단가 ${fmt(s.m.avgP)}원 · 원가율 ${pctT(s.m.rate)} · 주기 구매 월 ${man(s.pm / 10000)} · 개업 첫 주문 ${man(s.first / 10000)}</caption>
<thead><tr><th scope="col">메뉴</th><th scope="col" class="num">판매가</th><th scope="col" class="num">비중</th><th scope="col" class="num">원가</th><th scope="col" class="num">원가율</th><th scope="col">원가 항목(분류: 이름 금액)</th></tr></thead><tbody>
${rows.map(r => { const c = rowCost(r); return `<tr><th scope="row">${esc(r.name)}</th><td class="num">${fmt(num(r.price))}원</td><td class="num">${r.share}%</td><td class="num">${fmt(c.total)}원</td><td class="num">${pctT(c.total / num(r.price))}</td>
<td class="hint">${r.items.map(it => `${it.cat === '식재료' ? '' : '[' + it.cat + '] '}${esc(it.name)} ${fmt(it.qty * it.up)}원`).join(' · ')}${r.pct.map(p => ` · [기타 변동비] ${esc(p.name)} ${fmt(num(r.price) * p.rate)}원`).join('')}</td></tr>`; }).join('')}
</tbody></table></div>`; }).join('')}</details>`).join('');
}
function ingTbl() {
  const rows = Object.entries(D.ING).sort((a, b) => a[1][5].localeCompare(b[1][5], 'ko'));
  $('#ingTbl').innerHTML = `<caption>환산 단가 = 구매가 ÷ 구매 단위. 출처가 없는 값은 「예시(가정)」입니다 — 거래처 견적·영수증으로 바꾸세요.</caption>
<thead><tr><th scope="col">분류</th><th scope="col">이름</th><th scope="col" class="num">구매</th><th scope="col" class="num">환산 단가</th><th scope="col">발주 단위</th><th scope="col">보관</th><th scope="col">주기</th><th scope="col">근거</th></tr></thead><tbody>
${rows.map(([k, g]) => { const od = D.ORDER[k]; return `<tr><td>${g[5]}</td><td>${esc(g[0])}</td><td class="num">${esc(g[1])} ${fmt(g[2])}원</td><td class="num">${g[4].toLocaleString('ko-KR')}원/${esc(g[3])}</td>
<td>${od ? esc(od[1]) : '사지 않음(자가생산)'}</td><td>${od ? od[2] : '—'}</td><td>${od ? cyl(od[3]) : '—'}</td><td>${srcChip(g[6])}</td></tr>`; }).join('')}</tbody>`;
}

$('#ind').innerHTML = D.IND.map(i => `<option value="${i.key}">${esc(i.label)}</option>`).join('');
$('#rq-hours').value = 40; $('#rq-wage').value = D.WAGE; $('#rq-rent').value = ''; $('#rq-etc').value = 0;
$('#rq-util').value = D.UTIL[D.IND[0].key]; $('#rq-days').value = D.IND[0].days;
const autoRefill = () => st.filled && !st.rows.some(r => !r.ex);
$('#ind').addEventListener('change', e => { st.ind = e.target.value; if (autoRefill()) fill(); else render(); });
document.addEventListener('click', e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.id === 'fill') return fill();
  if (t.id === 'clear') { st.rows = [blank(), blank(), blank()]; st.setup = []; st.periodic = []; st.filled = false; st.open = new Set(); return render(); }
  if (t.id === 'add') { if (st.rows.length < MAXROWS) st.rows.push(blank()); return render(); }
  if (t.dataset.tier) { st.tier = t.dataset.tier; return autoRefill() ? fill() : render(); }
  if (t.dataset.mode) { st.mode = t.dataset.mode; return autoRefill() ? fill() : render(); }
  if (t.dataset.oview) { st.oview = t.dataset.oview; return render(); }
  if (t.dataset.ifilter) { st.itemFilter = t.dataset.ifilter; return render(); }
  if (t.dataset.sfilter) { st.setupFilter = t.dataset.sfilter; return render(); }
  if (t.dataset.pfilter) { st.perFilter = t.dataset.pfilter; return render(); }
  if (t.dataset.ofilter) { st.orderFilter = t.dataset.ofilter; return render(); }
  if (t.dataset.act === 'open') { const i = +t.dataset.r; st.open.has(i) ? st.open.delete(i) : st.open.add(i); return render(); }
  if (t.dataset.act === 'del') { st.rows.splice(+t.dataset.r, 1); st.open = new Set(); return render(); }
});
document.addEventListener('change', e => {
  const el = e.target, f = el.dataset && el.dataset.f, idv = el.id || '';
  if (!f && !idv.startsWith('rq-') && idv !== 'plan-daily') return;
  if (f === 'qty' || f === 'up') { const r = st.rows[+el.dataset.r]; r.items[+el.dataset.i][f] = num(el.value) || 0; r.ex = false; }
  else if (f === 'sqty' || f === 'sup') { st.setup[+el.dataset.s][f === 'sqty' ? 'qty' : 'up'] = num(el.value) || 0; }
  else if (f === 'pamt') { st.periodic[+el.dataset.p].amount = num(el.value) || 0; }
  else if (f) { const r = st.rows[+el.dataset.r]; r[f] = el.value.trim(); r.ex = false;
    if (f === 'manual' || (r.kind === 'manual' && f === 'price')) r.kind = 'manual'; }
  setTimeout(() => { const id = document.activeElement && document.activeElement.id; render(); if (id) { const n = document.getElementById(id); if (n) n.focus(); } }, 0);
});
render(); allEx(); ingTbl();
"""


def build():
    js = "<script>" + JS.replace("__DATA__", json.dumps(DATA, ensure_ascii=False)) + "</script>"
    return page("placeos-06-menu-fill.html", "메뉴 예시 채우기", "메뉴 설정 「예시 채우기」 — 메뉴 · 준비물 · 주기별 구매까지",
                "업종과 가격대를 고르고 「예시 채우기」를 누르면 대표 메뉴의 판매가·비중·원가(재료·포장·수수료), 한 번 사는 준비물, "
                "<b>주기별로 사는 것</b>(식재료·포장 발주 계획 · 위생·청소·설비 유지·서비스), 개업 첫 주문, 하루 몇 개를 팔아야 하는지까지 채워집니다.",
                chip("새 기능 제안 · v2", "v") + " " + chip("예시 값 · 출처 표기", "decide"), STYLE + BODY, js)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "placeos-06-menu-fill.html").write_text(build(), encoding="utf-8")
    print("wrote placeos-06-menu-fill.html")
