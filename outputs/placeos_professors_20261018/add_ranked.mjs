import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const dir=new URL('./',import.meta.url);
const file=new URL('PlaceOS_교수_통합명단.xlsx',dir);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(file)));
console.log((await wb.inspect({kind:'workbook',include:'id,name',maxChars:1200})).ndjson);
const before=wb.worksheets.items.map(s=>({name:s.name,values:s.getRange('A1:O160').values,formulas:s.getRange('A1:O160').formulas}));
await fs.writeFile(new URL('before_ranked.png',dir),new Uint8Array(await (await wb.render({sheetName:'교수명단',range:'A7:G11',scale:1})).arrayBuffer()));
const people=[];
function add(uni,aff,source,lines){for(const line of lines.trim().split('\n')){const [name,lab,email,field,priority='2']=line.split('|');people.push({uni,aff,source,name,lab,email,field,priority:Number(priority)});}}
add('성균관대학교','수원 · 글로벌창업대학원','https://startup.skku.edu/',`
김경환|별도 연구실명 미확인|khkim61@skku.edu|창업정책·기술사업화·기업가치 평가|1`);
add('성균관대학교','수원 · 기술경영전문대학원','https://skkmot.skku.edu/mot/intro/faculty.do',`
신준석|계량기술경영 연구실|jsshin@skku.edu|사업모델·기술전략·데이터 분석|1
신정우|별도 연구실명 미확인|shinjung11@skku.edu|데이터 기반 기술 인텔리전스·시장 분석|1
박상민|별도 연구실명 미확인|sangminpark@skku.edu|혁신정책·창업 생태계|1
임동준|테크노메트릭스연구실|tgno3@skku.edu|데이터과학·최적화·생산성|2
조근태|기술경영 연구실|ktcho@skku.edu|기술사업화·의사결정|1`);
add('서울대학교','경영대학 · 대학원 경영학과','https://cba.snu.ac.kr/en/research/faculty/professor?major=1',`
유병준|별도 연구실명 미확인|byoo@snu.ac.kr|MIS·디지털 플랫폼·비즈니스모델·창업|1
장정주|별도 연구실명 미확인|jahngj@snu.ac.kr|MIS·IT 전략·디지털 혁신|2`);
add('서울대학교','공과대학 · 기술경영경제정책전공','https://temep.snu.ac.kr/about/faculty/professor',`
이정혜|Computational Innovation Lab|junghye@snu.ac.kr|그래프 AI·혁신 분석|1
김연배|별도 연구실명 미확인|kimy1234@snu.ac.kr|기술사업화·혁신 생태계|1
황준석|별도 연구실명 미확인|junhwang@snu.ac.kr|스마트시티·디지털 전환·플랫폼 경제|1
이종수|별도 연구실명 미확인|jxlee@snu.ac.kr|수요 예측·소비자 선택·혁신 확산|2
이정동|별도 연구실명 미확인|leejd@snu.ac.kr|혁신경제·기업 및 산업 변화|2
구윤모|별도 연구실명 미확인|yyounmo@snu.ac.kr|기술정책·혁신 확산|3`);
add('서울대학교','공과대학 · 컴퓨터공학부','https://cse.snu.ac.kr/api/v1/file/1712387520810_CSE_Brochure.pdf',`
장병탁|바이오지능 연구실|btzhang@bi.snu.ac.kr|인공지능 방법론|3`);
add('KAIST','서울 · 경영대학 / 지도 과정 개별 확인','https://www.business.kaist.ac.kr/_prog/prof/?menu_dvs_cd=0401&site_dvs_cd=kr',`
백용욱|별도 연구실명 미확인|ywpaik@kaist.ac.kr|기업가정신·혁신·디지털 및 AI 경제|1
진병채|KAIST-SK 임팩트비즈니스센터|bjin@kaist.ac.kr|기술혁신·기업가정신|1
박병호|별도 연구실명 미확인|mediapark@kaist.ac.kr|사용자 행동·실험 연구|2
백윤석|별도 연구실명 미확인|ysbaik@kaist.ac.kr|전략경영|3
이지환|별도 연구실명 미확인|jihwanlee@kaist.ac.kr|전략경영·국제경영|3
박상찬|별도 연구실명 미확인|parks@kaist.ac.kr|조직·업무 혁신·사회적 가치|3`);
add('연세대학교','경영대학 · 대학원 경영학과','https://ysb.yonsei.ac.kr/mba/faculty/odi-is.do',`
임일|별도 연구실명 미확인|il.im@yonsei.ac.kr|추천시스템·SNS·AI의 영향|1
조대곤|별도 연구실명 미확인|daegon.cho@yonsei.ac.kr|디지털 플랫폼·AI 활용·데이터 의사결정|1
김승현|별도 연구실명 미확인|seungkim@yonsei.ac.kr|ODI-IS·정보시스템|2
방영석|별도 연구실명 미확인|yb@yonsei.ac.kr|ODI-IS·정보시스템|2
손재열|별도 연구실명 미확인|json@yonsei.ac.kr|ODI-IS·정보시스템|2
임건신|별도 연구실명 미확인|ksim@yonsei.ac.kr|ODI-IS·정보시스템|2`);
add('연세대학교','대학원 산업공학과','https://ie.yonsei.ac.kr/laboratory/list.php?type=2',`
임춘성|산업 경쟁력 연구실|leem@yonsei.ac.kr|사업모델·기술가치·정보시스템 평가|1
박희준|혁신경영 연구실|h.park@yonsei.ac.kr|플랫폼·사업모델·디지털 혁신|1
조영상|기술 경영 정책 연구실|y.cho@yonsei.ac.kr|소비자 선호·수요 예측·기술가치|2
모정훈|경영과학 연구실|j.mo@yonsei.ac.kr|최적화·강화학습·딥러닝|2
지용구|상호작용설계 연구실|yongguji@yonsei.ac.kr|사용자 경험·상호작용 설계|2`);
add('연세대학교','대학원 산업공학과','https://ie.yonsei.ac.kr/laboratory/list.php?type=1',`
윤현수|지식융합 인공지능 연구실|hs.yoon@yonsei.ac.kr|이종 데이터 결합·AI 에이전트|2
김우주|스마트 시스템 연구실|wkim@yonsei.ac.kr|자연어처리·지식그래프·데이터 분석|2
김창욱|시스템 인텔리전스 연구실|kimco@yonsei.ac.kr|AI·데이터 분석|2`);
add('연세대학교','대학원 인공지능학과','https://research.yonsei.ac.kr/csai_en/research/researchAI.do',`
여진영|Language & AGI Lab|jinyeo@yonsei.ac.kr|LLM·대화형 AI·에이전트|2`);
add('연세대학교','대학원 컴퓨터과학과','https://research.yonsei.ac.kr/csai_en/research/researchAI.do',`
이경호|Internet Computing Lab|khlee89@yonsei.ac.kr|추천·지식그래프·대화|2
조성배|Soft Computing Lab|sbcho@yonsei.ac.kr|신뢰 가능한 AI·하이브리드 학습|3`);
add('고려대학교','대학원 산업경영공학과','https://ie.korea.edu/ie_en/faculty/laboratory4.do',`
강필성|Data Science & Business Analytics Lab|pilsung_kang@korea.ac.kr|데이터 기반 경영·AI 의사결정|1`);
add('고려대학교','대학원 산업경영공학과','https://dmqa.korea.ac.kr/members/professor',`
김성범|Data Mining & Quality Analytics Lab|sbkim1@korea.ac.kr|머신러닝·데이터 분석·LLM|2`);
add('고려대학교','대학원 컴퓨터학과','https://nlp.korea.ac.kr/professor-2/',`
임희석|NLP&AI Lab|limhseok@korea.ac.kr|자연어처리·LLM·교육 AI|2`);
add('고려대학교','대학원 컴퓨터학과','https://info.korea.edu/en_info/about/fulltime_computer.do?articleNo=255757&mode=view',`
강재우|Data Mining & Information Systems Lab|kangj@korea.ac.kr|데이터마이닝·바이오 NLP 중심|3`);
add('고려대학교','대학원 인공지능학과 / 지도 자격 확인','https://tlo.korea.ac.kr/en/researcher/1564',`
이성환|Pattern Recognition & Machine Learning Lab|sw.lee@korea.ac.kr|패턴인식·머신러닝|3`);
add('고려대학교','경영대학 · 대학원 경영학과','https://biz.korea.ac.kr/eng/professor/professor_list1.html?major=M08',`
김정현|별도 연구실명 미확인|jeunghyunkim@korea.ac.kr|비즈니스 애널리틱스|2
김재환|별도 연구실명 미확인|jbayes@korea.ac.kr|마케팅 애널리틱스|2
김병조|별도 연구실명 미확인|bkim@korea.ac.kr|최적화·비즈니스 애널리틱스|2
김기훈|별도 연구실명 미확인|kihoon@korea.ac.kr|운영·비즈니스 애널리틱스|2
황준호|별도 연구실명 미확인|joonhwang@korea.ac.kr|비즈니스 애널리틱스|2`);
add('성균관대학교','서울 · 인공지능융합학과','https://skb.skku.edu/skkuaai/faculty.do',`
박은일|Data eXperience Laboratory|eunilpark@skku.edu|사용자 경험·데이터·산업 AI|2
이대호|Digital Environment & Human Behavior Lab|daeho.lee@skku.edu|플랫폼·AI 사용자 행동·서비스 전략|2
최윤석|Data & Language Intelligence Lab|ys.choi@skku.edu|LLM·자연어처리·추천|2
오하영|LAMDA Lab|hyoh79@skku.edu|AI 에이전트·LLM·추천|2
한진영|Data Science & Artificial Intelligence Lab|jinyounghan@skku.edu|소셜 컴퓨팅·네트워크·머신러닝|2
김장현|Data Science & Social Analytics Lab|alohakim@skku.edu|사회·의미 네트워크·스마트미디어|2
민무홍|소프트웨어연구실|iceo@skku.edu|AI 보안·기술창업 교육|2
홍주화|AAA Lab|j.hong@skku.edu|인간-AI 상호작용·소셜 AI|2
김재광|main Lab|linux@skku.edu|머신 인텔리전스|3`);
add('성균관대학교','서울 · 경영대학·대학원 경영학과','https://skb.skku.edu/gcemba_eng/faculty.do',`
유상석|별도 연구실명 미확인|sangyou@skku.edu|인간-AI 협업·알고리즘 의사결정|2
서아영|별도 연구실명 미확인|aysuh@skku.edu|인간-AI 협업·디지털 서비스·창의성|2`);
add('성균관대학교','수원 · 인공지능학과','https://ai.skku.edu/ai/faculty.do',`
이종욱|데이터지능 및 학습 연구실 DIAL|jongwuklee@skku.edu|추천·검색·자연어처리|2
이지형|정보 및 지능시스템 연구실|john@skku.edu|추천·텍스트 학습|2
이선재|Future Computing Lab|sunjae.lee@skku.edu|AI 에이전트·인간-AI 협업|2
이한국|효율적 기계학습 연구실 ELL|hankook.lee@skku.edu|시계열·표형 데이터·전이학습|2
조재민|인터랙티브데이터컴퓨팅 연구실|jmjo@skku.edu|데이터 시각화·상호작용|2
심규홍|음성 및 자연어처리 연구실|khshim@skku.edu|LLM·멀티모달|3`);
add('성균관대학교','수원 · 소프트웨어·지능형소프트웨어','https://skb.skku.edu/intelligentsw/faculty.do',`
박호건|LearnData Laboratory|hogunpark@skku.edu|설명 가능한 AI·그래프·지식|2
박진영|HLILab|jy.bak@skku.edu|자연어처리·머신러닝|2`);
if(people.length!==67)throw Error('추가 인원 불일치 '+people.length);
const old=new Set(wb.worksheets.getItem('교수명단').getRange('B8:C142').values.map(r=>r.join('|')));
for(const p of people){if(old.has(p.uni+'|'+p.name))throw Error('중복 '+p.name);if(!p.email.includes('@'))throw Error(p.name);}
people.sort((a,b)=>a.priority-b.priority);
const s=wb.worksheets.add('추가 후보_적합순');
s.getRange('A1').values=[['PlaceOS·Co.I 추가 교수 연락처 — 적합도 순']];
s.getRange('A2').values=[['정렬: 1순위 창업·MOT·플랫폼 직접 접점 → 2순위 MIS·응용 AI → 3순위 방법론·간접 접점. 동순위 내 순서는 추천 판단입니다.']];
s.getRange('A3').values=[['파트타임 지도·채용 가능성은 미확인. 기존 시트와 체크 상태는 수정하지 않았습니다. 공개 연구 분야를 바탕으로 선정했습니다.']];
const header=['적합 순위','우선군','대학교','교수명','캠퍼스·대학원·학과','연구실·관련 조직','이메일','연구 분야·문의 접점','파트타임·지도 확인 사항','공식 출처'];
const rows=people.map((p,i)=>[i+1,p.priority+'순위',p.uni,p.name,p.aff,p.lab,p.email,p.field,p.aff.includes('기술경영전문대학원')&&p.uni==='성균관대학교'?'주간·야간·주말 개설 확인. 재직·지도 조건 개별 문의':p.uni==='KAIST'?'서울 IMMS는 파트타임. 해당 교수의 IMMS 지도 여부 별도 확인; 경영공학 석박사는 전일제':'재직·파트타임 지원, 지도 및 연구원 채용 가능 여부 개별 문의',p.source]);
s.getRange('A5:J72').values=[header,...rows];
s.tables.add('A5:J72',true,'AdditionalRankedContacts');
s.getRange('A5:J72').format.font={name:'Arial',size:10};
s.getRange('A6:J72').format.wrapText=true;
s.getRange('A6:J72').format.rowHeight=62;
s.getRange('A5:J5').format={fill:'#183B56',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30};
for(const [i,w]of [10,10,22,14,43,46,39,48,60,65].entries())s.getRangeByIndexes(4,i,68,1).format.columnWidth=w;
s.getRange('A1').format.font={name:'Arial',size:16,bold:true,color:'#183B56'};
s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(4);
wb.recalculate();
for(const snap of before){const sh=wb.worksheets.getItem(snap.name);if(JSON.stringify(snap.values)!==JSON.stringify(sh.getRange('A1:O160').values)||JSON.stringify(snap.formulas)!==JSON.stringify(sh.getRange('A1:O160').formulas))throw Error('기존 데이터 변경 '+snap.name);}
const backup=new URL('PlaceOS_교수_통합명단_추가전백업.xlsx',dir);try{await fs.access(backup);}catch{await fs.copyFile(file,backup);}
await (await SpreadsheetFile.exportXlsx(wb)).save(fileURLToPath(file));
await fs.writeFile(new URL('ranked_preview.png',dir),new Uint8Array(await (await wb.render({sheetName:s.name,range:'A5:H11',scale:1})).arrayBuffer()));
console.log(JSON.stringify({added:people.length,existingDataUnchanged:true,top:people.slice(0,8).map(p=>p.name)}));
