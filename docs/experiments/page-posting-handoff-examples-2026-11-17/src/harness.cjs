// 표현 유형 자동 검증 — node src/harness.cjs <실험 폴더> <라운드 이름>
// 유형마다 데스크톱(1280×800)·폰(390×844) 라이트, 폰 다크로 열어 잰다. 판정·점수는 report.py 가 낸다(여기서는 원값만).
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path');
const [Xarg = '.', roundName = 'r0'] = process.argv.slice(2);
const X = path.resolve(Xarg);  // 상대 경로(.)도 file:// 주소가 되게 — 측정은 그대로
const cfg = JSON.parse(fs.readFileSync(path.join(X, 'out/types/check-config.json'), 'utf8'));
const shots = path.join(X, 'out/compare/shots'); fs.mkdirSync(shots, {recursive: true});

const PAGE_FN = (args) => {
  const {facts, core, mobile} = args;
  const vis = el => { for (let e = el; e && e !== document; e = e.parentElement) { const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden' || e.hidden) return false; } return true; };
  const all = document.body.textContent.replace(/\s+/g, ' ');
  // 첫 화면에 실제로 그려진 글자만
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let above = ''; let n;
  while ((n = tw.nextNode())) { if (!n.nodeValue.trim() || !n.parentElement || !vis(n.parentElement)) continue;
    const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect();
    if (b.height > 0 && b.bottom > 0 && b.top < innerHeight && b.right > 0 && b.left < innerWidth) above += ' ' + n.nodeValue; }
  above = above.replace(/\s+/g, ' ');
  const closedDetails = [...document.querySelectorAll('details:not([open])')].filter(d => vis(d)).length;
  const hiddenBlocks = [...document.querySelectorAll('[hidden]')].filter(e => !e.parentElement.closest('[hidden]') && e.textContent.trim().length > 20).length;
  // 글자 대비
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0.5) return c; }
    return parse(getComputedStyle(document.body).backgroundColor) || {r: 255, g: 255, b: 255, a: 1}; };
  let cTot = 0, cOk = 0, minFont = 99; const lowSamples = [];
  document.querySelectorAll('body *').forEach(el => {
    if (['SCRIPT', 'STYLE'].includes(el.tagName) || el.classList.contains('tip')) return;
    const own = [...el.childNodes].some(x => x.nodeType === 3 && x.nodeValue.trim()); if (!own || !vis(el)) return;
    const s = getComputedStyle(el), fg = parse(s.color), bg = bgOf(el); if (!fg) return;
    const fs = parseFloat(s.fontSize); minFont = Math.min(minFont, fs);
    const L1 = lum(fg), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const large = fs >= 24 || (fs >= 18.66 && parseInt(s.fontWeight) >= 700);
    cTot++; if (ratio >= (large ? 3 : 4.5)) cOk++; else if (lowSamples.length < 4) lowSamples.push(el.tagName + '.' + el.className + ' ' + ratio.toFixed(2));
  });
  // 이름 · 대체 텍스트 · 앵커
  const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')].filter(vis);
  const nameOf = e => (e.getAttribute('aria-label') || (e.id && document.querySelector(`label[for="${e.id}"]`)?.textContent) || e.closest('label')?.textContent || e.textContent || e.title || '').trim();
  const named = focusables.filter(e => nameOf(e)).length;
  const imgs = [...document.querySelectorAll('svg[role="img"],[role="img"],img')];
  const alt = imgs.filter(e => (e.getAttribute('aria-label') || e.getAttribute('alt') || '').trim()).length;
  const anchors = [...document.querySelectorAll('a[href^="#"]')].map(a => a.getAttribute('href')).filter(h => h.length > 1);
  const anchorsOk = anchors.filter(h => document.getElementById(decodeURIComponent(h.slice(1)))).length;
  const files = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => !/^(#|https?:|mailto:)/.test(h));
  // 터치 대상(폰) — 버튼·요약·선택·입력·내비 링크
  let tapTot = 0, tapOk = 0;
  if (mobile) [...document.querySelectorAll('button,summary,select,input:not([type=hidden]),nav a')].filter(vis).forEach(e => {
    const r = e.getBoundingClientRect(); if (!r.width) return; tapTot++; if (r.height >= 32 && r.width >= 32) tapOk++; });
  return {factsFound: facts.filter(f => all.includes(f)), coreAbove: core.filter(t => above.includes(t)),
    screens: document.documentElement.scrollHeight / innerHeight, closedDetails, hiddenBlocks,
    overflow: document.documentElement.scrollWidth - innerWidth, minFont, contrast: cTot ? cOk / cTot : 1, lowSamples,
    names: focusables.length ? named / focusables.length : 1, alt: imgs.length ? alt / imgs.length : 1,
    anchors: anchors.length ? anchorsOk / anchors.length : 1, files, tap: tapTot ? tapOk / tapTot : 1, textChars: all.length};
};

(async () => {
  const b = await chromium.launch(); const res = {round: roundName, at: new Date().toISOString(), types: {}};
  for (const t of cfg.types) {
    const file = path.join(X, 'out/types', t.file), url = 'file://' + file, r = {errors: []};
    for (const [mode, vw, vh, scheme] of [['desktop', 1280, 800, 'light'], ['mobile', 390, 844, 'light'], ['mobileDark', 390, 844, 'dark']]) {
      const ctx = await b.newContext({viewport: {width: vw, height: vh}, colorScheme: scheme}); const pg = await ctx.newPage();
      pg.on('pageerror', e => r.errors.push(String(e))); pg.on('console', m => m.type() === 'error' && r.errors.push(m.text()));
      await pg.goto(url); await pg.waitForTimeout(250);
      r[mode] = await pg.evaluate(PAGE_FN, {facts: cfg.facts, core: cfg.core, mobile: mode !== 'desktop'});
      if (mode !== 'mobileDark') await pg.screenshot({path: path.join(shots, `${t.key}-${mode === 'desktop' ? 'd' : 'm'}.jpg`), type: 'jpeg', quality: 70});
      await ctx.close();
    }
    const fl = r.desktop.files; r.fileLinks = fl.length ? fl.filter(h => fs.existsSync(path.resolve(path.dirname(file), h.split('#')[0]))).length / fl.length : 1;
    r.bytes = fs.statSync(file).size; res.types[t.key] = r;
    console.log(t.key, t.name, `사실 ${r.desktop.factsFound.length}/${cfg.facts.length}`, `첫화면 폰 ${r.mobile.coreAbove.length}/5 · PC ${r.desktop.coreAbove.length}/5`,
      `폰 ${r.mobile.screens.toFixed(1)}화면 · 숨김 ${r.mobile.closedDetails + r.mobile.hiddenBlocks}`, `넘침 ${r.mobile.overflow}`, `최소글자 ${r.mobile.minFont}`,
      `대비 ${(r.mobile.contrast * 100).toFixed(0)}%/${(r.mobileDark.contrast * 100).toFixed(0)}%`, `터치 ${(r.mobile.tap * 100).toFixed(0)}%`, `오류 ${r.errors.length}`);
  }
  fs.writeFileSync(path.join(X, `out/compare/metrics-${roundName}.json`), JSON.stringify(res, null, 1));
  await b.close();
})();
