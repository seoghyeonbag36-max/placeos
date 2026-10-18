import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const out = new URL('./', import.meta.url);
const people = [];
const add = (university, affiliation, source, lines) => {
  for (const line of lines.trim().split('\n')) {
    const [name, lab, email, field] = line.split('|');
    assert(name && lab && email && field, line);
    people.push({university, name, affiliation, lab, email, field, alternate:'', note:affiliation.includes('확인 필요')?'대학원 세부 소속·지원 과정 확인 필요':'', source, extraSource:''});
  }
};
add('연세대학교','정보대학원','https://gsi.yonsei.ac.kr/bbs/board.php?bo_table=sub2_1',`
김희웅|디지털 서비스 연구실|kimhw@yonsei.ac.kr|디지털 서비스·데이터 기반 경영
이준기|ICeT 연구실|zlee@yonsei.ac.kr|디지털 경영·비즈니스 데이터
김남일|디지털혁신 및 기술경영 연구실|namil.kim@yonsei.ac.kr|디지털 혁신·AI 사업화·기술경영
이정훈|ISi 연구실|jhoonlee@yonsei.ac.kr|정보시스템·스마트시티
김하영|MLCF 연구실|hayoung.kim@yonsei.ac.kr|비즈니스 AI·머신러닝
장백철|ANDlab|bjang@yonsei.ac.kr|AI·빅데이터
이웅섭|DAILY Lab|woongsup.lee@yonsei.ac.kr|AI·IoT
이상우|M.C.E 연구실|leesw726@yonsei.ac.kr|콘텐츠·플랫폼 비즈니스
이봉규|IT R&D 연구실|bglee@yonsei.ac.kr|IT·플랫폼 사업
최보름|PACE Lab|boreumchoi@yonsei.ac.kr|플랫폼 비즈니스
신재은|Spatial UX Lab|jaeeunshin@yonsei.ac.kr|공간 경험·UX
오창훈|AX LAB|changhoonoh@yonsei.ac.kr|AI 사용자 경험
`);
add('연세대학교','AI 관련 분야 / 대학원 과정 확인 필요','https://dli.yonsei.ac.kr/team',`
이동하|Data & Language Intelligence Lab|donalee@yonsei.ac.kr|추천·검색·언어모델
`);
add('고려대학교','기술경영전문대학원','https://mot.korea.ac.kr/bbs/board.php?bo_table=sub2_1',`
남기환|미확인|namkh@korea.ac.kr|생성형·설명가능 AI·Business Analytics
윤지환|미확인|towny@korea.ac.kr|기술경영 전략·조직 혁신
김영준|미확인|youngjkim@korea.ac.kr|기술경영·경제성 분석
은준엽|미확인|jeun@korea.ac.kr|시스템 분석·최적화·의사결정
손영우|미확인|ywsohn@korea.ac.kr|첨단기술 비즈니스
김장호|미확인|janghokim@korea.ac.kr|데이터 기반 금융·투자 의사결정
`);
add('고려대학교','경영대학 MIS 분야 / 대학원 과정 확인 필요','https://sites.google.com/korea.ac.kr/mis/faculty',`
이건웅|미확인|leegw@korea.ac.kr|MIS·디지털 기술과 지역경제·기업 생태계
이동원|미확인|mislee@korea.ac.kr|MIS·디지털 비즈니스
홍세준|미확인|sejoon@korea.ac.kr|MIS·정보기술 활용
이재남|미확인|isjnlee@korea.ac.kr|MIS·조직의 정보시스템 활용
고병완|미확인|byungwan@korea.ac.kr|MIS·데이터 기반 경영
이규한|미확인|kyuhanlee@korea.ac.kr|MIS·디지털 비즈니스
정경성|미확인|kyungjung@korea.ac.kr|MIS·정보시스템
최앤젤라애리|미확인|aachoi@korea.ac.kr|MIS·정보시스템
`);
add('한양대학교','기술경영전문대학원','https://cn-mot.hanyang.ac.kr/front/introduce/professor',`
류호경|미확인|hryu@hanyang.ac.kr|인간–AI 협업·의사결정·사용자 중심 혁신
김영민|Machine Learning Lab|yngmnkim@hanyang.ac.kr|머신러닝·확률 그래프·데이터마이닝
최재영|미확인|boogalooaz@hanyang.ac.kr|신기술 수요예측·응용경제
조대명|미확인|dmjo@hanyang.ac.kr|기술가치평가·기술사업화
권규현|미확인|ghkwon@hanyang.ac.kr|가치 기반 시스템 설계·혁신
정태현|미확인|tjung@hanyang.ac.kr|혁신정책·기술경영
이희정|미확인|stdream@hanyang.ac.kr|비정형 데이터·프로세스·의미 분석
김지은|미확인|jkim2@hanyang.ac.kr|서비스화·신제품 개발
한지은|미확인|juliahanje@hanyang.ac.kr|제품·서비스 혁신·데이터 시각화
최원영|미확인|won5475@hanyang.ac.kr|데이터 분석·머신러닝
김우형|미확인|pony30@hanyang.ac.kr|비즈니스·기술 전략
윤정원|미확인|jwyoon78@hanyang.ac.kr|지속가능한 기술혁신·사회혁신
`);
add('한양대학교','컴퓨터소프트웨어·AI 분야 / 대학원 과정 확인 필요','https://cs.hanyang.ac.kr/en/-02-1',`
김상욱|Data Science Lab|wook@hanyang.ac.kr|추천시스템·네트워크·데이터사이언스
김미숙|미확인|misukkim@hanyang.ac.kr|데이터마이닝·자연어처리
김태욱|미확인|kimtaeuk@hanyang.ac.kr|언어모델·에이전트
김은솔|미확인|eunsolkim@hanyang.ac.kr|표현학습·딥러닝
노영균|미확인|nohyung@hanyang.ac.kr|통계적 머신러닝
`);
add('한양대학교','경영대학 / 대학원 과정 확인 필요','https://site.hanyang.ac.kr/web/bizgrad/-3',`
이상용|미확인|tomlee@hanyang.ac.kr|경영정보
이상명|미확인|sanglee@hanyang.ac.kr|경영전략·벤처·혁신관리
이웅희|미확인|victory@hanyang.ac.kr|경영전략·벤처
`);
add('서강대학교','기술경영전문대학원','https://scc.sogang.ac.kr/sogangmot/new_faculties.html',`
박현규|미확인|hp376@sogang.ac.kr|디지털 기업가정신·창업
문성욱|미확인|seongwuk@sogang.ac.kr|데이터 경제·혁신·창업 생태계
우한균|미확인|hwoo@sogang.ac.kr|AI 도입·활용·기술경영
이규태|미확인|kyootai@sogang.ac.kr|혁신전략·신제품·기술이전
박수진|미확인|psjdream@sogang.ac.kr|요구공학·소프트웨어·데이터 활용
`);
add('국민대학교','경영정보·비즈니스IT대학원 관련','https://biz.kookmin.ac.kr/undergraduate/info/professor',`
안현철|KIS Lab|hcahn@kookmin.ac.kr|지능형 의사결정·비즈니스 AI
김남규|DS Lab|ngkim@kookmin.ac.kr|데이터사이언스
곽기영|미확인|kykwahk@kookmin.ac.kr|경영정보·네트워크·지식 활용
박도형|미확인|dohyungpark@kookmin.ac.kr|경영정보·사용자 분석·디지털 비즈니스
`);
add('국민대학교','경영정보 분야 / 대학원 과정 확인 필요','https://biz.kookmin.ac.kr/undergraduate/info/professor',`
박강민|AIMS Lab|gangmin.park@kookmin.ac.kr|AI·경영정보
한윤|미확인|yoonhan@kookmin.ac.kr|경영정보
`);
add('경희대학교','서울캠퍼스 경영·빅데이터응용학과','https://abigdata2.khu.ac.kr/sub02/sub02_1.html',`
김재경|AI Business Lab|jaek@khu.ac.kr|추천시스템·머신러닝·네트워크
이경전|미확인|klee@khu.ac.kr|AI 플랫폼·AI 사업화·창업
양성병|미확인|sbyang@khu.ac.kr|리뷰·비즈니스 분석·CRM·스마트관광
박재홍|미확인|jaehp@khu.ac.kr|인과분석·AI 경제성
권오병|미확인|obkwon@khu.ac.kr|텍스트·빅데이터·AI 활용
김민경|미확인|minkkim@khu.ac.kr|사회적 컴퓨팅·네트워크·머신러닝
김민용|미확인|andy@khu.ac.kr|경영정보시스템
김태경|미확인|tk_kim@khu.ac.kr|데이터사이언스·디지털 서비스
박하은|미확인|gracepark129@khu.ac.kr|생성형 AI·디지털 전환
`);
add('서울대학교','환경대학원','https://gses.snu.ac.kr/en/people/faculty/2',`
김경민|Shared City LAB|kkim2@snu.ac.kr|도시정보·부동산·공간 활용
`);
add('서울대학교','데이터사이언스대학원','https://dsri.snu.ac.kr/people/faculty/',`
박현우|미확인|hyunwoopark@snu.ac.kr|비즈니스 분석·네트워크
김태섭|미확인|taesup.kim@snu.ac.kr|머신러닝·딥러닝
오민환|미확인|minoh@snu.ac.kr|강화학습·통계적 머신러닝
이상원|미확인|swlee69@snu.ac.kr|데이터베이스·ML 데이터 처리
`);
add('서울대학교','컴퓨터공학부 / 대학원 과정 확인 필요','https://cse.snu.ac.kr/en/people/faculty/1',`
강유|Data Mining Lab|ukang@snu.ac.kr|데이터마이닝·그래프·추천
`);
add('서울대학교','지리교육과·데이터사이언스 관련','https://sangillee.snu.ac.kr/',`
이상일|미확인|si_lee@snu.ac.kr|GIS·공간 데이터사이언스
`);
add('서울대학교','경영대학 MIS 분야 / 대학원 과정 확인 필요','https://cba.snu.ac.kr/research/faculty/professor?idx=1261&major=1',`
박진수|미확인|jinsoo@snu.ac.kr|MIS·데이터 통합·의미적 상호운용성
`);
add('성균관대학교','서울캠퍼스 경영대학 경영정보 분야 / 대학원 과정 확인 필요','https://biz.skku.edu/eng_bizskk/faculty.do',`
변종복|미확인|jbyun@skku.edu|전자상거래·창업·데이터 분석
허윤영|미확인|yunyounghur@skku.edu|AI 활용의 효과·현장 실험
김용석|미확인|yongskim@skku.edu|디지털 플랫폼·소셜네트워크·크라우드펀딩
복기우|미확인|gwbock@skku.edu|지식관리·비즈니스 인텔리전스
장영봉|미확인|ybchang01@skku.edu|정보기술의 경제적 효과
경나경|미확인|knkyung@skku.edu|디지털 플랫폼·정보시스템
`);
add('동국대학교','서울캠퍼스 경영정보학과 / 대학원 과정 확인 필요','https://sba.dongguk.edu/professor/list?professor_haggwa_type=PROFH_029',`
김경재|미확인|kjkim@dongguk.edu|비즈니스 인텔리전스·데이터마이닝·CRM
이규민|미확인|gyuminlee@dgu.ac.kr|데이터 분석·자연어처리·기술경영
윤상혁|미확인|yoonsh@dgu.ac.kr|생성형 AI·빅데이터
권소연|미확인|miskwon@dongguk.edu|HCI·소셜미디어 분석
`);
add('서울과학기술대학교','데이터사이언스학과','https://data.seoultech.ac.kr/professor/prof',`
이학연|미확인|hylee@seoultech.ac.kr|기술경영·데이터 기반 비즈니스
이영훈|미확인|yhoon.lee@seoultech.ac.kr|추천·자연어처리·사용자 분석
박규태|미확인|kt.park@seoultech.ac.kr|디지털 트윈·시뮬레이션
김경옥|미확인|kyoungok.kim@seoultech.ac.kr|데이터마이닝
조남욱|미확인|nwcho@seoultech.ac.kr|소셜네트워크·비즈니스 프로세스
황상흠|미확인|shwang@seoultech.ac.kr|AI·딥러닝
권혁윤|미확인|hyukyoon.kwon@seoultech.ac.kr|빅데이터·데이터 기반 AI
정진우|미확인|jinw.jeong@seoultech.ac.kr|HCI·사용자 상호작용
이택호|미확인|taekho.lee@seoultech.ac.kr|응용 AI·연합학습
`);
add('KAIST','서울 경영대학 / 지원 대학원 과정 확인 필요','https://www.business.kaist.ac.kr/_prog/prof/index.php?div_cd=C02006&menu_dvs_cd=0501&site_dvs_cd=en',`
박성혁|미확인|sunghyuk.park@kaist.ac.kr|예측 분석·AI·추천시스템
오원석|미확인|wonseok.oh@kaist.ac.kr|IT 경제학·AI 비즈니스·디지털 마케팅
강금석|미확인|keumkang@kaist.ac.kr|정보시스템·비즈니스 분석·AI
신동혁|미확인|dhs@kaist.ac.kr|AI 경제성·비즈니스 응용
`);
add('건국대학교','경영대학·대학원 기술경영학과','https://sites.google.com/view/t-h-i-n-k-lab/introduction/academic-advisor',`
송영화|T.H.I.N.K LAB|sawng@konkuk.ac.kr|기술사업화·혁신·벤처
`);
add('건국대학교','기술경영학과','https://ki-it.com/xml/42047/42047.pdf',`
박재민|미확인|jpark@konkuk.ac.kr|기술경영·기술혁신·ICT 활용
`);
add('서울시립대학교','공간정보공학과 / 대학원 과정 확인 필요','https://pure.uos.ac.kr/en/organisations/college-of-urban-science/persons/',`
구형모|미확인|hmokoo@uos.ac.kr|공간 데이터 분석
전철민|미확인|cmjun@uos.ac.kr|GIS·공간정보
`);
add('한국외국어대학교','서울캠퍼스 경영정보 관련 / 대학원 과정 확인 필요','https://ssai.hufs.ac.kr/profl/ssai/575/3496/artclView.do',`
최형용|미확인|hchoi@hufs.ac.kr|디지털 혁신·빅데이터·IT 전략
`);
add('한국외국어대학교','서울캠퍼스 경영대학 경영정보 분야 / 대학원 과정 확인 필요','https://biz.hufs.ac.kr/profl/biz/420/2114/artclView.do',`
조준서|미확인|jscho@hufs.ac.kr|데이터마이닝·CRM·전자상거래·스마트시티
`);
add('숙명여자대학교','경영·MBA 관련 / 지원 대학원 과정 확인 필요','https://mba.sookmyung.ac.kr/profl/mba2/51/384/artclView.do',`
권영옥|미확인|yokwon@sm.ac.kr|빅데이터·비즈니스 분석
`);
add('숙명여자대학교','소프트웨어학부 / 대학원 과정 확인 필요','https://ds.sookmyung.ac.kr/software/5889/subview.do',`
이기용|미확인|kiyonglee@sm.ac.kr|데이터베이스·데이터마이닝
심준호|미확인|jshim@sm.ac.kr|데이터베이스·빅데이터
유석종|미확인|sjyu@sm.ac.kr|정보 시각화·머신러닝
`);
add('이화여자대학교','경영대학 경영정보 분야 / 지원 대학원 과정 확인 필요','https://gsb.ewha.ac.kr/gsb/faculty/management-information-system.do?articleNo=10664&mode=view',`
채상미|미확인|smchai@ewha.ac.kr|경영정보·모바일 비즈니스·사용자 행동
`);
add('세종대학교','AI·데이터사이언스 분야 / 대학원 과정 확인 필요','https://dept.sejong.ac.kr/aidsdpt/intro/professor.do',`
최우석|미확인|wschoi@sejong.ac.kr|도시·스마트시티·멀티모달 데이터
박동현|미확인|parkdh@sejong.ac.kr|언어모델·추천시스템
오상진|미확인|osjin@sejong.ac.kr|기술예측·기술정책·온톨로지
`);
const ssuSource='https://ensb.ssu.ac.kr/%EA%B5%90%EC%88%98%EC%A7%84%EC%86%8C%EA%B0%9C/%EC%A0%84%EC%9E%84%EA%B5%90%EC%88%98/';
add('숭실대학교','벤처중소기업학과 / 대학원 과정 확인 필요',ssuSource,`
원청연|미확인|clearlake@ssu.ac.kr|응용미시계량·정책효과 분석
`);
const initialCount=people.length;
const initialKeys=people.map(p=>p.university+'|'+p.name);

add('국민대학교','글로벌창업벤처대학원','https://gsge.kookmin.ac.kr/GSGE2014/introduction/faculty.do',`
박범서|미확인|bspark@kookmin.ac.kr|AI 데이터 분석·마케팅·전략·AI비즈니스이노베이션
이우진|미확인|drlee@kookmin.ac.kr|기업가정신·창업교육·조직이론
김도현|미확인|drkim@kookmin.ac.kr|전략·기업가정신·스타트업
황보윤|미확인|yun88@kookmin.ac.kr|창업·스타트업 투자·사내기업가정신
김종성|미확인|01041603713@kookmin.ac.kr|창업보육·기업가정신·캠퍼스타운
김성일|미확인|ksi@kookmin.ac.kr|창업교육·창업투자·지산학협력·커뮤니티
김종택|미확인|jtkim@kookmin.ac.kr|회계·재무·창업투자
`);
const hySource='https://startup-gse.hanyang.ac.kr/introduce/professor';
add('한양대학교','창업대학원',hySource,`
류창완|미확인|ryoocw@hanyang.ac.kr|기업가정신·신규 벤처 창출
`);
add('한양대학교','창업대학원·일반대학원 창업융합학과',hySource,`
배태준|미확인|tjbae@hanyang.ac.kr|기업가정신·창업
`);
add('한양대학교','창업대학원 참여교수',hySource,`
권규현|미확인|ghkwon@hanyang.ac.kr|가치 기반 혁신
정태현|미확인|tjung@hanyang.ac.kr|기술혁신 전략·경영
조대명|미확인|dmjo@hanyang.ac.kr|기술가치평가
한지은|미확인|juliahanje@hanyang.ac.kr|제품·서비스 혁신
이상명|미확인|sanglee@hanyang.ac.kr|경영전략·혁신관리
이명훈|미확인|mhlee99@hanyang.ac.kr|도시재생
`);
add('숭실대학교','중소기업대학원·벤처중소기업학과',ssuSource,`
서리빈|미확인|ribinseo@ssu.ac.kr|기업가정신·기술혁신·벤처금융
한용희|미확인|amade@ssu.ac.kr|AI
최자영|미확인|choi181@ssu.ac.kr|마케팅
유재원|미확인|yjw1774@ssu.ac.kr|마케팅
신상윤|미확인|stg@ssu.ac.kr|전략·국제경영
연규철|미확인|kcyeon@ssu.ac.kr|창업·중소기업 경영혁신
`);
add('숭실대학교','벤처중소기업학과',ssuSource,`
김영수|미확인|bukys@ssu.ac.kr|창업·벤처경영·기업가정신
박주영|미확인|jpark@ssu.ac.kr|유통·프랜차이즈·마케팅
원청연|미확인|clearlake@ssu.ac.kr|응용미시계량·정책효과 분석
`);
add('중앙대학교','일반대학원 창업학과','https://caugs.cau.ac.kr/graduate/department/startup/faculty.do',`
박재환|미확인|jaypark@cau.ac.kr|비즈니스모델·사회적 기업·기업혁신
류승완|미확인|rush2384@cau.ac.kr|경영과학·서비스운영관리·기술경영
`);
add('호서대학교','글로벌창업대학원(서울)','https://leader.hoseo.ac.kr/CmsHome/Intro_04.eznic',`
문남미|해당 과정의 Lab 명칭 미확인|mnm@hoseo.edu|AI·추천시스템·AI와 창업 연구 연결 상담
`);
add('서울벤처대학원대학교','융합산업학과 경영학전공','https://www.svu.ac.kr/department/department.php',`
박현숙|미확인|hspark@svu.ac.kr|벤처경영·사업화·마케팅
`);
const additionCount=people.length-initialCount;
const additionKeys=people.slice(initialCount).map(p=>p.university+'|'+p.name);
const unique=new Map();
for(const p of people){
  const key=p.university+'|'+p.name;
  if(!unique.has(key)){unique.set(key,{...p});continue;}
  const prev=unique.get(key);
  if(!prev.affiliation.includes(p.affiliation))prev.affiliation+='; '+p.affiliation;
  if(prev.source!==p.source)prev.extraSource=p.source;
  if(prev.email!==p.email)prev.alternate=p.email;
  prev.field=[...new Set([...prev.field.split('·'),...p.field.split('·')])].join('·');
}
const rows=[...unique.values()];
const patchPerson=(uni,name,patch)=>Object.assign(unique.get(uni+'|'+name),patch);
patchPerson('중앙대학교','류승완',{alternate:'ryu@cau.ac.kr',note:'이전 답변의 두 이메일을 모두 보존. 교수진 최신 안내에는 rush2384 주소가 표시됨.',extraSource:'https://mba.cau.ac.kr/about/faculty.php'});
patchPerson('중앙대학교','박재환',{extraSource:'https://mba.cau.ac.kr/about/faculty.php'});
patchPerson('서강대학교','박현규',{extraSource:'https://www.sogangtech.com/researcher/2314'});
patchPerson('서강대학교','문성욱',{extraSource:'https://www.sogangtech.com/researcher/2315'});
patchPerson('서강대학교','우한균',{extraSource:'https://www.sogangtech.com/researcher/2316'});
patchPerson('서강대학교','이규태',{extraSource:'https://www.sogangtech.com/researcher/2313'});
patchPerson('서강대학교','박수진',{extraSource:'https://scc.sogang.ac.kr/front/boardview.do?bbsConfigFK=21&pkid=877186&siteId=sogangmot',note:'이메일 근거는 이전 공식 안내. 발송 전 재확인 권장.'});
patchPerson('경희대학교','이경전',{extraSource:'https://bigdata21.khu.ac.kr/main/main03.html'});
patchPerson('경희대학교','양성병',{extraSource:'https://bigdata21.khu.ac.kr/main/main03.html'});
patchPerson('서울대학교','이상원',{extraSource:'https://gsds.snu.ac.kr/people-post/sang-won-lee/'});
patchPerson('한양대학교','김영민',{extraSource:'https://site.hanyang.ac.kr/web/mllab/professor'});
patchPerson('한양대학교','김상욱',{extraSource:'https://bigdas.hanyang.ac.kr/sang-wook/'});
for(const n of ['김태욱','김은솔','노영균'])patchPerson('한양대학교',n,{extraSource:'https://nextai.hanyang.ac.kr/en/people/professor/'});
for(const n of ['서리빈','한용희','최자영','유재원','신상윤','연규철'])patchPerson('숭실대학교',n,{extraSource:'https://small.ssu.ac.kr/introduce/professor'});

assert(!rows.some(p=>p.name==='김범수'));
assert.equal(rows.length,new Set(rows.map(p=>p.university+'|'+p.name)).size);
for(const key of [...initialKeys,...additionKeys])assert(unique.has(key),key);
for(const p of rows)assert(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(p.email),p.email);
const universities=new Set(rows.map(p=>p.university));
await fs.writeFile(new URL('manifest.json',out),JSON.stringify({initialCount,additionCount,total:rows.length,universityCount:universities.size,initialKeys,additionKeys,people:rows},null,2));

const wb=Workbook.create();
const sheet=wb.worksheets.add('교수명단');
sheet.showGridLines=false;
sheet.tabColor='#183B56';
const headers=['번호','대학교','교수명','대학원·학과·참여 과정','연구실명','연구 분야·PlaceOS 접점','이메일','추가 이메일','확인 사항','출처 URL','추가 출처 URL'];
sheet.getRange('A2').values=[['PlaceOS 대학원 교수 연락처']];
sheet.getRange('A3').values=[[`대화 명단 통합 ${rows.length}명 · ${universities.size}개 대학 · 2026-10-18 작성`]];
sheet.getRange('A4').values=[['기존 대화의 조사 내용을 통합한 파일입니다. 미확인 소속·연구실은 그대로 표시했으며 파트타임 지도 가능 여부는 개별 문의가 필요합니다.']];
sheet.getRange('A5').values=[['중복 교수는 한 행에 통합했습니다. 연세대학교 AI SPR Lab 김범수 교수는 요청에 따라 제외했습니다.']];
const data=rows.map((p,i)=>[i+1,p.university,p.name,p.affiliation,p.lab,p.field,p.email,p.alternate,p.note,p.source,p.extraSource]);
sheet.getRange(`A7:K${7+data.length}`).values=[headers,...data];
const table=sheet.tables.add(`A7:K${7+data.length}`,true,'ProfessorContacts');
table.showFilterButton=true;
sheet.getRange(`A7:K${7+data.length}`).format.font={name:'Arial',size:10,color:'#172B4D'};
sheet.getRange(`A8:K${7+data.length}`).format.rowHeight=58;
sheet.getRange(`A8:K${7+data.length}`).format.wrapText=true;
sheet.getRange(`A8:K${7+data.length}`).format.verticalAlignment='center';
const widths=[7,24,17,55,43,59,42,33,61,65,65];
for(let c=0;c<widths.length;c++)sheet.getRangeByIndexes(6,c,data.length+1,1).format.columnWidth=widths[c];
sheet.getRange(`G8:H${7+data.length}`).setNumberFormat('@');
sheet.getRange('A7:K7').format={fill:'#183B56',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center',verticalAlignment:'center',wrapText:true};
sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#183B56'};
sheet.getRange('A3:A5').format.font={name:'Arial',size:10,color:'#56677C'};
sheet.getRange('A3:A5').format.wrapText=false;
sheet.getRange('A2:A5').format.rowHeight=23;
sheet.freezePanes.freezeRows(7);
sheet.freezePanes.freezeColumns(3);
sheet.getRange(`E8:E${7+data.length}`).conditionalFormats.add('containsText',{text:'미확인',format:{fill:'#FFF2CC',font:{color:'#805B00'}}});
sheet.getRange(`D8:D${7+data.length}`).conditionalFormats.add('containsText',{text:'확인 필요',format:{fill:'#FFF2CC'}});

const agency=wb.worksheets.add('기관 문의');
agency.showGridLines=false;
agency.tabColor='#6B8299';
agency.getRange('A2').values=[['대학원·학과 공용 문의 연락처']];
agency.getRange('A3').values=[['교수 개인 이메일과 구분하여 보존한 대학원·학과·입시 담당 연락처입니다.']];
const agencies=[
['연세대학교','정보대학원','공용 문의','gsi@yonsei.ac.kr','','https://gsi.yonsei.ac.kr/sub2_5.php'],
['고려대학교','기술경영전문대학원','공용 문의','mot@korea.ac.kr','','https://mot.korea.ac.kr/bbs/board.php?bo_table=sub2_1'],
['서강대학교','기술경영전문대학원','공용 문의','sgmot@sogang.ac.kr','','https://scc.sogang.ac.kr/sogangmot/new_faculties.html'],
['국민대학교','글로벌창업벤처대학원','공용 문의','gsge@kookmin.ac.kr','','https://kmu-gsge.kr/'],
['경희대학교','빅데이터응용학과','공용 문의','bigdata21@khu.ac.kr','','https://bigdata21.khu.ac.kr/main/main03.html'],
['한양대학교','창업대학원','공용 문의','startupgse@hanyang.ac.kr','','https://startup-gse.hanyang.ac.kr/introduce/professor'],
['숭실대학교','중소기업대학원','공용 문의','small@ssu.ac.kr','','https://small.ssu.ac.kr/'],
['숭실대학교','벤처중소기업학과','공용 문의','venture@ssu.ac.kr','','https://ensb.ssu.ac.kr/'],
['중앙대학교','일반대학원 창업학과','공용 문의','caugs77@cau.ac.kr','','https://caugs.cau.ac.kr/graduate/department/startup/faculty.do'],
['중앙대학교','창업경영대학원 서울 교학지원팀','공용 문의','','02-820-6937~6938. 서울·안성 수업 장소 확인 필요.','https://iem.cau.ac.kr/am/am_7.php'],
['호서대학교','글로벌창업대학원(서울)','입시 담당 이재현','ljh@hoseo.edu','','https://leader.hoseo.ac.kr/CmsHome/Intro_04.eznic']
];
agency.getRange(`A5:F${5+agencies.length}`).values=[['대학교','대학원·학과','구분·담당','이메일','전화·확인 사항','출처 URL'],...agencies];
const at=agency.tables.add(`A5:F${5+agencies.length}`,true,'InstitutionContacts');at.showFilterButton=true;
agency.getRange(`A5:F${5+agencies.length}`).format.font={name:'Arial',size:10,color:'#172B4D'};
agency.getRange(`A6:F${5+agencies.length}`).format.rowHeight=44;
agency.getRange(`A6:F${5+agencies.length}`).format.wrapText=true;
agency.getRange(`A5:F${5+agencies.length}`).format.verticalAlignment='center';
for(const [i,width] of [25,43,25,40,65,75].entries())agency.getRangeByIndexes(4,i,agencies.length+1,1).format.columnWidth=width;
agency.getRange('A5:F5').format={fill:'#183B56',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center'};
agency.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#183B56'};
agency.getRange('A2').format.rowHeight=28;
agency.getRange('A3').format.font={name:'Arial',size:10,color:'#56677C'};
agency.freezePanes.freezeRows(5);
wb.recalculate();
assert.deepEqual(sheet.getRange(`C8:C${7+data.length}`).values.map(r=>r[0]),rows.map(p=>p.name));
assert.equal(sheet.tables.items.length,1);
console.log(JSON.stringify({initialCount,additionCount,total:rows.length,universities:universities.size,institutionContacts:agencies.length}));
console.log((await wb.inspect({kind:'table',range:'교수명단!A7:H11',include:'values',tableMaxRows:5,tableMaxCols:8,maxChars:1800})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(fileURLToPath(new URL('PlaceOS_교수_통합명단.xlsx',out)));
for(const [name,range,file] of [['교수명단','A2:G12','professors_preview.png'],['기관 문의','A2:E12','institutions_preview.png']]){
 const image=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(new URL(file,out),new Uint8Array(await image.arrayBuffer()));
}
