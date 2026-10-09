const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
 const browser = await chromium.launch({ executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true });
 const results=[];
 const context=await browser.newContext({viewport:{width:1440,height:900},hasTouch:true});
 const page=await context.newPage();
 page.setDefaultTimeout(15000);
 for(const [width,height] of [[1440,900],[1024,768],[768,1024],[390,844],[320,568]]) {
  await page.setViewportSize({width,height});
  for(const goal of ['start','move','pivot']) {
   console.log('checking',width,goal);
   await page.goto(`http://127.0.0.1:5173/.qa-industry.html?goal=${goal}`);
   const button=page.getByRole('button',{name:'데이터 기준·출처'});
   await button.waitFor();
   if(await button.getAttribute('aria-expanded')!=='false') throw new Error('not collapsed');
   await button.focus();
   await page.keyboard.press('Enter');
   if(await button.getAttribute('aria-expanded')!=='true') throw new Error('Enter failed');
   await page.keyboard.press('Space');
   if(await button.getAttribute('aria-expanded')!=='false') throw new Error('Space failed');
   if(width<600) await button.tap(); else await button.click();
   const metrics=await page.locator('.fitcard').evaluate(card=>{
    const facts=card.querySelector('.fit-facts');const wrap=card.querySelector('.fit-table-wrap');const toggle=card.querySelector('.fit-source-toggle');const src=card.querySelector('.fit-src');
    return {cardWidth:card.clientWidth,cardScrollWidth:card.scrollWidth,columns:facts?getComputedStyle(facts).gridTemplateColumns:null,tableWidth:wrap.clientWidth,tableScrollWidth:wrap.scrollWidth,sourceWidth:src.clientWidth,sourceScrollWidth:src.scrollWidth,buttonHeight:toggle.getBoundingClientRect().height,sourceVisible:!src.hidden};
   });
   if(metrics.cardScrollWidth>metrics.cardWidth+1 || metrics.sourceScrollWidth>metrics.sourceWidth+1 || metrics.buttonHeight<44 || !metrics.sourceVisible) throw new Error(JSON.stringify({width,goal,metrics}));
   await page.screenshot({path:`.qa/industry-fit/${width}-${goal}-viewport.png`});
   // 실제 패널의 너비는 유지하고 스크롤 밖까지 펼쳐 전체 카드 이미지를 확인한다.
   await page.locator('.trackmap-panel').evaluate(el=>{el.style.position='relative';el.style.top='0';el.style.left='0';el.style.bottom='auto';el.style.height='auto';el.style.width=el.getBoundingClientRect().width+'px';});
   await page.locator('.fitcard').screenshot({path:`.qa/industry-fit/${width}-${goal}-open.png`});
   await button.click();
   if(goal==='start') await page.locator('.fitcard').screenshot({path:`.qa/industry-fit/${width}-${goal}-closed.png`});
   results.push({width,height,goal,...metrics});
  }
 }
 await page.setViewportSize({width:1440,height:900});
 await page.goto('http://127.0.0.1:5173/.qa-industry.html?wide=1');
 await page.getByRole('button',{name:'데이터 기준·출처'}).waitFor();
 const columns=await page.locator('.fit-facts').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);
 if(columns!==4) throw new Error(`wide columns ${columns}`);
 await page.locator('.fitcard').screenshot({path:'.qa/industry-fit/1440-wide.png'});
 fs.writeFileSync('.qa/industry-fit/results.json',JSON.stringify(results,null,2));
 console.log(JSON.stringify({browser:browser.version(),cases:results.length,wideColumns:columns,results}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
