"""00~05 페이지 생성. 숫자는 verify/ 의 실호출 산출물과 main 의 커밋된 보고서에서만 읽는다."""
import json
import statistics as st
import sys
from pathlib import Path

from gen_common import FILES, chip, esc, heat_table, man, page, status_bars
import menu_data as MD
import menu_plan as MP

S = Path(sys.argv[1])          # 실험 폴더(data/ 가 있는 곳)
OUT = Path(sys.argv[2])
EX = json.loads((S / "data" / "examples_data.json").read_text())
UNITS = json.loads((S / "data" / "units_raw.json").read_text())
UC = json.loads((S / "data" / "use_check_vacant_seoul_2026-11-15.json").read_text())
SC = {r["label"]: r for r in EX["scenarios"]}
P2 = EX["p2"]
SUM = EX["summary"]
BIN = ["<1", "1-3", "3-6", "6-12", "12-24", ">=24"]
BIN_LAB = ["1개월 미만", "1~3개월", "3~6개월", "6~12개월", "12~24개월", "24개월 이상"]
TK = {"premium": "고급화", "value": "가성비", "factory": "기능중심"}
OPEX = {k: P2["opex"][v] for k, v in TK.items()}
KOS = {k: P2["kosis_store_month"][v] for k, v in TK.items()}
L = {f[0]: f for f in FILES}


def link(fname):
    f = L[fname]
    return f'<a href="{f[0]}">{f[1]} · {f[2]}</a>'


def scen_rows(labels):
    rows = []
    for lab, note in labels:
        r = SC[lab]
        rows.append((lab, [r["bins"][b] for b in BIN], f'중앙 {r["median"]}개월 · 사분위 {r["q1"]}~{r["q3"]}개월{" · " + note if note else ""}'))
    return rows


SCEN_ALL = [("현행 손 계수(재현)", "지금 화면"), ("투자비 ×2", ""), ("투자비 ×3", ""), ("투자비 ×5", ""), ("투자비 ×8", ""),
            ("인테리어 서울 평균 5,450만원(면적 무관)", "서울시 2025 가맹사업 등록현황"),
            ("외식업 창업비용 서울 평균 9,610만원(면적 무관)", "같은 자료")]


def req(rent, tier, days=26):
    m = rent / (1 - OPEX[tier])
    return m, m / days, m / KOS[tier]


# ───────────────────────── 00 검증 · 목차
def p00():
    base = SC["현행 손 계수(재현)"]; s545 = SC["인테리어 서울 평균 5,450만원(면적 무관)"]
    body = f"""
<div class="callout ok">
<p><b>한 줄 결론</b> — 「왜 바꾸나」의 세 원인은 <b>모두 사실</b>입니다. main 코드를 읽고 서빙 코드를 직접 다시 돌려 확인했습니다.
고칠 숫자가 둘 있고(분모 891 · Page 근사값), 새로 보인 사실이 하나 있습니다 — 회수기간이 짧게 나오는 이유는 <b>투자비 손 계수와 면적 비례 매출 두 가지</b>라서,
투자비만 바꾸면(P1) 「한 달 안에 본전」은 거의 사라지지만 회수기간은 여전히 낙관적입니다. 그래서 머리 문장을 요구치로 바꾸는 P2 가 필요합니다.</p>
</div>

<div class="callout decide">
<p><b>결정 ①~④ 는 대부분 이미 정해졌습니다</b> — 11-15 결정 기록(<code>docs/decision-confirm-before-contract-2026-11-15.md</code>):
① 투자비 실측 {chip("승인", "ok")} · ② 네 질문·정체성 {chip("승인 — Platform 문구는 현행 유지", "ok")} ·
③-b 오프라인 마케팅 「개업 뒤」 {chip("승인·시행", "ok")} · ③-a 인테리어 3D 선택 칸 {chip("보류 — 유일한 미결", "decide")} ·
④ 처리방침 목적 추가 {chip("승인 · 착수 미정", "ok")}.
그래서 01~04 파일은 「정할지」보다 <b>정한 대로 하면 화면·숫자가 어떻게 달라지는지</b>를 예시로 보여 줍니다. ③-a 만 선택지를 나란히 놓았습니다.</p>
</div>

<h2>1. 주장별 검증표</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">인계 문서의 주장</th><th scope="col">확인한 것 (근거)</th><th scope="col">판정</th></tr></thead>
<tbody>
<tr><th scope="row">개발자 모임 피드백(11-15) — 「Posting·Program 이 산으로 간다, 숫자가 가설이다」</th>
<td>저장소 밖 사실이라 다시 잴 수 없습니다. 같은 내용이 결정 문서 §0 에 기록돼 있습니다.</td><td>{chip("기록 일치", "mute")}</td></tr>
<tr><th scope="row">원인 1 · 질문이 바뀐다 — Posting 은 「어느 전략」을 묻는다</th>
<td>Posting 콘솔 질문 「어떤 비용과 전략으로 입점할까요?」(<code>pages/PostingConsole.tsx</code>) ·
흐름 R5 제목 「{{가격대}} 하면 {{n개월이면}} 본전이에요」(<code>flow/screens/Cost.tsx</code>) · 랜딩 Posting 질문 「얼마짜리 자리가 맞지?」.
<br><span class="src">단서: 「Platform·Page 는 실측으로 답한다」는 <b>대체로</b> 맞습니다. 빈 층(대장 기준)은 실측이지만, Page 의 층별 월 임대료는 R-ONE 추정에 층 계수를 곱한 <b>추정</b>이고,
Platform 순위는 업종 모델 평균입니다(결과 대조 첫 계산은 구분불가 — 11-15 finding).</span></td><td>{chip("맞음", "ok")}</td></tr>
<tr><th scope="row">원인 2 · 결론 숫자가 추정 네 겹이다</th>
<td><code>districts.tier_scenarios</code>: 투자비 = 권리금 + 면적 × 계수 + 고정비 — 계수는 손으로 적은 값(고급화 평당 55만원+400만원 · 가성비 32만원+220만원 · 기능중심 20만원+110만원).
매출 = 면적 × 평당 매출(서울시 상권분석 상대 수준 × KOSIS 점포당 매출 ÷ 공정위 평균 면적), 비용 = 월세 + 매출 × KOSIS 비임차 비용률(0.87~0.88).</td><td>{chip("맞음", "ok")}</td></tr>
<tr><th scope="row">「추천 전략 회수 1개월 미만 296/891」</th>
<td>서빙 코드 실호출 스냅샷을 다시 돌림(<code>scripts/posting_payback_snapshot.py</code>) — <b>{base["lt1"]}곳</b>, 중앙 {base["median"]}개월로 11-15 값과 같습니다.
화면 문장도 확인: 이 {base["lt1"]}곳에서 R5 가 「한 달 안에 본전이에요」라고 말합니다(<code>flow/format.ts</code> 의 <code>months()</code>).
<br><span class="src">분모 891 은 재현되지 않습니다. 셀 수 있는 분모는 <b>854</b>(자료 있는 유닛) · <b>836</b>(추천 있는 유닛)입니다 → 「296/836(35.4%)」로 인용하세요.</span></td><td>{chip("분자 맞음 · 분모 고침", "decide")}</td></tr>
<tr><th scope="row">원인 3 · Posting 7쪽 중 「주변 업종 지도」「찾아오는 길」은 Page 성격</th>
<td>Posting 콘솔 7쪽: 시뮬레이션 결과 · 상권 맞춤 인테리어 · 주변 업종 지도 · 찾아오는 길 · 위험 확인 · 메뉴 설정 · 비용 비교 및 결정.</td><td>{chip("맞음", "ok")}</td></tr>
<tr><th scope="row">Page 근거 — 빈 층 14,520 중 1종 근생 7,548(52%) · 2종 5,655(39%)</th>
<td>Gold 전수로 다시 세면 서울 빈 층 <b>14,517</b>곳. 대장 용도코드 기준 1종 <b>{UC["ledger_ho"]["제1종 근린생활시설"]:,}</b>(51.5%) · 2종 <b>{UC["ledger_ho"]["제2종 근린생활시설"]:,}</b>(41.3%)
(<code>reports/use_check_vacant_seoul_2026-11-15.json</code>). 인계 문서 값은 키워드 근사라 2종이 334곳 적습니다.</td><td>{chip("근사로 맞음 · 정확값으로 인용", "decide")}</td></tr>
<tr><th scope="row">「메뉴 설정이 이미 하루 판매량을 계산한다」</th>
<td><code>lib/menuPlan.ts</code> 의 <code>menuBep</code> — (월세 + 기타 고정비) ÷ (1 − 원가율) ÷ 객단가 ÷ 영업일. 기본값은 일부러 넣지 않습니다.</td><td>{chip("맞음", "ok")}</td></tr>
<tr><th scope="row">P1 원천 — 공정위 정보공개서에 인테리어·초기비용 필드가 있나</th>
<td>지금 쓰는 서비스(공공데이터 15110241 「브랜드별 가맹점 현황」)는 평균 매출·면적 단위 매출만 줍니다. 공공데이터 목록상 <b>15143711 「가맹사업자 부담금·인테리어비용」</b>에
단위면적 인테리어 금액 · 인테리어 금액 · 점포 기준면적 · 가맹금 항목이 있습니다.
<br><span class="src">1콜 실측은 <b>미실행</b> — 이 환경에서 키 확인 명령이 권한 정책에 막혔습니다. P1 착수 첫 단계로 남깁니다.</span></td><td>{chip("원천 있음(목록 기준)", "info")}</td></tr>
</tbody></table></div>

<h2>2. 새로 보인 것 — 회수기간이 짧게 나오는 두 지렛대</h2>
<div class="tiles">
<div class="tile"><div class="k">추천 전략 투자비 중앙(현행 손 계수)</div><div class="v">{SUM["inv_q"][1]:,}<small>만원</small></div>
<div class="s">서울 외식업 가맹점 평균 창업비 9,610만원의 약 1/8.5 · 인테리어 평균 5,450만원의 약 1/5</div></div>
<div class="tile"><div class="k">추천 전략 월매출 중앙(추정)</div><div class="v">{SUM["rev_q"][1]:,}<small>만원/월</small></div>
<div class="s">연 {SUM["rev_q"][1] * 12 / 10000:.1f}억 — 공정위 외식업 가맹점 평균 연 3.51억 · 서울 가맹점 평균 연 4.2억의 약 3배</div></div>
<div class="tile"><div class="k">빈 층 면적 중앙 vs 가맹점 평균 면적</div><div class="v">{P2["area_med"]}<small>평 vs 17~21평</small></div>
<div class="s">매출이 면적에 그대로 비례(고정항 없음) — 큰 층일수록 매출이 커진다</div></div>
</div>
<p>투자비만 서울 인테리어 평균(5,450만원)으로 바꿔 다시 세면 「1개월 미만」은 {base["lt1"]} → <b>{s545["lt1"]}</b>곳으로 줄지만, 회수 중앙은 {base["median"]} → <b>{s545["median"]}</b>개월에 그칩니다.
매출 추정이 그대로이기 때문입니다. 자세한 계산은 {link("placeos-01-invest.html")}, 전/후는 {link("placeos-05-before-after.html")}.</p>
<p class="src">매출 계산에 분기·월 단위 실수는 없습니다(KOSIS 연매출 ÷ 사업체 수 ÷ 12). 부풀림은 「빈 층 면적 × 평당 매출」에서 옵니다.</p>

<h2>3. 아직 배포 안 된 브랜치와 겹치는 곳</h2>
<p><code>claude/twin-roads</code>(5d25a37 · Page·Posting 보강 11개)는 main 보다 31커밋 뒤에 있습니다. 인계 작업과 겹치는 부분을 이렇게 정리하면 중복 없이 이어집니다.</p>
<div class="tbl"><table>
<thead><tr><th scope="col">브랜치 기능</th><th scope="col">닿는 인계 작업</th><th scope="col">처리 권장</th></tr></thead>
<tbody>
<tr><th scope="row">N1 인테리어·설비 견적 입력</th><td>P1 · P3</td><td>유지 — 사용자 견적이 공정위 평균보다 앞선다(P3 원칙)</td></tr>
<tr><th scope="row">N3 계약 월세·보증금 입력 · 환산보증금 판정</th><td>P3 들은 금액</td><td>유지 — R-ONE 은 「참고 범위」로 내린다</td></tr>
<tr><th scope="row">N6 민감도(매출 −10~30% · 월세 +5% → 회수기간)</th><td>P2 요구치</td><td><b>고쳐서</b> 유지 — 회수기간 대신 「하루 몇 개」 기준으로</td></tr>
<tr><th scope="row">N7 인건비 도우미 · N10 카드수수료·간이과세</th><td>P2 고정비·변동비</td><td>유지 — 요구치 입력칸으로 옮김</td></tr>
<tr><th scope="row">N9 개·폐업률 · N11 계약 전 체크리스트</th><td>Posting ③ 계약 전 확인</td><td>유지 — 체크리스트에 입점 점검 결과를 자동으로 채운다</td></tr>
<tr><th scope="row">N2 층 용도로 본 음식점 영업</th><td>2-E 입점 점검</td><td><b>철회</b> — main 의 <code>use_check</code>(다섯 갈래·토지이음 포함)가 정본</td></tr>
<tr><th scope="row">N4 공실 이력 요약 · N5 월세·면적 필터 · N8 건물 연식</th><td>2-A 자리 사실</td><td>유지 — Page 층 상세의 자리 사실로</td></tr>
</tbody></table></div>
<p class="src">main 에 들어간 뒤 바뀐 곳(<code>PostingConsole.tsx</code> · <code>MapShell.tsx</code> · <code>lib/api.ts</code>)에서 충돌이 예상됩니다. 배포 전에 main 위로 다시 맞춰야 합니다.</p>

<h2>4. 이 묶음의 예시 파일</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">파일</th><th scope="col">다루는 것</th><th scope="col">예시 방법</th></tr></thead>
<tbody>
<tr><td>{link("placeos-01-invest.html")}</td><td>투자비를 공정위 실측으로 (P1)</td><td>실제 자리 3곳 계산 대조 · 836곳 분포 구간표 · 원천 필드 대조</td></tr>
<tr><td>{link("placeos-02-questions.html")}</td><td>네 질문 · 정체성 문장</td><td>화면 문구 전/후 목업 · 실제 자리 머리 문장 · 예비창업자 대화</td></tr>
<tr><td>{link("placeos-03-interior-marketing.html")}</td><td>인테리어 3D · 오프라인 마케팅 칸</td><td>눌러 보는 탭 목업(A·B·C 안) · 장단점 표</td></tr>
<tr><td>{link("placeos-04-privacy.html")}</td><td>처리방침 목적 추가</td><td>문구 비교 · 동의 화면 목업 · 데이터 흐름도</td></tr>
<tr><td>{link("placeos-05-before-after.html")}</td><td>작업 뒤 결과 예측</td><td>지표 타일 · 작업별 전/후 표 · 구간표 · 상태 막대</td></tr>
<tr><td>{link("placeos-06-menu-fill.html")}</td><td>메뉴 「예시 채우기」 v2 — 준비물(한 번 · 주기별) · 발주 계획 · 개업 첫 주문</td><td>직접 눌러 보는 시제품(업종 6 × 가격대 3 · 채우기 방식 3)</td></tr>
</tbody></table></div>

<h2>5. 다시 재는 방법 · 한계</h2>
<pre><code># main 을 따로 받아(작업 트리 영향 없음) 서빙 코드를 실호출
git worktree add --detach ../placeos-main origin/main
cd ../placeos-main
python scripts/posting_payback_snapshot.py --label recheck --out /tmp/recheck.json   # 296 · 중앙 1.5개월
# 빈 층 판정 분포(커밋된 산출물): reports/use_check_vacant_seoul_2026-11-15.json</code></pre>
<ul>
<li>P1 시나리오(투자비 ×2·×3·… · 서울 평균)는 <b>예측</b>입니다 — 매출·월세는 그대로 두고 투자비만 바꿔 다시 셌습니다. P1 구현 뒤 값은 같은 스크립트로 다시 잽니다.</li>
<li>입점 점검 분포 재실행은 이 환경에 층 대장 원천(bronze)이 없어 0건이었습니다. 11-15 커밋 산출물을 인용했고, 빈 층 수 14,517 은 Gold 전수로 다시 확인했습니다.</li>
<li>공정위 15143711 의 1콜 확인과 외부 시세(참가격·KAMIS 원자료)는 이 환경에서 직접 부르지 않았습니다 — 공개 보도·목록으로 확인한 값입니다.</li>
</ul>
<p class="src">출처: <a href="https://www.data.go.kr/data/15143711/openapi.do">공공데이터포털 15143711</a> ·
<a href="https://www.hankyung.com/article/202606229186Y">서울시 2025 가맹사업 등록현황 보도(한국경제)</a> ·
<a href="https://mobile.newsis.com/view/NISX20260411_0003587198">공정위 2025 가맹사업 현황(뉴시스)</a></p>
"""
    return page("placeos-00-verify.html", "왜 바꾸나 검증", "「왜 바꾸나」 검증 결과와 예시 목차",
                "업로드하신 인계 문서(2026-11-15)의 「1. 왜 바꾸나」를 main 코드·데이터로 다시 확인하고, 결정 ①~④ · 전/후 기대값 · 메뉴 예시 채우기를 파일 6개의 예시로 풀었습니다.",
                chip("세 원인 모두 사실", "ok") + " " + chip("숫자 2곳 고침", "decide"), body)


# ───────────────────────── 01 투자비 실측
def p01():
    base = SC["현행 손 계수(재현)"]
    cards = []
    for e in EX["examples"]:
        months_txt = "한 달 안에" if e["roi"] < 1 else f'약 {round(e["roi"])}개월이면'
        cards.append(f"""<div class="card"><h4>{e["hub_name"]} · {e["area"]}평 · 월세 {e["rent"]:,}만원(추정)</h4>
<p class="src">추천 전략 {e["rec"]} · 월매출 {e["rev_man"]:,}만원 − 월비용 {e["cost_man"]:,}만원 = 월순익 {e["net_man"]:,}만원(추정 · 그대로 둠)</p>
<div class="tbl"><table><thead><tr><th scope="col">투자비</th><th scope="col" class="num">금액</th><th scope="col" class="num">회수</th></tr></thead><tbody>
<tr><th scope="row">지금 · 손 계수</th><td class="num">{e["inv_man"]:,}만원</td><td class="num"><b>{e["roi"]}개월</b></td></tr>
<tr><th scope="row">서울 인테리어 평균</th><td class="num">5,450만원</td><td class="num">{e["roi_int545"]}개월</td></tr>
<tr><th scope="row">서울 외식업 창업비 평균</th><td class="num">9,610만원</td><td class="num">{e["roi_food961"]}개월</td></tr>
</tbody></table></div>
<p class="src">지금 화면(R5): 「{e["rec"]} 하면 {months_txt} 본전이에요」</p></div>""")
    body = f"""
<div class="callout ok"><p><b>상태</b> — 11-15 승인(10-28 finding 의 (B) 안). 구현은 팀원 몫 P1 입니다. 첫 단계는 공정위 원천 1콜 확인이고, 목표치는 미리 정하지 않습니다(KPI 규칙 1).</p></div>

<h2>1. 식이 이렇게 바뀝니다</h2>
<div class="grid2">
<div class="mock before"><div class="label">지금 — <code>districts.tier_scenarios</code></div>
<pre><code>투자비(백만원) = 권리금/100 + 면적(평) × a + c
  고급화   a=0.55  c=4.0
  가성비   a=0.32  c=2.2
  기능중심 a=0.20  c=1.1     ← 손으로 적은 값</code></pre>
<p class="src">35평 기능중심이면 810만원 — 인테리어 평당 약 23만원꼴</p></div>
<div class="mock after"><div class="label">바뀐 뒤(안) — 공정위 정보공개서 실측</div>
<pre><code>투자비 = 권리금(들은 금액)
       + 단위면적 인테리어 금액[업종×가격대] × 면적
       + 최초 부담금(가맹금·교육비 등)[업종×가격대]
       (보증금은 돌려받는 돈이라 뺀다)
표본(브랜드) 부족 칸 → 「자료 부족」</code></pre>
<p class="src">가맹점 수로 가중한 중앙값 — 지금 면적 A 를 만들 때와 같은 규칙(<code>build_posting_store_area.py</code>)</p></div>
</div>

<h2>2. 예시 ① — 실제 자리 3곳에 넣어 보기</h2>
<p>서빙 코드가 지금 내는 값 그대로입니다. <b>월순익은 두고 투자비만</b> 바꿨습니다(P1 단독 효과).</p>
<div class="grid2">{"".join(cards)}</div>
<p class="src">투자비 비교값 — 서울시 「2025년 서울시 가맹사업 등록현황」(2026-06 발표): 가맹점 창업비 평균 1억 1,350만원 · 외식업 9,610만원 · 인테리어 평균 5,450만원(48.0%).
P1 이 실제로 쓸 값은 업종·가격대별 공정위 단위면적 인테리어 금액이라 위 숫자와 다를 수 있습니다.</p>

<h2>3. 예시 ② — 836곳 분포가 어떻게 움직이나</h2>
{heat_table("추천 전략 회수기간 구간별 자리 수 — 서빙 코드 실호출(2026-11-17) · 투자비만 바꾼 재계산", BIN_LAB, scen_rows(SCEN_ALL))}
<ul>
<li>투자비를 <b>3배</b>만 올려도 「1개월 미만」이 0 이 됩니다 — 「한 달 안에 본전이에요」는 거의 손 계수 때문에 나옵니다.</li>
<li>그래도 중앙 회수는 4~11개월로 짧은 편입니다. 매출 추정(면적 비례)이 그대로라서입니다 → P2 요구치가 머리 문장을 맡아야 합니다({link("placeos-05-before-after.html")}).</li>
</ul>

<h2>4. 예시 ③ — 원천 필드 대조와 1콜 확인 목록</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">공공데이터</th><th scope="col">주는 것</th><th scope="col">지금 쓰임</th></tr></thead>
<tbody>
<tr><th scope="row">15110241 브랜드별 가맹점 현황 (<code>FftcBrandFrcsStatsService</code>)</th><td>평균 매출액 · 면적 단위 평균 매출액 · 가맹점 수</td><td>tier별 평균 면적 A(고급화 20.8 · 가성비 18.5 · 기능중심 17.1평)</td></tr>
<tr><th scope="row">15143711 가맹사업자 부담금·인테리어비용</th><td>단위면적 인테리어 금액 · 인테리어 금액 · 점포 기준면적 · 가맹금 · 최초 상품 금액 · 예치 금액</td><td><b>아직 안 씀 — P1 원천</b></td></tr>
</tbody></table></div>
<ol>
<li>15143711 활용 신청 상태 확인(기존 <code>DATA_GO_KR_SERVICE_KEY</code> 공용 — 키 값은 출력하지 않는다)</li>
<li>기준연도 1개 · 1페이지 호출 → 응답 필드 이름·단위(천원/원)·면적 단위(3.3㎡ 여부) 확인</li>
<li>브랜드 업종 분류 ↔ 우리 tier(고급화·가성비·기능중심) 대응표 확인 — 면적 A 와 같은 대응을 쓴다</li>
<li>결과를 <code>docs/finding-ftc-interior-*.md</code> 로 남기고, 그다음 <code>tier_scenarios</code> 교체</li>
<li>교체 뒤 <code>python scripts/posting_payback_snapshot.py --label after-P1</code> → before 와 나란히. <code>provenance</code> 로 입력 갱신과 투자비 교체를 가른다</li>
</ol>
<div class="callout warn"><p><b>주의</b> — 공정위 값은 <b>전국 가맹점</b> 평균입니다. 개인 창업은 더 싸거나 비쌀 수 있어, 화면에는 「통계 · 공정위 정보공개서(전국 가맹점)」 배지를 달고,
사용자가 받은 견적(P3 · 브랜치 N1)이 있으면 그 값이 이깁니다.</p></div>
<p class="src">출처: <a href="https://www.data.go.kr/data/15143711/openapi.do">공공데이터포털 15143711</a> ·
<a href="https://www.hankyung.com/article/202606229186Y">한국경제 — 서울 프랜차이즈 창업비용(2026-06)</a> ·
<a href="https://www.fnnews.com/news/202606220601394155">파이낸셜뉴스 — 같은 발표</a></p>
"""
    return page("placeos-01-invest.html", "투자비 실측 예시", "결정 ① 투자비를 공정위 실측으로 — 계산으로 대조해 보기",
                "손으로 적은 투자비 계수를 공정위 정보공개서 실측으로 바꾸면 회수기간이 어떻게 달라지는지, 실제 자리 3곳과 836곳 분포로 미리 계산했습니다.",
                chip("승인 · 11-15", "ok") + " " + chip("구현 전 · P1", "decide") + " " + chip("1콜 확인 미실행", "warn"), body)


# ───────────────────────── 02 네 질문 · 정체성
def p02():
    ex = {e["hub"]: e for e in EX["examples"]}
    a, k = ex["apgujeong-rodeo"], ex["kyunghee"]
    ra, rk = req(a["rent"], "factory"), req(k["rent"], "factory")
    kor = next(i for i in MD.INDUSTRIES if i["key"] == "restaurant_korean")
    tk = MP.tier_summary(kor, "value", rent=k["rent"])
    t414 = MP.tier_summary(kor, "value")

    def card(track, q, body, cls):
        return f'<div class="card {cls}"><div class="src">{track}</div><h4>{q}</h4><p class="src" style="margin:0">{body}</p></div>'

    before = (card("Platform", "이 상권은 어떤 곳이지?", "상권의 성격을 읽고, 자리마다 어울리는 업종을 순위로 봅니다.", "before")
              + card("Page", "어느 건물 몇 층이 비었지?", "공실 히트맵과 건물·층별 매물 목록, 공실 이력의 확인 상태로 비어 있는 자리를 살펴봅니다.", "before")
              + card("Posting", "얼마짜리 자리가 맞지?", "고급화 · 가성비 · 기능중심, 세 가지 가격대로 비용과 회수 기간을 계산합니다.", "before")
              + card("Program", "계약하기 전에, 작게 먼저 어떻게 확인하지?", "(11-15 이미 반영) 팝업스토어 · 가오픈 · 시험 판매로 통하는지 확인할 계획을 세웁니다.", "before"))
    after = (card("Platform", "이 상권은 어떤 곳이지?", "<b>현행 유지</b>(11-15 사용자 결정) — 결과 대조가 「실력」 판정을 받은 뒤에 바꿉니다.", "after")
             + card("Page", "어느 층이 비었고, 내 업종이 들어갈 수 있지?", "빈 층을 찾고, 건축물대장·토지이음 기준으로 내 업종이 그 층에 들어갈 수 있는지(대장상 가능 · 확인 필요 · 대장상 용도 변경 필요)를 함께 봅니다. 허가 판정은 아닙니다.", "after")
             + card("Posting", "이 층 조건이면 얼마에 몇 개를 팔아야 하지?", "들은 월세(없으면 시세 범위)와 메뉴 가격·원가로, 이 층을 감당하려면 하루 몇 개를 팔아야 하는지 계산하고 같은 상권·업종 점포 매출과 나란히 봅니다.", "after")
             + card("Program", "계약하기 전에, 작게 먼저 어떻게 확인하지?", "그대로 — 목표선은 Posting 요구치(P2)에서 가져옵니다.", "after"))
    body = f"""
<div class="callout ok"><p><b>상태</b> — 11-15 승인. 단 <b>Platform 문구는 현행 유지</b>입니다(결과 대조 첫 계산이 구분불가).
Program 은 #243 에서 이미 바뀌었고, Page·Posting 문구는 <b>구현 PR 에서 함께</b> 바꿉니다 — 기능 없이 문구만 먼저 바꾸지 않습니다.</p></div>

<h2>1. 네 질문 — 지금과 바뀐 뒤</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">트랙</th><th scope="col">지금(CLAUDE.md 표)</th><th scope="col">승인안</th><th scope="col">반영</th></tr></thead>
<tbody>
<tr><th scope="row">Platform</th><td>이 입지·상권은 어떤 플랫폼인가</td><td>현행 유지</td><td>{chip("바꾸지 않음", "mute")}</td></tr>
<tr><th scope="row">Page</th><td>이 platform 안에 어떤 page 가 만들어져야 하는가</td><td>어느 층이 비었고, <b>내 업종이 들어갈 수 있나</b></td><td>{chip("2단계 PR", "decide")}</td></tr>
<tr><th scope="row">Posting</th><td>어떤 가격대의 page 가 posting 되어야 하는가</td><td><b>이 층 조건이면 얼마에 몇 개를 팔아야 하나</b></td><td>{chip("1단계 PR", "decide")}</td></tr>
<tr><th scope="row">Program</th><td>누구와 잇고 · 무엇을 지원받고 · 어떻게 알려…</td><td><b>계약 전에 어떻게 작게 확인하나</b></td><td>{chip("반영됨 #243", "ok")}</td></tr>
</tbody></table></div>

<h2>2. 예시 ① — 랜딩 「네 질문」 목업</h2>
<div class="grid2"><div><div class="label src">지금(placeos.co.kr #how)</div><div style="display:grid;gap:8px">{before}</div></div>
<div><div class="label src">바뀐 뒤(안)</div><div style="display:grid;gap:8px">{after}</div></div></div>

<h2>3. 예시 ② — 실제 자리의 Posting 머리 문장</h2>
<p>같은 자리, 같은 공식 통계로 문장만 「예측」에서 「요구치」로 바꿨습니다. 요구 월매출 = 월세 ÷ (1 − KOSIS 비임차 비용률 0.8696) — 서빙 중인 비용 구조 그대로, 매출 추정 없이 계산합니다.</p>
<div class="grid2">
<div class="mock before"><div class="label">지금 · {a["hub_name"]} {a["area"]}평 · 월세 {a["rent"]:,}만원(추정)</div>
<p style="font-size:19px;font-weight:700">「기능중심 하면 한 달 안에 본전이에요」</p>
<p class="src">회수 {a["roi"]}개월 = 투자 {a["inv_man"]:,}만원(손 계수) ÷ 월순익 {a["net_man"]:,}만원(월매출 {a["rev_man"]:,}만원 추정)</p></div>
<div class="mock after"><div class="label">바뀐 뒤(안)</div>
<p style="font-size:19px;font-weight:700">「이 층을 감당하려면 한 달에 {ra[0]:,.0f}만원, 하루 약 {ra[1]:,.0f}만원어치를 팔아야 해요」</p>
<p class="src">서울 같은 업종군 점포 평균 월매출(3,391만원 · KOSIS)의 <b>{ra[2]:.1f}배</b> · {chip("월세: 추정 — 들은 금액이 있으면 그 값", "mute")} {chip("비용률: 통계 KOSIS", "mute")}</p></div>
<div class="mock before"><div class="label">지금 · {k["hub_name"]} {k["area"]}평 · 월세 {k["rent"]:,}만원(추정)</div>
<p style="font-size:19px;font-weight:700">「기능중심 하면 약 2개월이면 본전이에요」</p>
<p class="src">회수 {k["roi"]}개월 = 투자 {k["inv_man"]:,}만원 ÷ 월순익 {k["net_man"]:,}만원(월매출 {k["rev_man"]:,}만원 추정)</p></div>
<div class="mock after"><div class="label">바뀐 뒤(안) — 메뉴를 넣었을 때</div>
<p style="font-size:19px;font-weight:700">「한식 백반이면 하루 약 {tk["daily"]:,}그릇을 팔아야 해요」</p>
<p class="src">(월세 {k["rent"]:,} + 인건비 3명 {tk["labor"]:,.0f} + 공과금·주기 구매 {tk["other"]:,.0f}만원) ÷ (1 − 원가율 {tk["cost_rate"]*100:.1f}%) = 월 {tk["bep"]:,.0f}만원 ÷ 객단가 {tk["avg_price"]:,.0f}원 ÷ 27일 —
메뉴·원가는 {link("placeos-06-menu-fill.html")} 의 한식 가성비 예시</p></div>
</div>

<h2>4. 예시 ③ — Page 층 상세에 붙는 한 줄</h2>
<div class="grid2">
<div class="mock before"><div class="label">지금</div><p><b>2F · 35평</b> · 빈 층(확정) · 월 259만원(추정)</p></div>
<div class="mock after"><div class="label">바뀐 뒤(안) — 내 업종: 음식점 · 판정은 모양을 보이는 예시</div><p><b>2F · 35평</b> · 빈 층(확정) · 월 259만원(추정)</p>
<p>{chip("↺ 대장상 용도 변경 필요", "warn")} (예) 대장 층 용도가 제1종 근린생활시설(소매점)이면 일반음식점을 하려면 대장 기재 변경이 필요해요.</p>
<p class="src">허가 판정 아님 · 건축물대장·토지이음 기준(기준일 표시) · 관할 구청 확인 — 문구는 main 의 <code>flow/useCheckLabels.ts</code> 다섯 갈래를 그대로 씁니다.</p></div>
</div>

<h2>5. 정체성 문장</h2>
<div class="grid2">
<div class="mock before"><div class="label">지금(CLAUDE.md)</div><p>…<b>계약하기 전에</b> 어느 상권 · 어느 건물 몇 층이 비었는지 · 월 얼마고 몇 달이면 본전인지 · 작게 먼저 확인할 방법까지 본다.</p></div>
<div class="mock after"><div class="label">승인본(11-15)</div><p>…<b>계약하기 전에</b> 어느 상권이 내 업종에 맞는지 · 어느 건물 몇 층이 비었고 <b>그 층에 내 업종이 들어갈 수 있는지</b> · <b>그 조건이면 얼마나 팔아야 하는지</b> · 계약 전에 작게 확인하는 방법까지 본다.</p></div>
</div>

<h2>6. 예시 ④ — 예비창업자 A 의 질문으로 따라가 보기</h2>
<p class="src">가정: 한식 백반 · 회기동 · 월세 {MD.DEFAULT_RENT}만원 자리 · 3명 운영. 숫자는 06 파일의 한식 가성비 예시에서 왔습니다.</p>
<div class="grid2">
<div class="card before"><h4>지금 흐름</h4>
<p><b>A</b>: 이 층에서 백반집 해도 돼요?<br><b>PlaceOS</b>: (답 없음 — 빈 층과 월세 추정까지만)</p>
<p><b>A</b>: 그럼 얼마나 벌어요?<br><b>PlaceOS</b>: 고급화·가성비·기능중심 중 기능중심 하면 한 달 안에 본전이에요.</p>
<p><b>A</b>: 한 달이요…? 믿어도 되나요?</p></div>
<div class="card after"><h4>바뀐 흐름</h4>
<p><b>A</b>: 이 층에서 백반집 해도 돼요?<br><b>PlaceOS</b>: 대장상 용도 변경이 필요해요(1종 근생 소매점). 구청에 기재 변경을 물어보세요. 허가 판정은 아니에요.</p>
<p><b>A</b>: 월세 {MD.DEFAULT_RENT}만원이면 얼마나 팔아야 해요?<br><b>PlaceOS</b>: 객단가 {t414["avg_price"]:,.0f}원 · 원가율 {t414["cost_rate"]*100:.0f}% 기준으로 하루 약 <b>{t414["daily"]:,}그릇</b>이에요. 중개사에게 들은 월세를 넣으면 다시 계산해요.</p>
<p><b>A</b>: 계약 전에 확인하려면요?<br><b>PlaceOS</b>: 주말 팝업 3일, 하루 {t414["daily"]:,}그릇을 못 넘으면 접는 기준으로 시험해 보세요(Program).</p></div>
</div>
"""
    return page("placeos-02-questions.html", "네 질문 정체성 예시", "결정 ② 네 질문 · 정체성 문장 — 화면 문구 전/후",
                "승인된 질문 개정이 랜딩·Posting 머리 문장·Page 층 상세·정체성 문장에서 어떻게 보이는지 실제 자리 값으로 목업했습니다.",
                chip("승인 · 11-15", "ok") + " " + chip("Platform 현행 유지", "mute") + " " + chip("Program 반영됨", "ok"), body)


# ───────────────────────── 03 인테리어 · 마케팅
def p03():
    js = r"""<script>
(()=>{function wire(group){const btns=[...document.querySelectorAll('[data-group="'+group+'"] [data-opt]')];
const panes=[...document.querySelectorAll('[data-pane-group="'+group+'"] [data-pane]')];
btns.forEach(b=>b.addEventListener('click',()=>{btns.forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
panes.forEach(p=>p.hidden=p.dataset.pane!==b.dataset.opt);}));}
wire('posting');wire('program');
document.querySelectorAll('.mtabs [role="tab"]').forEach(t=>t.addEventListener('click',()=>{const box=t.closest('.mtabs');
box.querySelectorAll('[role="tab"]').forEach(x=>x.setAttribute('aria-selected',x===t?'true':'false'));
box.querySelectorAll('.mpane').forEach(p=>p.hidden=p.id!==t.getAttribute('aria-controls'));}));})();
</script>"""
    style = """<style>
.opts{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.opts button{font:inherit;font-size:14px;padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--fg);cursor:pointer}
.opts button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.rail{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.rail span{font-size:13.5px;padding:5px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface)}
.rail span.opt{border-style:dashed;color:var(--muted)} .rail span.new{border-color:var(--accent);color:var(--accent);font-weight:600}
.rail span.moved{border-color:var(--decide);color:var(--decide)}
.mtabs [role="tablist"]{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line);margin-bottom:8px}
.mtabs [role="tab"]{font:inherit;font-size:14px;padding:6px 10px;border:0;border-bottom:2px solid transparent;background:none;color:var(--muted);cursor:pointer}
.mtabs [role="tab"][aria-selected="true"]{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
</style>"""
    body = style + f"""
<div class="callout ok"><p><b>③-b 승인·시행</b> — Program 탭 순서가 「가설 설정 → 네트워킹 → 지원 프로그램 → 오프라인 마케팅 솔루션(개업 뒤)」로 바뀌었습니다(main <code>pages/CampaignStudio.tsx</code> 의 <code>ORDER</code>). 탭 이름·PPPP 화면·가드는 그대로입니다.</p></div>
<div class="callout decide"><p><b>③-a 보류(유일한 미결)</b> — 인테리어 3D 를 Posting 기본 경로에서 「펼치는 선택 칸」으로 내릴지. 결정 전까지 11-09 결정(인테리어 쪽은 Posting 2번째)을 그대로 둡니다.
Posting 7쪽→3쪽 정리가 이 결정을 기다립니다.</p></div>

<h2>1. Program 탭 — 11-07 과 지금</h2>
<div class="opts" data-group="program" role="group" aria-label="Program 탭 순서 보기">
<button type="button" data-opt="old" aria-pressed="false">11-07 순서</button><button type="button" data-opt="now" aria-pressed="true">지금(11-15~)</button></div>
<div data-pane-group="program">
<div class="mock" data-pane="old" hidden><div class="label">11-07 리뉴얼 순서</div>
<div class="rail"><span>네트워킹</span><span>지원 프로그램</span><span>오프라인 마케팅 솔루션</span><span>가설 검증</span></div>
<p class="src">마케팅이 가설보다 앞 — 「계약 전 확인」보다 「알리기」가 먼저 보였습니다.</p></div>
<div class="mock" data-pane="now"><div class="label">지금 — 계약 전 확인이 먼저, 마케팅은 개업 뒤</div>
<div class="rail"><span class="new">가설 설정</span><span>네트워킹</span><span>지원 프로그램</span><span class="moved">오프라인 마케팅 솔루션 · 개업 뒤</span></div>
<p class="src">탭 안에 「개업 뒤 칸입니다 — 계약 전 확인은 앞의 가설 설정·네트워킹·지원 프로그램에서」 안내가 붙습니다.</p></div>
</div>

<h2>2. Posting 쪽 구성 — ③-a 선택지 눌러 보기</h2>
<div class="opts" data-group="posting" role="group" aria-label="Posting 쪽 구성 안">
<button type="button" data-opt="A" aria-pressed="true">A · 지금(7쪽)</button>
<button type="button" data-opt="B" aria-pressed="false">B · 3쪽 + 인테리어 선택 칸(인계 문서 안)</button>
<button type="button" data-opt="C" aria-pressed="false">C · 3쪽 + 인테리어는 「계약 뒤 준비」</button></div>
<div data-pane-group="posting">
<div class="mock" data-pane="A"><div class="label">A · 지금 — 질문 「어떤 비용과 전략으로 입점할까요?」</div>
<div class="rail"><span>1 시뮬레이션 결과</span><span>2 상권 맞춤 인테리어(3D)</span><span>3 주변 업종 지도</span><span>4 찾아오는 길</span><span>5 위험 확인</span><span>6 메뉴 설정</span><span>7 비용 비교 및 결정</span></div>
<p class="src">자리 사실(3·4)과 사업계획(1·6·7)과 인테리어(2)가 한 줄에 섞여 있습니다.</p></div>
<div class="mock" data-pane="B" hidden><div class="label">B · 3쪽 — 질문 「이 층 조건이면 얼마에 몇 개를 팔아야 하나」</div>
<div class="mtabs"><div role="tablist" aria-label="B 안 쪽">
<button type="button" role="tab" aria-selected="true" aria-controls="b1">① 이 층의 계약 조건</button>
<button type="button" role="tab" aria-selected="false" aria-controls="b2">② 얼마나 팔아야 하나</button>
<button type="button" role="tab" aria-selected="false" aria-controls="b3">③ 계약 전 확인</button></div>
<div class="mpane" id="b1"><p>들은 보증금·월세·권리금 → 없으면 R-ONE 범위(참고) · 면적 · 층. 첫 문장은 Page 에서 고른 층으로 시작(예: 「회기동 ○○빌딩 2층 · 35평 — 이 층을 계약해도 되나, 돈 쪽」).</p></div>
<div class="mpane" id="b2" hidden><p>요구치(P2): 하루 판매 개수 · 월매출 · 같은 상권·업종 점포 평균 대비 %. 메뉴 설정이 여기로 들어옵니다.</p>
<div class="rail"><span class="opt">펼치기 · 세 가격대 비교</span><span class="opt">펼치기 · 메뉴 설정</span><span class="opt">펼치기 · 상권 맞춤 인테리어(3D)</span></div></div>
<div class="mpane" id="b3" hidden><p>위험 확인 + 2단계 입점 점검 결과 + 계약 전 체크리스트. 주변 업종 지도·찾아오는 길은 Page 에 <b>더하고</b> 여기에도 링크로 남깁니다.</p></div></div></div>
<div class="mock" data-pane="C" hidden><div class="label">C · 3쪽 + 계약 뒤 준비</div>
<div class="rail"><span>① 이 층의 계약 조건</span><span>② 얼마나 팔아야 하나</span><span>③ 계약 전 확인</span><span class="opt">계약 뒤 준비 · 상권 맞춤 인테리어(3D)</span></div>
<p class="src">인테리어를 계약 뒤 단계로 분명히 미룹니다. Program 의 「개업 뒤」 칸(③-b)과 같은 원리입니다.</p></div>
</div>

<div class="tbl"><table>
<thead><tr><th scope="col">안</th><th scope="col">좋은 점</th><th scope="col">걸리는 점</th><th scope="col">인테리어까지 클릭</th></tr></thead>
<tbody>
<tr><th scope="row">A 지금</th><td>11-09 결정 그대로 · 작업 없음</td><td>개발자 모임 지적(「부동산 앱에 인테리어가?」) 그대로 · 7쪽 혼재</td><td class="num">1</td></tr>
<tr><th scope="row">B 선택 칸</th><td>질문 하나(요구치)에 집중 · 3D 기능은 지우지 않음 · 인계 문서 안과 같음</td><td>11-09 결정 변경 필요 · 펼치기 칸 구현</td><td class="num">2</td></tr>
<tr><th scope="row">C 계약 뒤</th><td>순서가 가장 분명(계약 전 → 뒤) · ③-b 와 같은 원리</td><td>11-09 결정 변경 · 「계약 뒤」 칸이 Posting 에 새로 생김</td><td class="num">2</td></tr>
</tbody></table></div>
<div class="callout"><p><b>제 의견: B</b> — 「예측을 줄이고 확인을 늘린다」는 방향과 개발자 모임의 지적에 맞고, 3D 트윈은 한 번 더 눌러 바로 열려서 11-09 결정의 기능을 지우지 않습니다.
다만 ③-a 는 사용자 결정 사항이라, 정해지기 전까지는 A 를 유지합니다.</p></div>
<p class="src">보존 규칙: Posting 트랙 화면(<code>PostingConsole</code>)과 레일 버튼은 그대로입니다. 트랙 안의 쪽 정리는 가드(<code>ppppScreens.test.tsx</code> — 트랙 이름·순서)의 대상이 아닙니다.</p>
"""
    return page("placeos-03-interior-marketing.html", "인테리어 마케팅 칸", "결정 ③ 인테리어 3D · 오프라인 마케팅 — 눌러 보는 탭 목업",
                "이미 시행된 Program 「개업 뒤」 칸(③-b)과, 아직 정하지 않은 인테리어 3D 위치(③-a)의 세 가지 안을 눌러 비교해 볼 수 있게 했습니다.",
                chip("③-b 시행", "ok") + " " + chip("③-a 보류", "decide"), body, js)


# ───────────────────────── 04 처리방침
def p04():
    js = r"""<script>
(()=>{const cb=document.getElementById('consent');const out=document.getElementById('consent-out');
function draw(){out.innerHTML=cb.checked
?'<b>저장</b>: 들은 월세 380만원 · 보증금 5,000만원(내 계정에만 보임)<br><b>추가로</b>: 이 자리의 추정 월세(R-ONE)와의 차이를 <b>개인·조직을 알아볼 수 없는 통계</b>(층·상권 단위 오차)로만 씁니다. 탈퇴하면 원래 값은 지우고 통계 숫자만 남습니다.'
:'<b>저장</b>: 들은 월세 380만원 · 보증금 5,000만원(내 계정에만 보임)<br><b>쓰지 않음</b>: 임대료 추정 정확도 통계에는 넣지 않습니다.';}
cb.addEventListener('change',draw);draw();})();
</script>"""
    svg = """<svg viewBox="0 0 880 210" role="img" aria-label="데이터 흐름: 사용자 입력에서 계정 저장, 동의 시 익명 통계, 탈퇴 시 삭제" style="width:100%;height:auto;max-width:880px">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="currentColor"/></marker></defs>
<g font-size="14" fill="currentColor" style="color:var(--fg)">
<rect x="10" y="20" width="190" height="70" rx="10" fill="var(--surface)" stroke="var(--line)"/><text x="105" y="50" text-anchor="middle">사용자 입력</text><text x="105" y="72" text-anchor="middle" fill="var(--muted)" font-size="12.5">들은 월세 · 답사 기록</text>
<rect x="250" y="20" width="190" height="70" rx="10" fill="var(--surface)" stroke="var(--line)"/><text x="345" y="50" text-anchor="middle">계정 저장(지금도 있음)</text><text x="345" y="72" text-anchor="middle" fill="var(--muted)" font-size="12.5">저장한 작업 불러오기</text>
<rect x="490" y="20" width="190" height="70" rx="10" fill="var(--accent-bg)" stroke="var(--accent)"/><text x="585" y="50" text-anchor="middle">새 목적(④)</text><text x="585" y="72" text-anchor="middle" fill="var(--muted)" font-size="12.5">동의한 값만 · 익명 통계</text>
<rect x="710" y="20" width="160" height="70" rx="10" fill="var(--surface)" stroke="var(--line)"/><text x="790" y="50" text-anchor="middle">KPI 집계</text><text x="790" y="72" text-anchor="middle" fill="var(--muted)" font-size="12.5">층별 임대료 오차</text>
<line x1="200" y1="55" x2="246" y2="55" stroke="var(--muted)" marker-end="url(#ar)"/>
<line x1="440" y1="55" x2="486" y2="55" stroke="var(--accent)" marker-end="url(#ar)"/>
<line x1="680" y1="55" x2="706" y2="55" stroke="var(--muted)" marker-end="url(#ar)"/>
<rect x="250" y="130" width="190" height="64" rx="10" fill="var(--warn-bg)" stroke="var(--warn)"/><text x="345" y="158" text-anchor="middle">탈퇴</text><text x="345" y="180" text-anchor="middle" fill="var(--muted)" font-size="12.5">원래 값 바로 삭제</text>
<line x1="345" y1="90" x2="345" y2="126" stroke="var(--warn)" marker-end="url(#ar)"/>
<text x="500" y="152" fill="var(--muted)" font-size="12.5"><tspan x="500">탈퇴해도 통계 숫자(오차 평균·구간)만</tspan><tspan x="500" dy="18">누구 것인지 모르는 집계로 남음</tspan></text>
</g></svg>"""
    body = f"""
<div class="callout ok"><p><b>상태</b> — 11-15 승인 · 5단계 몫이라 착수 시점은 미정입니다. 늦게 해도 1~4단계는 막히지 않습니다.
다만 <b>사용자가 입력한 월세를 KPI 에 쓰는 일</b>은 이 고지가 먼저입니다 — 지금 처리방침의 목적은 「저장한 작업 불러오기」까지라서입니다.</p></div>

<h2>1. 받는 것과 쓰는 곳 — 지금과 바뀐 뒤</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">항목</th><th scope="col">지금 처리방침(시행 2026-10-25)</th><th scope="col">바뀐 뒤(안)</th></tr></thead>
<tbody>
<tr><th scope="row">사업 정보 — 직접 저장한 후보 자리·계산·검증 결과</th><td>목적: 입력한 업종·상권에 맞춘 분석 제공, 저장한 작업 불러오기</td>
<td>목적에 더함: <b>「직접 입력한 계약 조건(보증금·월세·권리금)과 추정값의 차이를 재어 임대료 추정의 정확도를 높이는 통계 — 동의한 경우에만, 개인·조직을 알아볼 수 없는 집계로」</b></td></tr>
<tr><th scope="row">현장 확인 기록(답사) — <b>새 항목</b></th><td>—</td><td>방문일 · 빈 층 여부 · 시간대 유동 메모 · 들은 월세. 목적: 저장한 작업 불러오기 + (동의 시) 위 통계</td></tr>
<tr><th scope="row">보관·파기</th><td>탈퇴하면 바로 지움</td><td>그대로 — 원래 값은 탈퇴 즉시 삭제, 통계 결과(오차 평균·구간)만 식별자 없이 남음</td></tr>
</tbody></table></div>

<h2>2. 짧은 고지(PrivacyNote) 문구 비교</h2>
<div class="grid2">
<div class="mock before"><div class="label">지금</div><p>가입하면 이메일(로그인용)과 직접 적은 사업 정보·오프라인 캠페인 기록·피드백, 직접 저장한 후보 자리·계산·검증 결과, 이용 기록(어떤 분석을 불렀는지)을 보관합니다. …</p></div>
<div class="mock after"><div class="label">바뀐 뒤(안) — 한 문장 추가</div><p>… 직접 입력한 계약 조건(보증금·월세)과 답사 기록은 <b>동의한 경우에만</b> 임대료 추정이 얼마나 맞는지 재는 통계에 쓰고, 이 통계는 개인·조직을 알아볼 수 없게 집계합니다.</p></div>
</div>

<h2>3. 예시 — 저장할 때 묻는 동의(선택)</h2>
<div class="mock" style="max-width:560px"><div class="label">Posting ① 이 층의 계약 조건 · 저장</div>
<p>들은 월세 <b>380만원</b> · 보증금 <b>5,000만원</b></p>
<label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" id="consent"> <span>이 금액을 임대료 추정 정확도 통계(익명 집계)에 써도 됩니다 <span class="src">(선택 — 안 해도 계산·저장은 그대로)</span></span></label>
<p id="consent-out" class="src" style="margin-top:8px" aria-live="polite"></p></div>

<h2>4. 데이터 흐름</h2>
<div class="card">{svg}</div>

<h2>5. 같은 PR 에서 함께 고칠 것</h2>
<ul>
<li><code>components/PrivacyNote.tsx</code> 문구 · <code>public/privacy.html</code> 표와 시행일 — 받는 항목을 늘리는 PR 과 같은 PR(<code>docs/decision-lightweight-first-2026-10-05.md</code>)</li>
<li><code>auth_service.delete_account</code> — 답사 기록 테이블도 지우는지 테스트로 고정</li>
<li>KPI 계측: 오차 = |입력 월세 − 추정 월세| ÷ 입력 월세 · 표본 단위는 자리(조직당 최신 1건) · 내부 조직 제외(<code>services/kpi_scope</code>) · n 과 구간 동반 · 동의한 사람만이라 표본 치우침을 함께 적는다</li>
</ul>
<div class="callout warn"><p><b>법률 메모(자문 아님)</b> — 개인정보 보호법은 수집 때 알린 목적 밖의 이용을 제한합니다(제15조·제18조). 통계 작성은 가명 처리로도 할 수 있지만(제28조의2) 안전조치가 따로 필요합니다.
여기서는 가장 가벼운 길(선택 동의 + 익명 집계)을 예시로 들었고, 문구 확정 전에 검토를 받으세요.</p></div>
"""
    return page("placeos-04-privacy.html", "처리방침 목적 추가", "결정 ④ 처리방침에 목적 더하기 — 문구 전/후와 데이터 흐름",
                "사용자가 입력한 월세·답사 기록을 임대료 추정 오차 KPI 에 쓰려면 무엇을 고지하고 어떻게 동의를 받는지, 문구와 화면 목업으로 보였습니다.",
                chip("승인 · 11-15", "ok") + " " + chip("착수 미정 · 5단계", "mute"), body, js)


# ───────────────────────── 05 전/후 기대값
def p05():
    base = SC["현행 손 계수(재현)"]; x3 = SC["투자비 ×3"]; s545 = SC["인테리어 서울 평균 5,450만원(면적 무관)"]; s961 = SC["외식업 창업비용 서울 평균 9,610만원(면적 무관)"]
    # P2 미리보기 — 요구 월매출 ÷ 서울 점포당 평균(같은 tier) 분포
    ratios = [r["rent"] / (1 - OPEX[r["rec"]]) / KOS[r["rec"]] for r in UNITS if r["rec"]]
    edges = [(0, 0.5, "0.5배 미만"), (0.5, 1, "0.5~1배"), (1, 1.5, "1~1.5배"), (1.5, 2, "1.5~2배"), (2, 3, "2~3배"), (3, 99, "3배 이상")]
    hist = [sum(1 for x in ratios if lo <= x < hi) for lo, hi, _ in edges]
    uc = UC["status_by_industry"]
    uc_rows = [("음식점·술집", uc["restaurant"]), ("카페·디저트", uc["cafe"]), ("병·의원", uc["clinic"]), ("약국·편의점·옷", uc["pharmacy"]),
               ("미용·네일", uc["beauty"]), ("학원·교육", uc["education"]), ("운동·여가", uc["fitness"])]
    rest = uc["restaurant"]
    body = f"""
<div class="callout"><p><b>읽는 법</b> — {chip("측정", "ok")} 지금 값을 다시 잰 것 · {chip("계산", "info")} 가정을 밝힌 예측 · {chip("설계", "v")} 만들면 그렇게 되는 것 · {chip("모름", "mute")} 미리 말할 근거가 없음.
목표치는 미리 정하지 않습니다(KPI 규칙 1) — 아래 「바뀐 뒤」는 약속이 아니라 같은 방법으로 다시 잴 때 볼 범위입니다.</p></div>

<div class="tiles">
<div class="tile"><div class="k">「한 달 안에 본전이에요」 자리</div><div class="v">{base["lt1"]} → {x3["lt1"]}~{s545["lt1"]}<small>곳</small></div><div class="s">{chip("측정", "ok")} → {chip("계산", "info")} P1(투자비 ×3 ~ 서울 인테리어 평균) · 836곳 중</div></div>
<div class="tile"><div class="k">추천 회수 중앙</div><div class="v">{base["median"]} → {x3["median"]}~{s961["median"]}<small>개월</small></div><div class="s">{chip("계산", "info")} 매출·월세는 그대로 둔 값 — 실제는 더 길 수 있음</div></div>
<div class="tile"><div class="k">Posting 머리 문장</div><div class="v">회수기간 → 요구치</div><div class="s">{chip("설계", "v")} P2 · 「한 달 안에」 문장 자체가 머리에서 내려감</div></div>
<div class="tile"><div class="k">Page 「내 업종 들어갈 수 있나」</div><div class="v">0 → 10,574<small>곳</small></div><div class="s">{chip("측정", "ok")} 규칙 분포(서울 빈 층 14,517 중 · 3,943 자료 부족)</div></div>
</div>

<h2>1. 작업별 전/후</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">작업</th><th scope="col">지금</th><th scope="col">바뀐 뒤(기대)</th><th scope="col">근거</th><th scope="col">다시 재는 법</th></tr></thead>
<tbody>
<tr><th scope="row">P1 투자비 실측</th><td>손 계수 · 투자비 중앙 {SUM["inv_q"][1]:,}만원 · 1개월 미만 {base["lt1"]}</td><td>1개월 미만 {x3["lt1"]}~{s545["lt1"]} · 중앙 {x3["median"]}~{s961["median"]}개월</td><td>{chip("계산", "info")} 투자비만 바꾼 재계산</td><td><code>posting_payback_snapshot.py --label after-P1</code></td></tr>
<tr><th scope="row">P2 요구치</th><td>머리 문장 = 회수기간(「한 달 안에」 {base["lt1"]}곳)</td><td>머리 문장 = 하루 판매·월매출 + 서울 점포 평균 대비 배수. 추천 자리의 {P2["share_over_avg"]}%가 「평균 이상 팔아야」</td><td>{chip("계산", "info")} 월세 ÷ (1 − KOSIS 비용률)</td><td>응답 <code>requirement</code> 필드 · 테스트</td></tr>
<tr><th scope="row">P3 들은 금액 우선</th><td>세 가격대 계산의 월세는 R-ONE 추정(권리금·면적만 직접 입력 · 세부 업종 시나리오와 흐름 Q8 에는 금액 입력이 있음)</td><td>입력이 있으면 추정을 이긴다 · 없으면 범위로만</td><td>{chip("설계", "v")} 브랜치 N3 가 이미 구현</td><td>테스트: 입력값 &gt; 추정</td></tr>
<tr><th scope="row">P4 근거 배지</th><td>배지 없는 숫자 — 아직 세지 않음</td><td>0(테스트로 고정)</td><td>{chip("설계", "v")}</td><td>컴포넌트 테스트</td></tr>
<tr><th scope="row">Posting 7쪽 → 3쪽</th><td>7쪽(인테리어 2번째)</td><td>3쪽 + 선택 칸 — 인테리어 위치는 ③-a 결정 뒤</td><td>{chip("설계", "v")}</td><td><code>pppp_screens_check.py</code></td></tr>
<tr><th scope="row">2-A 자리 사실을 Page 로</th><td>주변 업종·찾아오는 길은 Posting 에만</td><td>Page 층 상세에도(+2 패널) · Posting 은 그대로</td><td>{chip("설계", "v")}</td><td>실화면 검사</td></tr>
<tr><th scope="row">2-C 사전등록</th><td>main 에 초안(<code>prereg-floor-use-check-2026-11-15</code>) · 채점 전</td><td>인허가 정답지 대조 결과 — 무정보 규칙과의 차이</td><td>{chip("모름", "mute")} 채점 전엔 말하지 않음</td><td>사전등록대로 채점</td></tr>
<tr><th scope="row">2-E Page 층 상세 연결</th><td>흐름 R4 · 후보 비교에만 연결(main)</td><td>Page 층 상세에서 내 업종 판정 — 음식점이면 가능 {rest["ledger_ok"]:,} · 확인 필요 {rest["needs_check"]:,} · 용도 변경 필요 {rest["use_change_needed"]:,} · 금지 {rest["zoning_prohibited"]:,} · 자료 부족 {rest["missing_inputs"]:,}</td><td>{chip("측정", "ok")} 규칙 분포(실력 아님)</td><td><code>use_check_vacant_summary.py</code></td></tr>
<tr><th scope="row">③-b 마케팅 「개업 뒤」</th><td colspan="2">이미 시행(11-15) — 바뀐 것 없음</td><td>{chip("측정", "ok")}</td><td>—</td></tr>
<tr><th scope="row">④ 처리방침</th><td>입력 월세를 KPI 에 쓸 근거 없음</td><td>동의한 값으로 층별 임대료 오차 KPI 를 잴 수 있음</td><td>{chip("설계", "v")}</td><td>KPI 계측 배선 · n</td></tr>
</tbody></table></div>

<h2>2. 회수기간 분포 — P1 전/후</h2>
{heat_table("추천 전략 회수기간 구간별 자리 수(836곳) — 서빙 코드 실호출 · 투자비만 바꾼 재계산", BIN_LAB, scen_rows([SCEN_ALL[0], SCEN_ALL[2], SCEN_ALL[5], SCEN_ALL[6]]))}

<h2>3. P2 미리보기 — 「얼마나 팔아야 하나」로 바꾸면</h2>
<p>요구 월매출 = 월세 ÷ (1 − KOSIS 비임차 비용률). 이 값을 같은 가격대의 서울 점포당 평균 월매출(KOSIS)로 나눈 배수입니다. 매출 추정 없이 월세와 공식 통계만 씁니다.</p>
{heat_table("추천 자리 836곳 — 요구 월매출이 서울 점포 평균의 몇 배인가", [lab for _, _, lab in edges], [("자리 수", hist, f'중앙 {P2["ratio_med"]}배 · 사분위 {P2["ratio_q1"]}~{P2["ratio_q3"]}배')], row_head="")}
<p>추천 자리의 <b>{P2["share_over_avg"]}%</b>는 월세만 감당하려 해도 서울 점포 평균 이상을 팔아야 하고, <b>{P2["share_over_2x"]}%</b>는 2배 이상입니다.
지금 화면이 「한 달 안에 본전」이라고 말하는 자리들이 여기에 섞여 있습니다 — 이 차이가 「숫자가 가설이다」는 지적의 실체입니다.</p>

<h2>4. Page — 「내 업종이 들어갈 수 있나」 규칙 분포</h2>
<p class="src">서울 빈 층 14,517곳 · 서술 통계(규칙이 어떻게 나누나)이지 규칙의 실력이 아닙니다. 강남·송파·강동 3,943곳은 토지이음 행위제한을 아직 다 받지 못해 「자료 부족」입니다.</p>
{status_bars(uc_rows, "빈 층 판정 분포 — reports/use_check_vacant_seoul_2026-11-15.json")}

<h2>5. 생길 수 있는 부작용</h2>
<div class="tbl"><table>
<thead><tr><th scope="col">무엇</th><th scope="col">왜</th><th scope="col">줄이는 법</th></tr></thead>
<tbody>
<tr><th scope="row">숫자가 「덜 매력적」으로 보임</th><td>「한 달 안에 본전」 → 「서울 평균 이상 팔아야」</td><td>사실이므로 감추지 않음 · 대신 「작게 확인」(Program)으로 바로 잇기</td></tr>
<tr><th scope="row">공정위 값이 개인 창업과 다름</th><td>전국 가맹점 평균</td><td>배지로 밝힘 · 견적 입력(P3)이 이김</td></tr>
<tr><th scope="row">자료 부족 3,943곳</th><td>토지이음 일일 한도(약 1,000콜)</td><td>남은 콜 재수집 뒤 다시 집계 — 다른 구 값으로 채우지 않음</td></tr>
<tr><th scope="row">브랜치 충돌</th><td>11개 기능 브랜치가 main 보다 31커밋 뒤</td><td>N2 철회 · N6 요구치로 고쳐 다시 · 나머지는 main 위로 다시 맞춤({link("placeos-00-verify.html")})</td></tr>
</tbody></table></div>

<h2>6. KPI 와의 관계</h2>
<ul>
<li>KPI① 빈 층 판정: 바뀌지 않음(라벨 0/458 — 사람 몫). 입점 점검은 새 축 후보이고 사전등록 → 채점 순서입니다.</li>
<li>KPI② 표면 성능: 흐름 답 화면 계측 0 은 그대로 — 이 작업이 바꾸지 않습니다.</li>
<li>KPI③ 파일럿: 영향은 미리 말하지 않습니다({chip("모름", "mute")}).</li>
</ul>
"""
    return page("placeos-05-before-after.html", "전후 기대값", "작업을 마치면 무엇이 달라지나 — 전/후 기대값",
                "인계 문서대로 Page·Posting 작업을 했을 때 화면과 숫자가 어떻게 달라지는지, 지금 값(측정)과 바뀐 뒤 범위(계산·설계)를 나란히 놓았습니다.",
                chip("측정 + 계산", "info"), body)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fn, fname in ((p00, "placeos-00-verify.html"), (p01, "placeos-01-invest.html"), (p02, "placeos-02-questions.html"),
                      (p03, "placeos-03-interior-marketing.html"), (p04, "placeos-04-privacy.html"), (p05, "placeos-05-before-after.html")):
        (OUT / fname).write_text(fn(), encoding="utf-8")
        print("wrote", fname)
