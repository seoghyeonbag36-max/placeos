import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const dir=new URL('./',import.meta.url), file=new URL('PlaceOS_교수_통합명단.xlsx',dir);
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(file)));
const snapshots=wb.worksheets.items.map(s=>({name:s.name,values:s.getRange('A1:O180').values,formulas:s.getRange('A1:O180').formulas}));
assert(!snapshots.some(s=>s.name==='추가_연구·산학협력'));
const existing=new Set(snapshots.flatMap(s=>s.values.flat()).filter(v=>typeof v==='string'&&v.includes('@')));
const rows=[
['동국대학교','성창수','서울 · 일반대학원 기술창업학과','기업가정신과혁신연구소(학과 연계 조직)','redsun44@dgu.ac.kr','기업가정신·기술창업전략·로컬비즈니스','PlaceOS의 상권·창업 의사결정과 Co.I의 창업지원·교육을 학술 연구로 연결','학과는 창업기술원·창업교육·보육·기술사업화 조직 연계를 공식 안내. 연구소 참여·과제 업무 및 재직 학위 병행 상담','https://startup.dongguk.edu/professor/list?professor_haggwa_type=PROFH_150','https://startup.dongguk.edu/page/2787'],
['동국대학교','전병훈','서울 · 일반대학원 기술창업학과','개별 연구실명 미확인 / 기술창업학과','bhjeon@dongguk.edu','기술사업화·창업 캡스톤디자인','Co.I의 창업팀 사업화 지원·MVP·사업 검증 연구','학과의 창업지원 조직 연계를 바탕으로 기술사업화 과제·연구 참여 경로 상담. 개인 운영 연구소·채용 미확인','https://startup.dongguk.edu/professor/list?professor_haggwa_type=PROFH_150','https://startup.dongguk.edu/page/2781'],
['서강대학교','김용진','서울 · 경영대학 / 대학원 지도 과정 확인','스마트핀테크연구센터','yongjkim@sogang.ac.kr','MIS·디지털 플랫폼·O2O 솔루션·사업모델','PlaceOS의 온라인 정보와 상업공간 연결, Co.I의 사업모델 혁신 연구','공식 센터 소개에 센터장 및 빅데이터 기반 O2O 솔루션 연구 명시. 센터 과제·연구원 업무와 학업 병행 상담','https://scc.sogang.ac.kr/isbs/isbs08_2_2.html','https://sc.sogang.ac.kr/sfrc/3209.html'],
['한성대학교','이형용','서울 · 지식서비스&컨설팅대학원','개별 연구실명 미확인 / 지식서비스&컨설팅','leemit@hansung.kr','경영공학·AI 활용 분석·컨설팅 조사연구','PlaceOS의 분석 신뢰성·의사결정 지원 효과를 정량적으로 검증','AI 창업·상권 분석 및 기술사업화 관련 교수 연결, 산학 컨설팅 과제 참여 경로 상담. 연구소 운영·채용 미확인','https://hansung.ac.kr/prsnInt/gshansung/228/artclView.do?buseo=KA30&sabun=110588','https://www.hansung.ac.kr/kscon/3647/subview.do'],
['한성대학교','주형근','서울 · 지식서비스&컨설팅대학원 참여 교수','개별 연구실명 미확인 / 컨설팅·마케팅','82hkjoo@naver.com','마케팅·지식서비스 컨설팅·사업 분석','PlaceOS·Co.I의 시장 검증·컨설팅 효과 및 사업화 연구','컨설팅·산학 프로젝트에서 데이터 분석·AI 개발 기여와 학위 병행 경로 상담. 연구소 운영·채용 미확인','https://www.hansung.ac.kr/gshansung/3501/subview.do','https://www.hansung.ac.kr/kscon/3647/subview.do'],
['서강대학교','김진화','서울 · 경영대학 / 대학원 지도 과정 확인','개별 연구실명 미확인 / MIS·AI 연구','jinhwakim@sogang.ac.kr','MIS·빅데이터·인공지능','PlaceOS의 추천·예측 모형과 Co.I의 AI 서비스 효과 연구','AI·빅데이터 과제에서 개발·분석 업무를 수행하며 학업 병행 가능 여부 상담. 연구원 채용 미확인','https://sc.sogang.ac.kr/jinhwakim/',''],
['숭실대학교','최정일','서울 · 일반대학원 IT정책경영학과 참여 / 경영학부','개별 연구실명 미확인 / IT정책경영학과','jichoi@ssu.ac.kr','비즈니스모델·전략·서비스경영','PlaceOS·Co.I 서비스의 사업모델·수용·성과 검증 연구','공식 이력에 창업지원단장·캠퍼스타운사업단장 역임. 관련 조직 업무 및 연구 참여 경로 상담; 현재 직책·채용과 구분','https://itpm.ssu.ac.kr/bbs/board.php?bo_table=faculty','https://biz.ssu.ac.kr/professor/read.do?pType=1&page=2&pf_id=prof14'],
['동국대학교','이창영','서울 · 일반대학원 기술창업학과','개별 연구실명 미확인 / 기술창업학과','e10vs01@dongguk.edu','창업교육·소셜벤처','Co.I를 통한 창업교육·창업팀 검증 지원 효과 연구','학과 창업지원 조직과 연계한 창업교육·사업화 과제 참여 및 학위 병행 상담. 채용 미확인','https://startup.dongguk.edu/professor/list?professor_haggwa_type=PROFH_150','https://startup.dongguk.edu/page/2781'],
['서울미디어대학원대학교','배기태','서울 · 미디어비즈니스학과(공식 교수소개 기준)','산학협력단(공식 소개상 부단장; 현 직책 확인 필요)','ktbae@smit.ac.kr','기술사업화·뉴미디어 서비스·비즈니스 기획','PlaceOS·Co.I의 AI 서비스 사업화·사용자 검증 연구','공식 소개의 산학협력단 경력을 근거로 산학 연구·서비스 개발 업무와 학업 병행 상담. 현재 학위 소속·직책·채용 확인 필요','https://life.smit.ac.kr/sub1_3_b.php','https://sanhak.smit.ac.kr/archive'],
['서강대학교','이상근','서울 · 경영대학 / 대학원 지도 과정 확인','경영학 교육연구단 참여 / MIS','slee1028@sogang.ac.kr','MIS·디지털 기술 활용','PlaceOS·Co.I의 기술 수용·활용 및 디지털 의사결정 연구','MIS 관련 연구·산학 과제의 분석·개발 참여와 학위 병행 상담. 개인 연구소·채용 미확인','https://sbsbk21.sogang.ac.kr/sbsbk21/D_3302_21408.html',''],
['숭실대학교','김광용','서울 · 일반대학원 IT정책경영학과 참여 / 경영학부','개별 연구실명 미확인 / IT정책경영학과','gygim@ssu.ac.kr','빅데이터 분석·감성지능','PlaceOS의 데이터 기반 분석·AI 활용 의사결정 연구','빅데이터·응용 AI 연구 및 과제 개발 업무와 재직 학위 병행 상담. 개인 연구소·채용 미확인','https://itpm.ssu.ac.kr/bbs/board.php?bo_table=faculty','']
];
for(const r of rows){assert(!existing.has(r[4]),'기존 이메일 중복 '+r[1]);assert(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(r[4]));}
const s=wb.worksheets.add('추가_연구·산학협력');
s.getRange('A1').values=[['PlaceOS·Co.I 학술연구 및 산학협력 상담 — 추가 11명']];
s.getRange('A2').values=[['우선순위는 연구 주제의 직접성·관련 조직 근거에 대한 추천 판단입니다. 채용·파트타임 지도 가능성을 뜻하지 않습니다.']];
s.getRange('A3').values=[['기존 202명과 중복 제외. 기존 시트·행·체크 상태는 수정하지 않음. 개별 Lab명이 확인되지 않은 경우 미확인으로 표기.']];
s.getRange('A4').values=[['재직 수업 편의성만으로 선정한 과정과, 기술보호·특허 등 간접 접점 위주 후보는 이번 추가에서 제외했습니다.']];
const data=rows.map((r,i)=>[i+1,...r]);
const headers=['추천 순위','대학교','교수명','캠퍼스·대학원·학과','연구실·연구소·관련 조직','이메일','연구 분야','학술 연구 접점','연구소·산학협력 업무 병행 상담 근거·확인 사항','공식 출처','추가 출처'];
s.getRange('A6:K17').values=[headers,...data];
s.tables.add('A6:K17',true,'ResearchCollaborationContacts');
s.getRange('A6:K17').format.font={name:'Arial',size:10,color:'#172B4D'};
s.getRange('A7:K17').format.wrapText=true;s.getRange('A7:K17').format.rowHeight=85;s.getRange('A7:K17').format.verticalAlignment='center';
s.getRange('A6:K6').format={fill:'#183B56',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:35,verticalAlignment:'center'};
for(const [i,w]of [10,25,15,49,55,40,48,63,88,64,64].entries())s.getRangeByIndexes(5,i,12,1).format.columnWidth=w;
s.getRange('A1').format.font={name:'Arial',size:16,bold:true,color:'#183B56'};
s.getRange('A2:A4').format.font={name:'Arial',size:10,color:'#56677C'};
s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(3);
wb.recalculate();
for(const snap of snapshots){const sh=wb.worksheets.getItem(snap.name);assert.deepEqual(sh.getRange('A1:O180').values,snap.values);assert.deepEqual(sh.getRange('A1:O180').formulas,snap.formulas);}
assert.equal(new Set(rows.map(r=>r[4])).size,11);
await fs.copyFile(file,new URL('PlaceOS_교수_통합명단_연구산학추가전백업.xlsx',dir));
await (await SpreadsheetFile.exportXlsx(wb)).save(fileURLToPath(file));
await fs.writeFile(new URL('research_contacts_preview.png',dir),new Uint8Array(await (await wb.render({sheetName:s.name,range:'A6:H10',scale:1})).arrayBuffer()));
console.log(JSON.stringify({added:11,total:213,existingSheetsPreserved:snapshots.map(s=>s.name),addedSheet:s.name}));
