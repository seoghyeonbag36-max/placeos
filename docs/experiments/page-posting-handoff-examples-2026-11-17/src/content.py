"""표현 유형 5종이 함께 쓰는 내용 — 숫자·문장을 한 곳에서 만든다(유형마다 숫자가 달라지지 않게).

숫자 출처: data/examples_data.json · data/units_raw.json(서빙 코드 실호출 2026-11-17) · data/use_check_vacant_seoul_2026-11-15.json(main 커밋 산출물) ·
menu_plan(메뉴 예시 v2). 문장 출처: 00~06 예시 파일과 같다.
"""
import json
from pathlib import Path

import menu_data as MD
import menu_plan as MP

X = Path(__file__).resolve().parents[1]
EX = json.loads((X / "data" / "examples_data.json").read_text())
UNITS = json.loads((X / "data" / "units_raw.json").read_text())
UC = json.loads((X / "data" / "use_check_vacant_seoul_2026-11-15.json").read_text())
SC = {r["label"]: r for r in EX["scenarios"]}
P2 = EX["p2"]
SUM = EX["summary"]
TK = {"premium": "고급화", "value": "가성비", "factory": "기능중심"}
OPEX = {k: P2["opex"][v] for k, v in TK.items()}
KOS = {k: P2["kosis_store_month"][v] for k, v in TK.items()}
BIN = ["<1", "1-3", "3-6", "6-12", "12-24", ">=24"]
BIN_LAB = ["1개월 미만", "1~3개월", "3~6개월", "6~12개월", "12~24개월", "24개월 이상"]
MENU_LINK = "../set/placeos-06-menu-fill.html"
SET_LINK = "../set/placeos-00-verify.html"

BASE = SC["현행 손 계수(재현)"]
X3 = SC["투자비 ×3"]
S545 = SC["인테리어 서울 평균 5,450만원(면적 무관)"]
S961 = SC["외식업 창업비용 서울 평균 9,610만원(면적 무관)"]


def req(rent, tier, days=26):
    m = rent / (1 - OPEX[tier])
    return m, m / days, m / KOS[tier]


def build():
    ex = {e["hub"]: e for e in EX["examples"]}
    a, k = ex["apgujeong-rodeo"], ex["kyunghee"]
    ra = req(a["rent"], "factory")
    kor = next(i for i in MD.INDUSTRIES if i["key"] == "restaurant_korean")
    t414 = MP.tier_summary(kor, "value")
    ratios = [r["rent"] / (1 - OPEX[r["rec"]]) / KOS[r["rec"]] for r in UNITS if r["rec"]]
    edges = [(0, 0.5, "0.5배 미만"), (0.5, 1, "0.5~1배"), (1, 1.5, "1~1.5배"), (1.5, 2, "1.5~2배"), (2, 3, "2~3배"), (3, 99, "3배 이상")]
    uc = UC["status_by_industry"]
    rest = uc["restaurant"]

    core = [
        dict(tag="검증", head="「왜 바꾸나」 세 원인은 모두 사실", body="main 코드를 읽고 서빙 코드를 다시 돌려 확인했습니다. 숫자 두 곳만 고칩니다(분모 891 → 836 · Page 근사값 → 대장 용도코드 값)."),
        dict(tag="숫자", head=f"「한 달 안에 본전」 {BASE['lt1']}/836곳 → P1 뒤 {X3['lt1']}~{S545['lt1']}곳(계산)", body=f"투자비만 공정위 실측 수준으로 바꾼 재계산입니다. 추천 회수 중앙은 {BASE['median']}개월 → {S545['median']}개월(서울 인테리어 평균 적용 시)."),
        dict(tag="결정", head="결정 ①②④ · ③-b 는 11-15 승인 — ③-a(인테리어 3D 위치)만 보류", body="그래서 결정 예시는 「정한 대로 하면 어떻게 보이나」를 보여 주고, ③-a 만 A·B·C 선택지를 나란히 놓습니다."),
        dict(tag="방향", head="머리 문장을 회수기간에서 요구치(P2)로", body=f"투자비만 고쳐도 회수 중앙 {S545['median']}개월은 여전히 낙관입니다 — 매출이 면적에 비례해 부풀어 있어서입니다. 「이 층 조건이면 하루 몇 개를 팔아야 하나」로 바꿉니다."),
        dict(tag="현실", head=f"추천 자리의 {P2['share_over_avg']}%는 월세만으로도 서울 점포 평균 이상을 팔아야", body=f"요구 월매출 = 월세 ÷ (1 − KOSIS 비임차 비용률). 2배 이상인 자리도 {P2['share_over_2x']}%입니다."),
    ]
    claims = [
        ("개발자 모임 피드백(11-15)", "저장소 밖 사실 — 결정 문서 §0 에 같은 기록", "기록 일치", "mute"),
        ("원인 1 · Posting 은 「어느 전략」을 묻는다", "콘솔 질문 「어떤 비용과 전략으로 입점할까요?」 · R5 「{가격대} 하면 {n개월이면} 본전이에요」 · 랜딩 「얼마짜리 자리가 맞지?」. 단 Page 층별 월세는 추정이라 「실측으로 답한다」는 대체로만 맞음", "맞음", "ok"),
        ("원인 2 · 결론 숫자가 추정 네 겹", "tier_scenarios: 투자비 = 권리금 + 면적 × 손 계수(평당 55·32·20만원) + 고정비 · 매출 = 면적 × 평당 매출 · 비용 = 월세 + 매출 × KOSIS 비용률(0.87~0.88)", "맞음", "ok"),
        ("「296/891」", f"서빙 코드 실호출 재실행 {BASE['lt1']}곳 · 중앙 {BASE['median']}개월로 같음. 분모 891 은 재현 안 됨 → 854(자료 있는 유닛) · 836(추천 있는 유닛) — 「296/836(35.4%)」로 인용", "분자 맞음 · 분모 고침", "decide"),
        ("원인 3 · 7쪽 중 「주변 업종 지도」「찾아오는 길」은 Page 성격", "Posting 콘솔 7쪽 구성 그대로 확인", "맞음", "ok"),
        ("Page 근거 14,520 · 7,548(52%) · 5,655(39%)", f"Gold 전수 빈 층 14,517 · 대장 용도코드 1종 {UC['ledger_ho']['제1종 근린생활시설']:,}(51.5%) · 2종 {UC['ledger_ho']['제2종 근린생활시설']:,}(41.3%) — 키워드 근사라 2종이 334곳 적었음", "근사로 맞음", "decide"),
        ("메뉴 설정이 하루 판매량을 계산한다", "lib/menuPlan.ts menuBep — 기본값은 일부러 없음", "맞음", "ok"),
        ("P1 원천에 인테리어 필드가 있나", "지금 쓰는 15110241 은 평균 매출·면적 단위 매출만. 공공데이터 15143711 에 단위면적 인테리어 금액 · 인테리어 금액 · 점포 기준면적 — 1콜 실측은 미실행(이 환경 권한)", "원천 있음(목록 기준)", "info"),
    ]
    levers = [
        ("추천 전략 투자비 중앙(손 계수)", f"{SUM['inv_q'][1]:,}만원", "서울 외식업 가맹점 평균 창업비 9,610만원의 약 1/8.5 · 인테리어 평균 5,450만원의 약 1/5"),
        ("추천 전략 월매출 중앙(추정)", f"{SUM['rev_q'][1]:,}만원", f"연 {SUM['rev_q'][1] * 12 / 10000:.1f}억 — 공정위 외식업 가맹점 평균 연 3.51억 · 서울 가맹점 평균 연 4.2억의 약 3배"),
        ("빈 층 면적 중앙 vs 가맹점 평균", f"{P2['area_med']}평 vs 17~21평", "매출이 면적에 그대로 비례(고정항 없음) — 큰 층일수록 매출이 커진다. 분기·월 단위 실수는 없음"),
    ]
    decisions = [
        dict(id="①", name="투자비를 공정위 정보공개서 실측으로", status="승인", kind="ok",
             change="손 계수(평당 55·32·20만원 + 고정비) → 업종×가격대 단위면적 인테리어 금액 × 면적 + 최초 부담금(보증금 제외), 표본 부족 칸은 「자료 부족」",
             before=f"{a['hub_name']} {a['area']}평 · 투자 {a['inv_man']:,}만원 → 회수 {a['roi']}개월 「한 달 안에 본전이에요」",
             after=f"서울 인테리어 평균(5,450만원)이면 {a['roi_int545']}개월 · 외식업 창업비 평균(9,610만원)이면 {a['roi_food961']}개월",
             next="공정위 15143711 1콜 확인 → finding → tier_scenarios 교체 → 같은 스냅샷 스크립트로 전·후"),
        dict(id="②", name="네 질문 · 정체성 문장", status="승인 — Platform 문구는 현행 유지", kind="ok",
             change="Page 「어느 층이 비었고, 내 업종이 들어갈 수 있나」 · Posting 「이 층 조건이면 얼마에 몇 개를 팔아야 하나」 · Program 「계약 전에 어떻게 작게 확인하나」(반영됨)",
             before="「기능중심 하면 한 달 안에 본전이에요」",
             after=f"「이 층을 감당하려면 한 달에 {ra[0]:,.0f}만원, 하루 약 {ra[1]:,.0f}만원어치를 팔아야 해요」 — 서울 같은 업종군 점포 평균의 {ra[2]:.1f}배",
             next="Page·Posting 문구는 구현 PR 에서 함께(기능 없이 문구만 먼저 바꾸지 않음)"),
        dict(id="③-b", name="오프라인 마케팅을 Program 「개업 뒤」 칸으로", status="승인·시행", kind="ok",
             change="Program 탭: 가설 설정 → 네트워킹 → 지원 프로그램 → 오프라인 마케팅 솔루션(개업 뒤)",
             before="네트워킹 · 지원 프로그램 · 오프라인 마케팅 · 가설 검증", after="가설 설정이 먼저, 마케팅은 맨 뒤 「개업 뒤」", next="완료 — 바뀐 것 없음"),
        dict(id="③-a", name="인테리어 3D 를 Posting 기본 경로에서 선택 칸으로", status="보류(유일한 미결)", kind="decide",
             change="A 지금(7쪽 · 인테리어 2번째) · B 3쪽 + 인테리어 펼치는 선택 칸(인계 문서 안) · C 3쪽 + 「계약 뒤 준비」 칸",
             before="7쪽에 자리 사실·사업계획·인테리어가 섞임", after="제 의견 B — 질문 하나(요구치)에 집중, 3D 기능은 한 번 더 눌러 바로 열림",
             next="사용자 결정 — 정해지기 전까지 A(11-09 결정) 유지"),
        dict(id="④", name="처리방침에 목적 더하기", status="승인 · 착수 미정", kind="ok",
             change="직접 입력한 계약 조건(보증금·월세)과 답사 기록을 동의한 경우에만 임대료 추정 정확도 통계(익명 집계)에 씀",
             before="목적: 저장한 작업 불러오기까지", after="선택 동의 + 익명 집계 · 탈퇴 시 원래 값 즉시 삭제, 통계 숫자만 남음",
             next="PrivacyNote · privacy.html · delete_account 를 받는 항목을 늘리는 PR 에서 함께"),
    ]
    metrics = [
        ("P1 투자비 실측", f"1개월 미만 {BASE['lt1']} · 투자비 중앙 {SUM['inv_q'][1]:,}만원", f"1개월 미만 {X3['lt1']}~{S545['lt1']} · 중앙 {X3['median']}~{S961['median']}개월", "계산"),
        ("P2 요구치", f"머리 문장 = 회수기간(「한 달 안에」 {BASE['lt1']}곳)", f"하루 판매·월매출 + 서울 점포 평균 대비 배수 · 추천 자리 {P2['share_over_avg']}%가 「평균 이상」", "계산"),
        ("P3 들은 금액 우선", "세 가격대 월세는 R-ONE 추정(권리금·면적만 입력)", "입력이 있으면 추정을 이김 · 없으면 범위로", "설계"),
        ("P4 근거 배지", "아직 세지 않음", "배지 없는 숫자 0(테스트로 고정)", "설계"),
        ("Posting 7쪽 → 3쪽", "7쪽(인테리어 2번째)", "3쪽 + 선택 칸 — 인테리어 위치는 ③-a 뒤", "설계"),
        ("2-E Page 층 상세 「내 업종」", "흐름 R4 · 후보 비교에만(main)",
         f"음식점: 가능 {rest['ledger_ok']:,} · 확인 필요 {rest['needs_check']:,} · 용도 변경 필요 {rest['use_change_needed']:,} · 금지 {rest['zoning_prohibited']:,} · 자료 부족 {rest['missing_inputs']:,}", "측정"),
        ("2-C 입점 점검 실력", "사전등록 초안 · 채점 전", "인허가 정답지 대조 — 채점 전엔 말하지 않음", "모름"),
        ("④ 처리방침", "입력 월세를 KPI 에 쓸 근거 없음", "동의한 값으로 층별 임대료 오차 KPI", "설계"),
    ]
    scen = [(lab, [SC[lab]["bins"][b] for b in BIN], f"중앙 {SC[lab]['median']}개월") for lab in
            ("현행 손 계수(재현)", "투자비 ×3", "인테리어 서울 평균 5,450만원(면적 무관)", "외식업 창업비용 서울 평균 9,610만원(면적 무관)")]
    hist = [(lab, sum(1 for x in ratios if lo <= x < hi)) for lo, hi, lab in edges]
    usecheck = [("음식점·술집", uc["restaurant"]), ("카페·디저트", uc["cafe"]), ("병·의원", uc["clinic"]), ("약국·편의점·옷", uc["pharmacy"]),
                ("미용·네일", uc["beauty"]), ("학원·교육", uc["education"]), ("운동·여가", uc["fitness"])]
    menu = []
    for ind in MD.INDUSTRIES:
        row = {"label": ind["label"], "tiers": {}}
        for tk in ("premium", "value", "factory"):
            s = MP.tier_summary(ind, tk)
            row["tiers"][tk] = dict(price=s["avg_price"], rate=s["cost_rate"], daily=s["daily"], pm=s["periodic_month"], first=s["first_order"], pre=s["pre_open"])
        menu.append(row)
    overlap = [
        ("N1 견적 입력 · N3 계약 월세·보증금", "P1 · P3", "유지 — 사용자 금액이 추정·평균보다 앞섬"),
        ("N6 민감도(회수기간)", "P2", "고쳐서 유지 — 「하루 몇 개」 기준으로"),
        ("N7 인건비 · N10 카드수수료·간이과세", "P2 입력", "유지"),
        ("N9 개·폐업률 · N11 계약 전 체크리스트", "Posting ③ 계약 전 확인", "유지 — 입점 점검 결과를 자동으로 채움"),
        ("N2 층 용도로 본 음식점 영업", "2-E", "철회 — main use_check(다섯 갈래)가 정본"),
        ("N4 공실 이력 · N5 월세·면적 필터 · N8 건물 연식", "2-A", "유지 — Page 층 상세의 자리 사실"),
    ]
    sources = [
        ("공공데이터포털 15143711 — 공정위 가맹사업자 부담금·인테리어비용", "https://www.data.go.kr/data/15143711/openapi.do"),
        ("한국경제 — 2025 서울시 가맹사업 등록현황", "https://www.hankyung.com/article/202606229186Y"),
        ("뉴시스 — 공정위 2025 가맹사업 현황", "https://mobile.newsis.com/view/NISX20260411_0003587198"),
        ("농식품부 — 2025 외식업체 경영실태조사", "https://www.mafra.go.kr/bbs/home/792/577439/artclView.do"),
        ("경북매일 — 참가격 서울 외식비(2026-09)", "https://kbmaeil.com/article/20261111500032"),
        ("세계일보 — KAMIS 쌀 20kg", "https://www.segye.com/newsView/20260108514984"),
    ]
    return dict(
        title="Page·Posting 인계 — 검증 · 결정 · 전/후 · 메뉴 예시",
        core=core, claims=claims, levers=levers, decisions=decisions, metrics=metrics, scen=scen, hist=hist,
        hist_note=f"중앙 {P2['ratio_med']}배 · 사분위 {P2['ratio_q1']}~{P2['ratio_q3']}배", usecheck=usecheck, menu=menu,
        overlap=overlap, sources=sources, persona=dict(daily=t414["daily"], price=t414["avg_price"], rate=t414["cost_rate"]),
        ra=ra, a=a, k=k, base=BASE, x3=X3, s545=S545, s961=S961, p2=P2,
    )


# 검증 기준 — 모든 유형에 들어가야 하는 사실(글자 그대로 찾는다)과, 첫 화면에 보여야 하는 핵심 5가지
FACTS = ["모두 사실", "296", "836", "35.4%", "854", "14,517", "7,472", "5,989", "1,130만원", "9,610만원", "5,450만원",
         "1.5개월", "6.5개월", "48.8%", "16.4%", "③-a", "보류", "491", "6,099", "3,943", "15143711", "요구치",
         "주기 구매", "개업 첫 주문", "31커밋"]
CORE_TOKENS = ["모두 사실", "296", "③-a", "요구치", "48.8%"]
