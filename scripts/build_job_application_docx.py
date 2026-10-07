# -*- coding: utf-8 -*-
"""기술지주회사·산학협력단·창업지원단 지원용 서류 3종 .docx 생성기.

만드는 것
  1) 이력서          — 1~2쪽. 신상·학력·경력은 **빈칸 템플릿**(지어내지 않는다)
  2) 경력기술서      — 역할 / 기간 / 사용 기술 / 정량 성과 4항목 고정
  3) 포트폴리오      — PlaceOS 실측 산출물 + 검증 방법론

규칙
- 수치는 `python scripts/pppp_status.py` · `scripts/kpi_baseline.py` 산출물에서만 인용한다.
  본인 신상(성명·학력·경력·자격)은 저장소에 없으므로 **[ ] 로 남긴다**. 추정해 채우지 않는다.
- 한글 폰트는 임베딩한다(폰트명만 지정하면 뷰어에서 □ 로 깨진다).
  → build_business_plan_docx 의 subset → ECMA-376 §17.8.1 난독화 → fontTable 배선을 그대로 쓴다.
- 이모지·기호는 쓰지 않는다. subset 대상에 없으면 빈칸으로 렌더된다.

실행:
    python scripts/build_job_application_docx.py [-d 출력디렉터리] [--fonts 폰트캐시]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_business_plan_docx as bp  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

J = WD_ALIGN_PARAGRAPH.JUSTIFY
C = WD_ALIGN_PARAGRAPH.CENTER
L = WD_ALIGN_PARAGRAPH.LEFT
R = WD_ALIGN_PARAGRAPH.RIGHT

BLANK = "[                              ]"
FILL = "[ 채울 것 ]"

# 저장소 실측값 (2026-10-04 기준 · 줄 수와 테스트 수는 2026-10-07 `bd2517c` 기준으로 다시 쟀다).
# 숫자마다 산출 근거를 붙인다 — 근거 없는 값은 쓰지 않는다.
#   S1 = python scripts/pppp_status.py      S2 = python scripts/kpi_baseline.py
# 세는 방법은 10-04 말 커밋 `34d1678` 에 대 보고 옛 값이 그대로 나오는지로 검증했다(줄 수 69,686 · 백엔드 파일 34 ·
# 백엔드 collect 420 이 재현됨). 프론트 파일 수만 17 이 재현되지 않았다 — 그 방법(`*.test.*`)으로는 그때도 19 였다.
M = {
    # S1 — 서빙 거점(page_hubs.ACTIVE_HUBS) · 트랙 진행률
    "hubs": "81",
    "page": "100.0",
    "platform": "66.7",          # 남은 두 게이트가 LSTM 확인대기라 100 이 아니다
    "posting": "100.0",
    "program": "100.0",
    "gates": "27",               # 진행률 게이트 수 · 그중 선언형(사람이 판정) 8개
    "gates_declared": "8",
    # S1 — 공실 인벤토리: 81/81거점 840유닛 / data/gold/*/vacant_floor_units.json 합계(certainty 로 분리)
    "units": "840",
    "floor_units": "15,366",
    "floor_conf": "11,770",
    "floor_prob": "3,596",
    # git ls-files 의 py/ts/tsx/js/jsx 줄 수 (2026-10-07 bd2517c · 10-04 34d1678 에서는 69,686)
    "loc": "73,432",
    # S2 — LSTM 공실 예측 (reg-0928 서빙본 · 홀드아웃 240 · 거점 80곳). 두 축 모두 '참고' 판정이고
    #      게이트는 20262 이후 분기 표본 전에는 닫히지 않는다(확인대기).
    "lstm_n": "240",
    "lstm_mae": "0.822",
    "lstm_persist": "1.190",     # 지속성(직전 분기값) MAE
    "lstm_base": "0.998",        # 거점 평균 MAE — 두 무정보 규칙 중 강한 쪽 = 대조군
    "lstm_skill": "+17.6",
    "lstm_skill_ci": "+11.6, +24.5",
    "lstm_dir": "80.0",
    "lstm_dir_base": "68.8",     # '평균 쪽' 규칙 — 상수 '항상 하락' 55.0% 보다 강해 이쪽이 대조군
    "lstm_dir_const": "55.0",
    "lstm_dir_skill": "+11.3",
    "lstm_dir_ci": "+5.4, +17.1",
    # S2 — GNN 업종 추천 (81거점 · 09-27 · 어휘 group_mapped)
    "gnn_top3": "92.0",
    "gnn_prior": "88.7",
    "gnn_skill": "+3.36",
    "gnn_ci": "+2.78, +3.95",
    "gnn_test": "17,650",
    "gnn_nodes": "88,238",
    "gnn_feat": "132",
    # 서빙 81거점 840유닛에 districts.tier_scenarios 를 직접 호출해 센 값
    #   (scripts/posting_cost_sensitivity.py 의 528유닛은 시드 54거점 표본이라 서빙 전체가 아니다)
    "roi_units": "840",
    "roi_fail": "0.5",           # 4/840
    "roi_fail_n": "4",
    "roi_win": "620",            # 기능중심(factory)이 회수 최단인 유닛
    "roi_real": "827",           # 실측 매출 모델이 도는 유닛 (폴백 13 · garak · bulgwang)
    "roi_hubs_real": "79",
    # 테스트: pytest --collect-only (apps/backend) · 프론트는 *.test.* 파일 수 (2026-10-07 bd2517c)
    #   · 백엔드 collect: 10-04 420 → 493 · 백엔드 파일(tests/test_*.py): 34 → 41 · 프론트 파일: 10-04 19(스크립트엔 17) → 24
    "tests_be": "493",
    "tests_be_files": "41",
    "tests_fe_files": "24",
    # 09-16 에 지표 결함을 발견한 시점의 값(역사) — 현재 값과 섞어 쓰지 않는다
    "leak_dir_model": "70.8",
    "leak_dir_const": "78.5",
    "leak_gnn_prior": "89.4",
    "bundle_before": "832",
    "bundle_after": "4",
}


# ══════════════════════════════════════════════════════════════════════════
#  공통 조각
# ══════════════════════════════════════════════════════════════════════════
def doc_title(doc, title, sub):
    p = bp.para(doc, before=0, after=1, line=1.1)
    bp.run(p, title, size=26, bold=True, color=bp.NAVY, spacing=-14)
    p = bp.para(doc, before=0, after=4, line=1.3)
    bp.run(p, sub, size=10, color=bp.MUTED)
    bp.para_border(p, ("bottom",), color=bp.NAVY, sz=12, space=9)


def label_row(doc, pairs):
    """이름: 값 형태의 얇은 2열 표."""
    bp.make_table(doc, pairs, [3.6, 12.2], head=False, sizes=[9.0, 9.0],
                  aligns=[L, L], zebra=False, bold_first_col=True)


def guide(doc, lines):
    bp.note_box(doc, [(t, b) for t, b in lines])


# ══════════════════════════════════════════════════════════════════════════
#  1) 이력서
# ══════════════════════════════════════════════════════════════════════════
def build_resume(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "이력서")

    doc_title(doc, "이 력 서", "Resume · 지원 분야: 창업보육 (보육매니저 · 창업지원)")

    bp.h2(doc, "01", "인적사항")
    label_row(doc, [
        ["성명 (한글 / 한자)", BLANK],
        ["생년월일", BLANK],
        ["주소", "[ 시 / 구 까지만 기재 — 상세주소는 최종합격 후 ]"],
        ["휴대전화", BLANK],
        ["이메일", "seoghyeonbag36@gmail.com"],
        ["포트폴리오", "https://placeos.web.app"],
        ["병역 / 보훈 / 장애", "[ 해당 시에만 기재 ]"],
    ])
    bp.caption(doc, "주민등록번호는 기재하지 않는다. 기관 채용은 최종합격 후 별도 서식으로 수집한다.")

    bp.h2(doc, "02", "지원 포지션 및 한 줄 요약")
    label_row(doc, [
        ["지원 기관", FILL],
        ["지원 부문", "[ 공고에 적힌 부문명을 그대로 옮길 것 ]"],
        ["공고번호", FILL],
    ])
    bp.body(doc,
            "오프라인 상권을 데이터로 재구성하는 SaaS 두 종(PlaceOS · Co.I)을 기획부터 배포까지 "
            "단독으로 수행했습니다. 데이터 수집 파이프라인, 예측 모델, API, 프론트엔드, 클라우드 배포까지 "
            "한 사람이 전 구간을 담당했고, 두 서비스 모두 데모가 아니라 운영 중입니다.",
            before=6)

    bp.h2(doc, "03", "핵심 역량")
    bp.bullets(doc, [
        ("데이터 파이프라인 설계 · ",
         "공공 API(건축물대장 · 상권분석 · R-ONE · KOSIS)를 Bronze/Silver/Gold 3계층으로 "
         f"정규화해 서울 {M['hubs']}개 거점의 건물 단위 공실 인벤토리를 구축했습니다."),
        ("예측 모델 개발 · ",
         "시계열 공실 예측(LSTM)과 업종 추천(GNN)을 학습·서빙까지 연결했습니다. "
         "성능은 임계값이 아니라 무정보 베이스라인 대비 개선폭으로 관리합니다."),
        ("제품화 · ",
         "FastAPI + React 스택을 GitHub Actions - Cloud Run 파이프라인에 올려 "
         "테스트 통과 시에만 배포되도록 구성했습니다."),
        ("검증 설계 · ",
         "자기 지표의 결함을 스스로 찾아내 지표 체계 전체를 재정의한 경험이 있습니다. "
         "아직 확정되지 않은 값은 달성이 아니라 '확인대기'로 둡니다. 상세는 경력기술서 4장."),
    ])

    bp.h2(doc, "04", "주요 프로젝트")
    bp.make_table(doc, [
        ["프로젝트", "기간", "역할", "내용"],
        ["PlaceOS",
         "2026.05 ~\n현재",
         "기획 · 개발\n(단독)",
         "오프라인 상권 디지털 트윈 플랫폼.\n건물 단위 공실 인벤토리 + 공실 예측 · 업종 추천 + 입점 ROI · 창업 검증 program 생성"],
        ["Co.I",
         FILL,
         "기획 · 개발\n(단독)",
         "창업 코파일럿 AI.\n" + FILL],
    ], [3.0, 2.2, 2.4, 8.2], sizes=[9.0, 8.5, 8.5, 9.0],
        aligns=[L, C, C, L], bold_first_col=True)
    bp.caption(doc, "상세 내역은 별첨 경력기술서 · 포트폴리오 참조.")

    bp.h2(doc, "05", "보유 기술")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["Backend", "Python 3.11, FastAPI, PostgreSQL (계정 · 조직 · 사용량), SQLAlchemy, Alembic"],
        ["ML · LLM", "PyTorch, PyTorch Geometric (GNN), LSTM, MLflow / Anthropic SDK (생성 엔진 직접 호출)"],
        ["Frontend", "React, TypeScript, Vite, 네이버 지도 API (지도 · 거리뷰)"],
        ["Data", "Selenium / Playwright 수집기, Bronze / Silver / Gold 3계층 설계, 일일 쿼터 런북"],
        ["Infra", "Docker, GitHub Actions, Google Cloud Run, Firebase Hosting"],
        ["공공데이터", "건축HUB 건축물대장, 서울시 상권분석, R-ONE 부동산통계, KOSIS, 공정위 정보공개서"],
    ], [3.0, 12.8], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    bp.h2(doc, "06", "학력")
    bp.make_table(doc, [
        ["기간", "학교 / 전공", "학위", "비고"],
        [BLANK, BLANK, FILL, FILL],
        [BLANK, BLANK, FILL, FILL],
    ], [3.6, 6.4, 2.6, 3.2], sizes=[8.5, 9.0, 8.5, 8.5], aligns=[C, L, C, L])
    bp.caption(doc, "최종 학력부터 역순으로 기재한다.")

    bp.h2(doc, "07", "경력")
    bp.make_table(doc, [
        ["기간", "기관 / 부서", "직위", "담당 업무"],
        [BLANK, BLANK, FILL, FILL],
        [BLANK, BLANK, FILL, FILL],
    ], [3.6, 5.0, 2.2, 5.0], sizes=[8.5, 9.0, 8.5, 8.5], aligns=[C, L, C, L])
    bp.caption(doc, "경력이 없으면 행을 지우고 '해당 없음'으로 적는다. 빈 표를 남기지 않는다.")

    bp.h2(doc, "08", "자격 · 교육 · 수상")
    bp.make_table(doc, [
        ["취득일", "명칭", "발급 기관"],
        [BLANK, BLANK, BLANK],
        [BLANK, BLANK, BLANK],
    ], [3.2, 7.4, 5.2], sizes=[8.5, 9.0, 9.0], aligns=[C, L, L])
    bp.caption(doc, "기술사업화 직무는 특허 출원 · 등록 실적을 이 표 최상단에 둔다.")

    guide(doc, [
        ("작성 안내", True),
        ("1. 공고에 지정 양식(hwp / xlsx)이 있으면 이 문서를 쓰지 말고 그 양식에 옮겨 적는다. "
         "기관 채용은 자유 양식을 반려한다.", False),
        ("2. [ ] 로 남긴 칸은 저장소 자료로 확인할 수 없어 비워 둔 곳이다. 직접 채운다.", False),
        ("3. 첫 메일에는 주민등록번호 · 상세주소 · 졸업증명서 · 희망연봉 · 대학원 진학 계획을 넣지 않는다.", False),
        ("4. 파일명은 공고가 지정한 규칙을 그대로 따른다. 지정이 없으면 "
         "'[부문]성명_이력서.pdf' 로 변환해 제출한다.", False),
    ])

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
#  2) 경력기술서
# ══════════════════════════════════════════════════════════════════════════
def proj_head(doc, num, title, rows):
    bp.h2(doc, num, title)
    bp.make_table(doc, rows, [3.0, 12.8], head=False, sizes=[9.0, 9.0],
                  aligns=[L, L], zebra=False, bold_first_col=True)


def build_experience(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "경력기술서")

    doc_title(doc, "경 력 기 술 서",
              "Statement of Experience · 성명: " + BLANK)

    bp.h1(doc, "1", "요약")
    bp.body(doc,
            "오프라인 상권을 데이터로 재구성하는 SaaS 두 종을 기획부터 배포까지 단독으로 수행했습니다. "
            "수집 파이프라인, 예측 모델, API, 화면, 배포까지 전 구간을 담당했으며, 두 서비스 모두 "
            "운영 중입니다. 아래 정량 성과는 모두 저장소의 산출물 계측 스크립트에서 산출한 값이며, "
            "아직 확정되지 않은 항목(공실 예측 두 축)도 확인대기로 그대로 기재했습니다.")
    bp.make_table(doc, [
        ["항목", "값", "산출 근거"],
        ["대상 상권", f"서울 {M['hubs']}개 거점", "건축물대장 실측 (Tier1)"],
        ["공실 인벤토리", f"{M['units']}유닛 (층 단위 {M['floor_units']}개)",
         f"확정 {M['floor_conf']} / 추정 {M['floor_prob']}"],
        ["코드 규모", f"{M['loc']} 라인 (Python · TypeScript)", "git ls-files 기준"],
        ["트랙 진행률",
         f"Page {M['page']}% · Posting {M['posting']}% ·\nProgram {M['program']}% · Platform {M['platform']}%",
         "scripts/pppp_status.py"],
    ], [3.4, 6.2, 6.2], sizes=[9.0, 9.0, 8.5], aligns=[L, L, L], bold_first_col=True)

    # ── PlaceOS ─────────────────────────────────────────────────────────
    bp.h1(doc, "2", "PlaceOS — 오프라인 상권 디지털 트윈 플랫폼")
    proj_head(doc, "2.1", "프로젝트 개요", [
        ["기간", "2026.05 ~ 현재 (진행 중)"],
        ["역할", "기획 · 아키텍처 설계 · 전 구간 개발 · 배포 (단독)"],
        ["사용 기술",
         "Python 3.11, FastAPI, PostgreSQL (계정 · 조직 · 사용량), SQLAlchemy, Alembic / "
         "PyTorch, PyTorch Geometric, MLflow, Anthropic SDK / "
         "React, TypeScript, Vite, 네이버 지도 API / "
         "Docker, GitHub Actions, Google Cloud Run, Firebase Hosting"],
        ["운영 주소", "https://placeos.web.app"],
        ["문제 정의",
         "상권 정보가 '어느 동네가 뜨는가' 수준의 행정동 통계에 머물러, "
         "'어느 건물 몇 층이 비었고 거기에 무엇이 들어가야 하는가'를 답하지 못한다."],
        ["해결 접근",
         "건축물대장을 실측 원천으로 삼아 건물 - 층 - 유닛 단위 공실 인벤토리를 세우고, "
         "그 위에 공실 예측 · 업종 추천(Platform), 층별 공실(Page), 입점 ROI(Posting), "
         "창업 검증 program 생성(Program) 네 트랙을 얹었다."],
    ])

    bp.h2(doc, "2.2", "Platform — 상권 AI 추천 엔진")
    bp.bullets(doc, [
        ("담당 · ", "LSTM 공실 예측 모델과 GNN 업종 추천 모델의 데이터셋 구성, 학습, 서빙 연동."),
        ("규모 · ",
         f"GNN 그래프 노드 {M['gnn_nodes']}개 · 피처 {M['gnn_feat']}열 · {M['hubs']}거점."),
        ("성과 (업종 추천 · 확정) · ",
         f"Top-3 정확도 {M['gnn_top3']}% — 거점 사전분포 베이스라인 {M['gnn_prior']}% 대비 "
         f"{M['gnn_skill']}%p ({M['gnn_ci']} · 95% 구간 · test {M['gnn_test']}자리)."),
        ("성과 (공실 예측 · 참고) · ",
         f"MAE {M['lstm_mae']} — 무정보 규칙 둘(지속성 {M['lstm_persist']} · 거점 평균 "
         f"{M['lstm_base']}) 중 강한 쪽인 거점 평균 대비 {M['lstm_skill']}% "
         f"({M['lstm_skill_ci']} · 홀드아웃 {M['lstm_n']}건). 방향 정확도 {M['lstm_dir']}% — "
         f"강한 쪽 대조군('평균 쪽' 규칙) {M['lstm_dir_base']}% 대비 {M['lstm_dir_skill']}%p "
         f"({M['lstm_dir_ci']})."),
        ("아직 확정하지 않은 것 (그대로 기재) · ",
         "위 공실 예측 두 값은 '참고 판정'입니다. 이미 본 분기로는 확정하지 않는다는 규칙을 "
         "사전에 못박아 두었고, 2026년 3분기 데이터가 공표된 뒤에만 닫습니다. "
         "그 전까지 이 두 축은 달성이 아니라 확인대기입니다."),
    ])

    bp.h2(doc, "2.3", "Page — 공실 히트맵 · 층별 매물 · 거리뷰")
    bp.bullets(doc, [
        ("담당 · ", "건축HUB 건축물대장 수집기, 주소 정규화, 층별 공실 판정 파이프라인, 지도 화면."),
        ("성과 · ",
         f"{M['hubs']}개 거점 전부를 건축물대장 실측(Tier1)으로 올렸고, 대표 집계 커버리지 100%, "
         "R-ONE 앵커 대조 체계를 갖췄습니다."),
        ("최적화 · ",
         f"3D 렌더링이 실측 형상이 아니라 층 상태를 색으로 표현할 뿐임을 확인하고 2D 층 스택 + "
         f"거리뷰로 대체해 번들을 {M['bundle_before']}KB에서 {M['bundle_after']}KB로 줄였습니다."),
    ])

    bp.h2(doc, "2.4", "Posting — 입점 의사결정 · ROI 시뮬레이션")
    bp.bullets(doc, [
        ("담당 · ", "3-Tier 비용-효용 모델, 매출 추정 앵커링, 외부 코파일럿 연동 어댑터 설계."),
        ("성과 · ",
         f"서빙 {M['hubs']}거점 {M['roi_units']}유닛 기준 회수불가 {M['roi_fail_n']}유닛"
         f"({M['roi_fail']}%), 기능중심 티어가 회수 최단인 유닛 {M['roi_win']}개. "
         "공정위 가맹사업 정보공개서와 KOSIS를 교차 검증해 평당매출을 업계 통상 대역 안으로 "
         "맞췄습니다."),
        ("발견한 결함 (1) · ",
         "임대료를 1층 기준으로 계산하던 초기 모델이 실제 상업층 분포와 맞지 않아 "
         "임대료를 중앙값 기준 45% 과대계상하고 있었습니다. 층별 면적 비중으로 가중 평균해 "
         "바로잡았고, 두 모델이 참값을 사이에 두는 상한 - 하한 관계임을 테스트로 고정했습니다."),
        ("발견한 결함 (2) · ",
         "매출 산출물이 시드 54거점으로만 빌드된 채 서빙이 81거점으로 늘어, 28거점이 근거 없는 "
         "폴백 계수로 계산되고 있었습니다(840유닛 중 313유닛 · 마진 중앙 76.6% · 회수 1.1개월 — "
         "비현실적인 값). 81거점으로 재빌드해 실측 모델 거점 "
         f"{M['roi_hubs_real']}개 · {M['roi_real']}/{M['roi_units']}유닛으로 올렸고, 같은 "
         "사고를 막는 테스트(산출물이 서빙 거점 수와 다르면 실패)를 더했습니다. 폴백 13유닛"
         "(2거점)은 표본 부족으로 그대로 남아 있으며, 응답이 어느 모델이 돌았는지 밝힙니다."),
    ])

    bp.h2(doc, "2.5", "Program — 창업 아이템 검증 program 자동 생성")
    bp.bullets(doc, [
        ("대상 · ",
         "예비창업자, 그리고 자기 아이템이 통하는 상권을 찾아 팝업스토어 · 가오픈 · MVP 로 "
         "검증하려는 기창업자. 영업 중인 가게의 마케팅은 이 트랙이 아닙니다(2026-09-17 대상 재정의)."),
        ("담당 · ",
         "검증 브리프 입력 계약(아이템 · 검증 방식 · 단계 · 가설 · 기간 · 예산 구간), "
         "모객 · 자리 · 상권 연계 세 벌의 출력, LLM 생성 엔진(Anthropic SDK 직접 호출), "
         "생성물 사실성 검증 가드(ha_guard)."),
        ("설계 원칙 · ",
         "무엇을 세면 통했다고 할지 시작 전에 정하지 않은 검증은 판정이 아니라 지출이라고 보고, "
         "출력에 검증 지표(지표 · 측정 방법 · 목표선 · 기각 조건)를 반드시 포함시켰습니다."),
        ("성과 · ",
         "아직 해 보지 않은 아이템에 '단골'이나 '쌓인 후기'를 근거로 삼는 문장을 서버 검증으로 "
         "차단합니다(측정 문장은 면제 — 재방문율 같은 검증 지표를 막지 않기 위해). 예산 항목을 "
         "정수 퍼센트 타입으로 강제해 허구의 절대 금액이 구조적으로 들어갈 수 없게 했습니다."),
        ("접근 통제 · ",
         "조직 · API 키 인증 계정층과 접근 감사 로그를 두었습니다."),
    ])

    # ── Co.I ────────────────────────────────────────────────────────────
    bp.h1(doc, "3", "Co.I — 창업 코파일럿 AI")
    proj_head(doc, "3.1", "프로젝트 개요", [
        ["기간", BLANK],
        ["역할", "기획 · 개발 (단독)"],
        ["사용 기술", FILL],
        ["운영 주소 / 저장소", FILL],
        ["문제 정의", FILL],
        ["해결 접근", FILL],
    ])
    guide(doc, [
        ("Co.I 장 작성 안내", True),
        ("이 장은 저장소에 자료가 없어 비워 두었습니다. 아래 네 항목을 채우면 2장과 같은 밀도가 됩니다.", False),
        ("1. 무엇을 자동화했는가 — 창업자가 원래 며칠 걸리던 어떤 판단을 몇 분으로 줄였는가.", False),
        ("2. 무엇을 근거로 답하는가 — 검색인가, 내부 데이터인가, 생성인가. 환각을 무엇으로 막는가.", False),
        ("3. 정량 지표 — 응답 시간, 처리한 질의 수, 정답률 또는 사용자 평가. 없으면 지금 재 둔다.", False),
        ("4. PlaceOS 와의 관계 — PlaceOS 는 Posting 트랙에서 외부 코파일럿 어댑터 계약을 "
         "이미 발행해 두었으므로, Co.I 를 그 자리에 붙이는 구조로 설명하면 두 프로젝트가 "
         "하나의 이야기가 됩니다.", False),
    ])

    # ── 문제해결 사례 ────────────────────────────────────────────────────
    bp.h1(doc, "4", "문제 해결 사례")
    bp.h2(doc, "4.1", "자사 지표의 결함을 스스로 찾아 지표 체계를 재정의")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["상황", "AI 정확도 70% 이상을 목표로 두고, 두 모델 모두 그 선을 넘겼다고 보고하고 있었다."],
        ["과제",
         "같은 홀드아웃에서 입력을 전혀 보지 않는 규칙이 이미 그 선을 넘는지 확인했다."],
        ["행동",
         f"무정보 베이스라인을 계산했다. 2026-09-16 시점에 공실 예측 방향은 '항상 하락' 상수가 "
         f"{M['leak_dir_const']}% (모델 {M['leak_dir_model']}%), 업종 추천 Top-3 은 거점 사전분포가 "
         f"{M['leak_gnn_prior']}% 였다. 즉 임계값을 넘겼다는 사실에 정보가 없었고, 그 달성 표기가 "
         "진행률 문서와 외부 원고까지 퍼져 있었다."],
        ["결과",
         "!임계값 단독 판정을 폐기하고 베이스라인 대비 실력으로 전 지표를 재정의했다. "
         "네 규칙(임계값 단독 금지 / 불확실성 동반 / 선택과 보고 분리 / 계측기 없는 목표는 "
         "지표가 아님)을 세우고, 실력이 확인되지 않은 축이 하나라도 있으면 종료코드 1을 내는 "
         "검사 스크립트로 못박았다."],
    ], [2.4, 13.4], sizes=[9.0, 9.0], aligns=[C, L], bold_first_col=True)
    bp.body(doc,
            "그 뒤에도 이 체계 자체를 두 번 고쳤습니다. 누수를 막은 재학습(81거점 · 홀드아웃 "
            f"{M['lstm_n']}건)에서 방향 축이 +4.6%p 였는데 신뢰구간이 0 을 품는데도 점추정 부호만으로 "
            "게이트가 닫혀 있었습니다. 그래서 판정을 '실력 · 구분불가 · 열위 · 검정불가' 세 갈래 "
            "(표본이 없으면 검정불가)로 바꾸고 '실력'일 때만 닫히게 했습니다. 이어서 대조군을 두 무정보 "
            "규칙 중 강한 쪽으로 올리고 학습 조건을 사전에 등록했습니다. 그 과정에서 참고 판정용 분기가 "
            "한 번 노출됐던 사실도 문서에 남겼고, 그래서 확정은 이후 분기 데이터로만 하기로 했습니다. "
            "현재 공실 예측 두 축은 참고 판정이 '실력'이지만 확정은 확인대기입니다.", before=4)

    bp.h2(doc, "4.2", "계측기 없는 목표를 먼저 계측 가능하게 만들기")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["상황", "API 응답 p95 200ms 미만, 지도 로딩 3초 미만을 성능 목표로 걸어 두고 있었다."],
        ["과제", "그 목표를 재는 코드가 저장소에 한 줄도 없다는 것을 확인했다."],
        ["행동",
         "지연 계측 미들웨어와 클라이언트 타이밍 수집 경로를 만들고 관리자 조회 창구를 냈다. "
         "표본이 기준 미만이면 계측기가 스스로 판정을 보류하도록 했고, 클라이언트 자가보고 값은 "
         "저장 키 접두사로 서버 실측과 구분했다."],
        ["결과",
         "!배선 완료와 목표 달성을 문서에서 분리했다. 재지 않은 것을 달성으로 적지 않는 것이 "
         "이 프로젝트의 기본 규칙이 되었다."],
    ], [2.4, 13.4], sizes=[9.0, 9.0], aligns=[C, L], bold_first_col=True)

    bp.h2(doc, "4.3", "수집이 아니라 배선이 병목임을 반복 확인")
    bp.body(doc,
            "'데이터가 없어서 못 한다'고 문서에 적혀 있던 항목 다섯 건을 실제로 확인한 결과, "
            "네 건이 이미 저장소 안에 재료가 있는데 서빙 코드가 읽지 않고 있던 경우였습니다. "
            "유동인구 좌표, 공실 유닛 인벤토리, 층별 점유 정보, 임대료 기준선이 모두 그랬습니다. "
            "이후로는 문서의 서술을 믿지 않고 1회 실측으로 확인한 뒤 그 결과를 별도 문서로 "
            "남기는 절차를 두었습니다.", before=4)

    bp.h2(doc, "4.4", "통계상 '실력'이 나왔지만 서빙하지 않은 사례")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["상황", f"업종 추천(GNN)을 {M['hubs']}거점으로 재학습했다. 판정 도구는 거점 사전분포 대비 "
                 "+1.88%p 로 통계적 '실력'을 냈다."],
        ["과제", "판정이 닫히는 것과 그 추천을 제품으로 내보내도 되는 것은 별개인지 서빙 산출물을 "
                 "직접 열어 확인했다."],
        ["행동",
         "1순위 추천의 74%, 3순위 안의 100%가 '미분류'였다. 판정 도구는 추천 어휘가 쓸 수 있는지는 "
         "묻지 않기 때문에 제품으로는 틀린 '실력'이었다. 서빙 파일을 이전 본으로 되돌리고, 라벨 "
         "어휘를 먼저 정한 뒤 재학습했다."],
        ["결과",
         "!판정 도구에 어휘 점검 세 항목(라벨 수준 일치 · 미분류 0건 · 라벨 6종 이상)을 붙였다. "
         "재학습 결과는 Top-3 " + f"{M['gnn_top3']}% (사전분포 {M['gnn_prior']}%, "
         f"{M['gnn_skill']}%p [{M['gnn_ci']}]). 다만 추천 어휘 7종 중 문화시설은 이 모집단에 "
         "나타나지 않아 6종으로 서빙한다."],
    ], [2.4, 13.4], sizes=[9.0, 9.0], aligns=[C, L], bold_first_col=True)

    bp.h1(doc, "5", "일하는 방식")
    bp.bullets(doc, [
        ("측정 우선 · ", "재지 않은 값은 달성으로 적지 않습니다. 미달 항목은 미달로 남깁니다."),
        ("낡은 서술 추적 · ",
         "같은 산출물 안에서 두 곳이 다른 말을 하는 것을 주된 실패 양식으로 보고, "
         "폐기한 결정도 지우지 않고 경위를 남깁니다."),
        ("테스트로 고정 · ",
         "합의한 전제는 문장이 아니라 테스트와 타입으로 고정합니다. "
         "예: 예산 항목을 정수 퍼센트 타입으로 두어 절대 금액이 구조적으로 들어갈 수 "
         f"없게 했습니다. 현재 백엔드 테스트 {M['tests_be']}개({M['tests_be_files']}개 파일)와 "
         f"프론트 테스트 {M['tests_fe_files']}개 파일이 GitHub Actions 에서 돌고, "
         "통과해야만 배포됩니다."),
        ("서빙 거점 기준 검사 · ",
         "Posting 매출 산출물이 시드 거점 수가 아니라 서빙 거점 수를 따라가는지 재는 테스트를 "
         "두었습니다. 거점이 늘었는데 빌더를 다시 돌리지 않으면 CI 가 실패합니다."),
        ("검증 절차 · ",
         "변경 직후 정적 3종(백엔드 테스트 · 프론트 빌드 타입체크 · 모델 임포트)을 항상 "
         "돌립니다. 다만 이 저장소에서 실제로 밟은 함정은 전부 '테스트는 통과하는데 화면과 "
         "데이터가 틀린' 자리에서 나왔기 때문에, 로컬에서 앱을 띄워 API 응답과 지도 화면까지 "
         "확인하는 절차를 따로 두고 있습니다."),
        ("도구 · ",
         "Cursor 와 Claude Code 를 활용해 개발합니다. 무엇을 만들지와 그 결과가 맞는지는 "
         "제가 판단하며, 위 검증 체계가 그 판단을 강제합니다."),
    ])

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
#  3) 포트폴리오
# ══════════════════════════════════════════════════════════════════════════
def build_portfolio(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "포트폴리오")

    # 표지
    p = bp.para(doc, before=110, after=0, line=1.1)
    bp.run(p, "PlaceOS", size=44, bold=True, color=bp.NAVY, spacing=-22)
    p = bp.para(doc, before=2, after=0, line=1.3)
    bp.run(p, "오프라인 상권의 디지털 트윈 플랫폼", size=13, color=bp.INK)
    p = bp.para(doc, before=1, after=0, line=1.3)
    bp.run(p, "Co.I  —  창업 코파일럿 AI", size=13, color=bp.INK)
    p = bp.para(doc, before=14, after=0, line=1.3)
    bp.para_border(p, ("top",), color=bp.NAVY, sz=10, space=10)
    bp.run(p, "포트폴리오", size=10.5, bold=True, color=bp.ACCENT)
    p = bp.para(doc, before=1, after=0, line=1.45)
    bp.run(p, "성명 " + BLANK, size=9.5, color=bp.MUTED)
    p = bp.para(doc, before=0, after=0, line=1.45)
    bp.run(p, "seoghyeonbag36@gmail.com  ·  https://placeos.web.app", size=9.5, color=bp.MUTED)
    p = bp.para(doc, before=0, after=0, line=1.45)
    bp.run(p, "2026. 10.", size=9.5, color=bp.MUTED)

    p = bp.para(doc, before=0, after=0)
    from docx.enum.text import WD_BREAK
    bp.run(p, "").add_break(WD_BREAK.PAGE)

    # 01
    bp.h1(doc, "01", "한 장 요약")
    bp.body(doc,
            "물리적 상권을 SNS · 디지털 관점의 플랫폼으로 읽는 가설에서 출발했습니다. "
            "기존 상권 정보가 행정동 단위 통계에 머물러 '어느 건물 몇 층이 비었는가'를 답하지 "
            "못한다는 점이 문제였습니다. PlaceOS 는 건축물대장을 실측 원천으로 삼아 건물 - 층 - 유닛 "
            "단위 공실 인벤토리를 세우고, 그 위에 Platform · Page · Posting · Program 네 가지 "
            "질문을 차례로 답하는 구조입니다. 마지막 Program 의 대상은 예비창업자, 그리고 자기 "
            "아이템이 통하는 상권을 찾아 팝업스토어 · 가오픈 · MVP 로 검증하려는 기창업자입니다.")
    bp.make_table(doc, [
        ["트랙", "답하는 질문", "구현", "진행률"],
        ["Platform", "이 입지 · 상권은 어떤 플랫폼인가",
         "공실 예측(LSTM) · 업종 추천(GNN)", f"{M['platform']}%"],
        ["Page", "이 platform 안에 어떤 page 가 만들어져야 하는가 (어디가 비었는가)",
         "공실 히트맵 · 층별 매물 · 거리뷰", f"{M['page']}%"],
        ["Posting", "어떤 가격대의 page 가 posting 되어야 하는가",
         "3-Tier 비용-효용 · 입점 ROI · 외부 코파일럿 연동 계약", f"{M['posting']}%"],
        ["Program", "이 아이템이 이 platform 에서 통하는지, 어떤 검증 program 으로 확인할 것인가",
         "검증 program 자동 생성(모객 · 자리 · 연계 + 검증 지표) · 사실성 검증 가드",
         f"{M['program']}%"],
    ], [2.4, 5.4, 5.8, 2.2], sizes=[9.0, 9.0, 9.0, 9.0],
        aligns=[L, L, L, C], bold_first_col=True)
    bp.caption(doc,
               "진행률은 문서가 아니라 산출물을 세어 계산한다 (scripts/pppp_status.py). "
               f"다만 진행률 게이트 {M['gates']}개 중 {M['gates_declared']}개는 사람이 판정하는 "
               "선언형이고, Platform 이 100%가 아닌 것은 남은 두 게이트가 공실 예측의 확정 판정 "
               "(확인대기)이기 때문입니다.")

    # 02
    bp.h1(doc, "02", "실측 산출물")
    bp.body(doc,
            "아래 수치는 모두 저장소의 계측 스크립트가 산출물을 직접 세어 낸 값입니다. "
            "선언이나 문서 서술이 아닙니다.")
    bp.make_table(doc, [
        ["항목", "값", "비고"],
        ["대상 거점", f"서울 {M['hubs']}개 상권", "전부 건축물대장 실측 (Tier1)"],
        ["공실 유닛", f"{M['units']}유닛", "건물 단위 인벤토리"],
        ["층 단위 공실", f"{M['floor_units']}개",
         f"확정 {M['floor_conf']} / 추정 {M['floor_prob']}"],
        ["히트맵 레이어", "4종", "공실 · 임대료 · 유동 · 밀도 (동일 100m 격자)"],
        ["시간 축", "24시간",
         f"집계구 단위 생활인구 · {M['hubs']}/{M['hubs']}거점 · 표본 7일(평일 5 / 주말 2) — 격자 실측은 아님"],
        ["GNN 그래프", f"노드 {M['gnn_nodes']} · 피처 {M['gnn_feat']}", "업종 간 시너지 · 잠식"],
        ["ROI 표본", f"{M['roi_units']}유닛 ({M['hubs']}거점)",
         f"회수불가 {M['roi_fail_n']}유닛({M['roi_fail']}%) · 실측 매출 모델 {M['roi_real']}유닛"],
        ["코드 규모", f"{M['loc']} 라인", "Python · TypeScript"],
        ["테스트", f"백엔드 {M['tests_be']}개 · 프론트 {M['tests_fe_files']}개 파일", "GitHub Actions 통과 시에만 배포"],
    ], [3.2, 4.4, 8.2], sizes=[9.0, 9.0, 8.5], aligns=[L, L, L], bold_first_col=True)

    # 03
    bp.h1(doc, "03", "기술 아키텍처")
    bp.make_table(doc, [
        ["계층", "구성"],
        ["수집", "건축HUB 건축물대장 · 서울시 상권분석 · R-ONE 부동산통계 · KOSIS · 공정위 정보공개서\n"
                 "Selenium / Playwright 수집기 · 수동 실행 스크립트 · 일일 쿼터 관리 런북"],
        ["저장", "Bronze (원본) → Silver (정제 · 주소 정규화) → Gold (분석용 집계)\n"
                 "분석 산출물은 Gold JSON · Parquet 을 직접 읽고, DB(PostgreSQL · Alembic)는 "
                 "계정 · 조직 · 사용량 층만 담당"],
        ["모델", "LSTM 공실 예측 · GNN(PyTorch Geometric) 업종 추천 · MLflow 실험 추적 · "
                 "생성 엔진은 Anthropic SDK 직접 호출"],
        ["서빙", "FastAPI (/api/v1/ 규약) · 지연 계측 미들웨어 · 클라이언트 타이밍 수집"],
        ["화면", "React + TypeScript + Vite · 네이버 지도(지도 · 거리뷰) · CSS 변수 토큰 단일 체계"],
        ["배포", "GitHub Actions (테스트 → 빌드 → 배포 → 검증) → Cloud Run + Firebase Hosting"],
    ], [2.4, 13.4], sizes=[9.0, 8.5], aligns=[L, L], bold_first_col=True)

    # 04
    bp.h1(doc, "04", "검증 방법론")
    bp.body(doc,
            "이 프로젝트에서 가장 설명하고 싶은 부분입니다. 2026년 9월, 자사 지표가 "
            "모델 성능을 전혀 보증하지 못한다는 사실을 스스로 확인하고 지표 체계를 전면 "
            "재정의했습니다. 그 전까지의 기준은 'AI 정확도 70% 이상' 한 줄이었습니다. "
            "당시 공실 예측 방향은 '항상 하락'이라고만 답하는 상수가 "
            f"{M['leak_dir_const']}% 로 모델({M['leak_dir_model']}%)보다 높았습니다. "
            "그 뒤 재학습과 판정 정정을 거친 현재 상태는 아래와 같습니다 "
            "(2026-10-04 · scripts/kpi_baseline.py).")
    bp.make_table(doc, [
        ["축", "대조군 (무정보 규칙 중 강한 쪽)", "모델", "차이 [95% 구간]", "판정"],
        ["공실 예측 · 오차 (MAE)", f"거점 평균 {M['lstm_base']} (지속성 {M['lstm_persist']})",
         M['lstm_mae'], f"{M['lstm_skill']}% [{M['lstm_skill_ci']}]", "!참고 실력 · 확인대기"],
        ["공실 예측 · 방향", f"'평균 쪽' {M['lstm_dir_base']}% (상수 {M['lstm_dir_const']}%)",
         f"{M['lstm_dir']}%", f"{M['lstm_dir_skill']}%p [{M['lstm_dir_ci']}]", "!참고 실력 · 확인대기"],
        ["업종 추천 · Top-3", f"거점 사전분포 {M['gnn_prior']}%", f"{M['gnn_top3']}%",
         f"{M['gnn_skill']}%p [{M['gnn_ci']}]", "실력 (확정)"],
    ], [3.8, 4.4, 1.8, 3.4, 2.4], sizes=[8.5, 8.5, 8.5, 8.5, 8.5],
        aligns=[L, L, C, C, C], bold_first_col=True)
    bp.caption(doc,
               f"공실 예측은 홀드아웃 {M['lstm_n']}건(거점 80곳), 업종 추천은 test {M['gnn_test']}자리 기준입니다. "
               "공실 예측 두 축은 확정이 아니라 참고 판정입니다. 이미 본 분기 데이터로는 확정하지 않는다는 "
               "규칙을 사전에 정했고, 2026년 3분기 데이터가 공표되면 자동 감시 작업이 재학습까지 "
               "돌린 뒤 사람이 판정합니다. 그때까지 이 두 값을 달성이라고 적지 않습니다.")

    bp.h2(doc, "4.1", "적용한 네 규칙")
    bp.bullets(doc, [
        ("임계값 단독 금지 · ",
         "같은 표본의 무정보 베이스라인과의 차이로 판정한다. 임계값은 발명하지 않고 "
         "베이스라인에서 유도한다."),
        ("불확실성 동반 · ",
         "표본 수와 신뢰구간 없이 달성이라 적지 않는다. 구간이 목표를 품으면 구분 불가이지 "
         "달성이 아니다."),
        ("선택과 보고의 분리 · ", "고르는 데 쓴 표본으로 성능을 보고하지 않는다."),
        ("계측기 없는 목표는 지표가 아니다 · ",
         "계측 배선이 0번 조건이다. 배선이 섰다는 것과 목표를 넘겼다는 것은 다르다."),
    ])

    # 05
    bp.h1(doc, "05", "Co.I — 창업 코파일럿 AI")
    bp.make_table(doc, [
        ["항목", "내용"],
        ["한 줄 정의", FILL],
        ["해결하는 문제", FILL],
        ["기술 구성", FILL],
        ["정량 지표", FILL],
        ["PlaceOS 와의 연결", "PlaceOS Posting 트랙이 외부 코파일럿 연동 계약을 이미 발행해 두었으므로,\n"
                              "Co.I 를 그 자리에 연결하는 구조로 설명한다."],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)
    guide(doc, [
        ("이 장을 반드시 채울 것", True),
        ("Co.I 는 면접에서 가장 많이 질문받을 항목입니다. "
         "위 다섯 칸을 비운 채 제출하면 '만들다 만 두 번째 프로젝트'로 읽힙니다.", False),
        ("정량 지표가 아직 없다면, 제출 전에 응답 시간과 처리 질의 수만이라도 측정해 두십시오. "
         "측정하지 않은 값을 적는 것보다는 '현재 측정 중'이 낫습니다.", False),
    ])

    # 06
    bp.h1(doc, "06", "링크 및 연락처")
    bp.make_table(doc, [
        ["구분", "주소"],
        ["PlaceOS 운영", "https://placeos.web.app"],
        ["Co.I", FILL],
        ["저장소", FILL],
        ["이메일", "seoghyeonbag36@gmail.com"],
        ["연락처", BLANK],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
#  4) 인재풀 등록 프로필 (공고가 없을 때 — 1~2쪽)
# ══════════════════════════════════════════════════════════════════════════
def build_talent_profile(out: Path) -> Path:
    """공고 없이 보내는 인재풀 등록용. 심사 통과가 아니라 기억에 남는 것이 목적이라
    이력서보다 짧고, 대신 '무엇을 줄 수 있는가'와 '보관 동의'를 명시한다."""
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "인재풀 등록 프로필")

    doc_title(doc, "인재풀 등록 프로필",
              "Talent Pool Profile · 창업보육 분야 · 공고 없이 제출하는 사전 등록용 요약본")

    # 1. 신원 · 희망 조건
    bp.h2(doc, "01", "기본 정보 및 희망 조건")
    bp.make_table(doc, [
        ["성명", BLANK, "희망 직무", "창업보육 (보육매니저 · 창업지원)"],
        ["연락처", BLANK, "고용 형태", "정규직 · 계약직 모두 가능"],
        ["이메일", "seoghyeonbag36@gmail.com", "근무 가능 시점", FILL],
        ["포트폴리오", "https://placeos.web.app", "근무 희망 지역", "서울 전역"],
    ], [2.2, 5.4, 2.8, 5.4], head=False, sizes=[8.5, 9.0, 8.5, 9.0],
        aligns=[L, L, L, L], zebra=False, bold_first_col=True)

    # 2. 한 줄 요약
    bp.h2(doc, "02", "한 줄 요약")
    bp.body(doc,
            "창업 도메인에서 SaaS 두 종(PlaceOS · Co.I)을 기획부터 배포까지 단독으로 만들어 "
            "운영 중입니다. 창업 당사자이면서 동시에 수집 파이프라인부터 모델, API, 배포까지 "
            "전 구간을 다루는 개발자입니다. 창업보육 업무에서 제 차별점은 두 가지입니다. "
            "입주기업의 사업계획서에 적힌 기술이 실제로 구현 가능한지를 코드 수준에서 판단할 수 "
            "있고, 보육 성과를 정직한 지표로 설계해 관리할 수 있습니다.",
            before=2)

    # 3. 기여 가능 직무
    bp.h2(doc, "03", "창업보육 업무에 기여할 수 있는 것")
    bp.make_table(doc, [
        ["업무", "무엇을 할 수 있는가"],
        ["입주기업\n선발 · 평가",
         "사업계획서의 기술 항목을 코드 수준에서 검증합니다. 구현 가능한 주장인지, "
         "이미 공개된 기술인지 고유한 것인지를 구분할 수 있습니다. 공공 API와 특허 정보를 "
         "직접 수집 · 정규화해 심사 근거 자료를 만들 수 있습니다."],
        ["보육 성과\n관리",
         "성과지표를 정직하게 설계하고 계측합니다. 제 프로젝트에서 목표 지표가 정작 성능을 "
         "보증하지 못한다는 것을 스스로 확인하고 지표 체계를 무정보 기준선 대비 개선폭으로 "
         "재정의했으며, 재지 않은 값을 달성으로 적지 않는 원칙을 코드로 강제했습니다. "
         "센터가 매년 받는 성과평가에서 쓰일 수 있는 경험입니다."],
        ["프로그램 운영\n· 멘토링",
         "창업 당사자로서 보육을 받는 쪽의 입장을 압니다. 입주기업에게 무엇이 실제로 도움이 "
         "되고 무엇이 형식에 그치는지를 구분할 수 있습니다. 예비창업자가 자기 아이템을 팝업스토어 · "
         "가오픈 · MVP 로 검증하는 program 을 설계해 본 경험이 있고, 무엇을 세면 통했다고 할지(검증 "
         "지표 · 기각 조건)를 시작 전에 정하는 방식을 씁니다. 데모데이 · IR 자료의 시장 분석 "
         "파트를 데이터로 뒷받침하는 일도 가능합니다."],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    # 4. 대표 실적
    bp.h2(doc, "04", "대표 실적 (모두 계측 산출물 기준)")
    bp.make_table(doc, [
        ["프로젝트", "핵심 성과"],
        ["PlaceOS\n(운영 중)",
         f"서울 {M['hubs']}개 상권을 건축물대장으로 실측해 건물 단위 공실 인벤토리 구축 "
         f"({M['units']}유닛 · 층 단위 {M['floor_units']}개)\n"
         f"업종 추천 Top-3 {M['gnn_top3']}% — 거점 사전분포 대비 {M['gnn_skill']}%p "
         f"[{M['gnn_ci']}] (확정)\n"
         f"공실 예측 MAE {M['lstm_mae']} — 거점 평균 대비 {M['lstm_skill']}% "
         f"[{M['lstm_skill_ci']}] (참고 · 확정은 2026년 3분기 데이터 이후)\n"
         f"코드 {M['loc']} 라인 · 백엔드 테스트 {M['tests_be']}개 · GitHub Actions - Cloud Run 자동 배포"],
        ["Co.I", FILL],
    ], [3.0, 12.8], sizes=[9.0, 8.5], aligns=[C, L], bold_first_col=True)
    bp.caption(doc,
               "아직 확정하지 못한 항목도 함께 밝힙니다. 공실 예측 두 축은 참고 판정이며 확인대기입니다. "
               "재지 않은 값, 확정되지 않은 값을 달성으로 적지 않는 것이 이 프로젝트의 기본 규칙입니다.")

    # 5. 기술
    bp.h2(doc, "05", "보유 기술")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["Backend · Data",
         "Python, FastAPI, PostgreSQL (계정층), SQLAlchemy / Alembic, Selenium / Playwright, "
         "Bronze · Silver · Gold 3계층"],
        ["ML · LLM", "PyTorch, PyTorch Geometric (GNN), LSTM, MLflow, Anthropic SDK"],
        ["Frontend · Infra",
         "React, TypeScript, Vite, 네이버 지도 API / Docker, GitHub Actions, Cloud Run"],
        ["공공데이터",
         "건축HUB 건축물대장, 서울시 상권분석, R-ONE 부동산통계, KOSIS, 공정위 정보공개서"],
    ], [3.2, 12.6], sizes=[9.0, 8.5], aligns=[L, L], bold_first_col=True)

    # 6. 학력 · 경력
    bp.h2(doc, "06", "학력 · 경력 요약")
    bp.make_table(doc, [
        ["구분", "기간", "내용"],
        ["학력", BLANK, BLANK],
        ["경력", BLANK, BLANK],
        ["자격", BLANK, BLANK],
    ], [2.2, 4.0, 9.6], sizes=[9.0, 8.5, 9.0], aligns=[C, C, L], bold_first_col=True)
    bp.caption(doc, "상세 경력기술서와 포트폴리오는 요청 시 즉시 제출 가능합니다.")

    # 7. 중장기 계획
    bp.h2(doc, "07", "중장기 계획")
    bp.make_table(doc, [
        ["단계", "기간", "내용"],
        ["1단계\n적응 · 자격",
         "입사 ~ 1년",
         "입주기업 관리와 사업비 집행 · 정산 절차를 익히는 데 집중합니다. 그 과정에서 "
         "한국창업보육협회의 창업보육전문매니저 자격을 취득하고자 합니다."],
        ["2단계\n석사",
         "2 ~ 3년차",
         "업무와 직결되는 분야(창업학 · 기술경영 · 데이터사이언스)의 야간 또는 주말 "
         "석사 과정을 병행하고자 합니다. 근무에 지장이 없는 과정으로 한정하며, "
         "기관 규정과 사전 협의를 전제로 합니다."],
        ["3단계\n전문성",
         "4년차 ~",
         "축적한 실무와 연구를 바탕으로 기술 기반 창업기업을 제대로 볼 수 있는 보육 "
         "전문가가 되는 것이 목표입니다. 기술의 실현 가능성과 보육 성과를 함께 판단할 수 "
         "있는 인력이 되고자 합니다."],
    ], [2.2, 2.6, 11.0], sizes=[9.0, 8.5, 9.0], aligns=[C, C, L], bold_first_col=True)
    bp.caption(doc,
               "학업 계획은 채용 조건이 아니라 장기 근속 의사의 표현입니다. "
               "기관이 허용하지 않거나 업무에 지장이 있다고 판단하시면 조정하겠습니다.")

    # 8. 보관 동의
    bp.h2(doc, "08", "개인정보 보관 및 활용 동의")
    guide(doc, [
        ("본인은 채용 목적의 인재풀 등록을 위해 아래와 같이 개인정보 보관 및 활용에 동의합니다.", True),
        ("수집 항목: 성명, 연락처, 이메일, 학력, 경력, 자격 사항", False),
        ("이용 목적: 향후 채용 공고 발생 시 지원 안내 및 서류 검토", False),
        ("보관 기간: 등록일로부터 1년. 기간 경과 시 파기하여 주시기 바랍니다.", False),
        ("철회 방법: 위 이메일로 요청 시 즉시 파기 (동의 철회로 불이익 없음)", False),
        ("", False),
        ("등록일 " + BLANK + "          성명 " + BLANK + "  (서명)", False),
    ])
    bp.caption(doc,
               "기관 채용 담당자는 동의 없는 개인정보를 보관할 수 없습니다. "
               "이 문구가 없으면 등록 요청 자체를 거절해야 하는 경우가 있으므로 반드시 넣습니다.")

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
#  0) 메일 문안 (보내는 도구 — 첨부물이 아니다)
# ══════════════════════════════════════════════════════════════════════════
def mail_subject(doc, text):
    p = bp.para(doc, before=8, after=4, line=1.25, indent=0.32, right=0.32)
    bp.run(p, "제목   ", size=8.5, bold=True, color=bp.MUTED)
    bp.run(p, text, size=9.5, bold=True, color=bp.NAVY)
    bp.para_shade(p, bp.HEADFILL)
    bp.keep_with_next(p)


def mail_body(doc, text):
    """메일 본문을 음영 블록으로 싣는다. 줄바꿈을 그대로 보존한다."""
    lines = text.strip("\n").split("\n")
    for i, line in enumerate(lines):
        p = bp.para(doc, before=(6 if i == 0 else 0),
                    after=(8 if i == len(lines) - 1 else 0),
                    line=1.38, indent=0.32, right=0.32)
        bp.run(p, line if line else " ", size=9.5, color=bp.INK)
        bp.para_shade(p, bp.ZEBRA)
        if i == 0:
            bp.para_border(p, ("top",), color=bp.RULE, sz=8, space=7)
        if i == len(lines) - 1:
            bp.para_border(p, ("bottom",), color=bp.RULE, sz=8, space=7)


MAIL_UNIV_BI = f"""
○○대학교 창업보육센터 담당자님께

안녕하십니까.
현재 공고된 채용이 없는 것으로 확인했습니다만, 향후 보육매니저 또는
창업지원 분야 채용 계획이 있으실 때 검토해 주실 수 있을지 문의드립니다.

저는 창업 도메인에서 두 개의 서비스를 직접 만들어 운영 중입니다.

- PlaceOS — 상권 디지털 트윈 플랫폼 (운영 중: https://placeos.web.app)
  서울 {M['hubs']}개 상권의 공실을 건축물대장 실측으로 건물·층 단위까지 산출하고,
  업종 추천과 입점 ROI 시뮬레이션, 예비창업자의 팝업·가오픈·MVP 검증
  program 설계를 결합했습니다.

- Co.I — 창업 코파일럿 AI
  창업 의사결정(입지·업종·가격대·홍보)을 단계별로 보조합니다.

창업보육 업무에 제가 기여할 수 있는 지점은 세 가지라고 생각합니다.

첫째, 입주기업 선발과 평가에서 기술 항목을 직접 검증할 수 있습니다.
수집 파이프라인부터 모델, API, 배포까지 전 구간을 다뤄 봤기 때문에
사업계획서의 기술 서술이 실현 가능한지, 이미 공개된 것인지 고유한 것인지를
코드 수준에서 판단할 수 있습니다.

둘째, 보육 성과를 데이터로 관리할 수 있습니다. 제 프로젝트에서 목표 지표가
정작 성능을 전혀 보증하지 못한다는 것을 스스로 확인하고, 지표 체계 전체를
무정보 기준선 대비 개선폭으로 재정의한 적이 있습니다. 미달 항목은 미달로
남기고 재지 않은 값은 달성으로 적지 않는 원칙을 코드로 강제했습니다.
보육센터가 매년 받는 성과평가에서 이 경험이 쓰일 수 있다고 생각합니다.

셋째, 보육을 받는 쪽의 입장을 압니다. 같은 고민을 하고 있어, 입주기업에게
무엇이 실제로 도움이 되고 무엇이 형식에 그치는지를 구분할 수 있습니다.

중장기 계획도 말씀드립니다. 입사 후 1년은 입주기업 관리와 사업비 집행·정산
절차를 익히는 데 집중하고, 그 과정에서 창업보육전문매니저 자격을 취득하고자
합니다. 이후 업무에 적응한 뒤 창업학 또는 기술경영 분야의 야간·주말 석사
과정을 병행하고자 하며, 근무에 지장이 없는 과정으로 한정하고 기관 규정과
사전 협의를 전제로 합니다. 장기적으로는 기술 기반 창업기업을 제대로 볼 수
있는 보육 전문가가 되는 것이 목표입니다.

1~2쪽 분량의 프로필을 첨부합니다. 개인정보 보관 동의 문구를 함께
넣어 두었으니 그대로 보관하셔도 됩니다.

바쁘신 중에 읽어 주셔서 감사합니다.

[성명]
010-****-****
seoghyeonbag36@gmail.com
"""

MAIL_PUBLIC_BI = f"""
○○ 창업보육센터 담당자님께

안녕하십니까.
현재 공고된 채용이 없는 것으로 확인했습니다만, 향후 보육매니저 또는
창업지원 인력 채용 계획이 있으실 때 검토해 주실 수 있을지 문의드립니다.

저는 창업 도메인에서 두 개의 서비스를 직접 만들어 운영 중입니다.

- PlaceOS — 상권 디지털 트윈 플랫폼 (운영 중: https://placeos.web.app)
  서울 {M['hubs']}개 상권의 공실을 건축물대장 실측으로 건물·층 단위까지 산출하고,
  업종 추천과 입점 ROI 시뮬레이션, 예비창업자의 팝업·가오픈·MVP 검증
  program 설계를 결합했습니다. 오프라인 점포 기반 창업팀의 입지 판단에
  바로 쓰이는 형태입니다.

- Co.I — 창업 코파일럿 AI
  창업 의사결정(입지·업종·가격대·홍보)을 단계별로 보조합니다.

보육 업무에 제가 기여할 수 있는 지점은 세 가지입니다.

첫째, 입주기업 선발·평가에서 기술 항목을 직접 검증할 수 있습니다. 전 구간을
직접 다뤄 봤기 때문에 사업계획서의 기술 서술이 실현 가능한지를 판단할 수
있습니다.

둘째, 보육 성과를 데이터로 관리할 수 있습니다. 제 프로젝트에서 목표 지표가
정작 성능을 보증하지 못한다는 것을 확인하고 지표 체계를 재정의한 경험이
있습니다. 재지 않은 값을 달성으로 적지 않는 원칙을 코드로 강제했습니다.

셋째, 보육을 받는 쪽의 입장을 압니다. 같은 고민을 하고 있어, 입주기업에게
무엇이 실제로 도움이 되고 무엇이 형식에 그치는지를 구분할 수 있습니다.

중장기 계획은 이렇습니다. 입사 후에는 입주기업 관리와 사업비 집행·정산
절차를 익히는 데 집중하고, 그 과정에서 창업보육전문매니저 자격을 취득하고자
합니다. 장기적으로는 기술 기반 창업기업을 제대로 볼 수 있는 보육 전문가가
되는 것이 목표이며, 업무에 지장이 없는 범위에서 관련 분야 야간 석사 과정도
병행할 계획입니다.

1~2쪽 분량의 프로필을 첨부합니다. 개인정보 보관 동의 문구를 함께
넣어 두었으니 그대로 보관하셔도 됩니다.

바쁘신 중에 읽어 주셔서 감사합니다.

[성명]
010-****-****
seoghyeonbag36@gmail.com
"""

MAIL_FOLLOWUP = """
○○ 담당자님께

지난 ○월에 인재풀 등록을 문의드렸던 [성명]입니다.
답신을 재촉드리려는 것은 아니고, 그 사이 진행된 내용을 한 줄로
공유드립니다.

- [ 새로 추가된 것 한 가지. 예: 창업보육전문매니저 자격시험 응시 /
  새 기능 배포 / 거점 확대 / 정부 지원사업 선정 ]

여전히 귀 기관의 창업보육 업무에 관심이 있습니다.
채용 계획이 생기면 알려 주시면 감사하겠습니다.

[성명]
"""


def build_mail_drafts(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "인재풀 등록 메일 문안")

    doc_title(doc, "인재풀 등록 메일 문안",
              "창업보육 분야 · 채용 공고가 없는 기관에 보내는 사전 등록 메일 · 초안")

    bp.body(doc,
            "공고 지원과 목적이 다릅니다. 심사 통과가 아니라 담당자의 기억에 남는 것이 "
            "목적이므로 첨부는 하나만 보냅니다. 아래 문안은 그대로 복사해 쓰되, "
            "대괄호로 표시한 곳은 반드시 채웁니다.", before=4)

    bp.h1(doc, "1", "대학 창업보육센터 · 산학협력단용")
    mail_subject(doc, "[인재풀 등록 문의] 창업보육 분야 · 기술 검증 가능 — [성명]")
    mail_body(doc, MAIL_UNIV_BI)

    p = bp.para(doc, before=0, after=0)
    from docx.enum.text import WD_BREAK
    bp.run(p, "").add_break(WD_BREAK.PAGE)

    bp.h1(doc, "2", "공공 · 지자체 창업보육센터 · 창업지원기관용")
    mail_subject(doc, "[인재풀 등록 문의] 보육매니저 · 창업지원 분야 — [성명]")
    mail_body(doc, MAIL_PUBLIC_BI)

    p = bp.para(doc, before=0, after=0)
    bp.run(p, "").add_break(WD_BREAK.PAGE)

    bp.h1(doc, "3", "후속 리마인드 (2~3개월 뒤 · 최대 2회)")
    bp.body(doc,
            "답신을 재촉하는 메일이 아니라 진행 사항을 공유하는 메일이어야 합니다. "
            "새로 알릴 내용이 없으면 보내지 않습니다.", before=2)
    mail_subject(doc, "Re: [인재풀 등록 문의] — 진행 상황 공유 드립니다 · [성명]")
    mail_body(doc, MAIL_FOLLOWUP)

    bp.h1(doc, "4", "첨부 구성")
    bp.make_table(doc, [
        ["단계", "시점", "보낼 것"],
        ["1차", "최초 메일", "!인재풀등록프로필 PDF 1개 — 이것만 보낸다"],
        ["2차", "회신 후 요청받으면", "경력기술서 PDF + 포트폴리오 PDF (각각 분리)"],
        ["3차", "실제 공고 지원 시", "공고 지정 양식 + 이력서 + 2차 서류"],
        ["4차", "최종 합격 후", "졸업 · 성적 · 경력증명서, 4대보험 가입내역, 개인정보 동의서"],
    ], [1.8, 3.6, 10.4], sizes=[9.0, 9.0, 9.0], aligns=[C, L, L], bold_first_col=True)
    bp.caption(doc,
               "파일명은 '[성명]_인재풀등록_상권데이터플랫폼개발.pdf' 형식으로 통일한다.")

    bp.h1(doc, "5", "발송 전 점검")
    bp.bullets(doc, [
        ("대괄호 교체 · ", "[성명] 3곳(제목 · 서명 · 파일명), ○○대학교 기관명, 부서명."),
        ("첨부 확인 · ",
         "PDF 1개만. 경력기술서 · 포트폴리오 · 이력서를 함께 보내지 않는다."),
        ("넣지 말 것 · ",
         "주민등록번호, 상세주소, 졸업증명서, 희망 연봉, 겸직 관련 설명. "
         "겸직은 먼저 꺼내면 자백처럼 읽히므로 면접에서 물으면 답한다."),
        ("수신처 · ",
         "대표메일보다 담당자 지정이 회신율이 높다. 산학협력단 홈페이지 조직도에 "
         "업무별 담당자가 공개된 곳이 있다."),
        ("시점 · ",
         "화~목 오전 9~11시. 1~2월과 8~9월이 특히 좋다(창업지원사업 주관기관 선정 "
         "발표 직후라 인력 수요가 실제로 생긴다). 한 번에 5~7곳씩 나눠 보낸다."),
    ])

    guide(doc, [
        ("이 문단은 지우지 말 것", True),
        ("본문 중장기 계획 문단의 두 문장이 위험 차단 장치입니다.", False),
        ("1. '근무에 지장이 없는 과정으로 한정하며, 기관 규정과 사전 협의를 전제로 합니다' "
         "— 야간 수업 때문에 정시 퇴근을 요구할 것이라는 근태 우려를 막습니다.", False),
        ("2. '지금 그것을 전제로 지원하는 것은 아닙니다' — 채용 문의가 기술 거래 제안으로 "
         "읽히는 것을 막습니다.", False),
        ("기술사업화 문장을 빼고 싶으면 '장기적으로는 제가 축적한 기술이 대학의 기술사업화 "
         "성과로 이어지는 길을 찾고,' 이 구절만 지웁니다. 나머지는 그대로 성립합니다.", False),
    ])

    doc.save(out)
    return out


BUILDERS = [
    ("PlaceOS_지원서류_0_메일문안.docx", build_mail_drafts),
    ("PlaceOS_지원서류_1_이력서.docx", build_resume),
    ("PlaceOS_지원서류_2_경력기술서.docx", build_experience),
    ("PlaceOS_지원서류_3_포트폴리오.docx", build_portfolio),
    ("PlaceOS_지원서류_4_인재풀등록프로필.docx", build_talent_profile),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", default=".", help="출력 디렉터리")
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리")
    args = ap.parse_args()

    outdir = Path(args.dir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        fonts = bp.fetch_fonts(cache)
        for i, (name, fn) in enumerate(BUILDERS, 1):
            out = outdir / name
            print(f"{i}) {name}")
            fn(out)
            print(f"   생성 {out.stat().st_size:,}B")
            sub = work / f"embed{i}"
            sub.mkdir(exist_ok=True)
            bp.embed_fonts(out, fonts, sub)
            bp.verify_embedding(out)
            print(f"   완료 {out.stat().st_size:,}B")
    print(f"\n출력 디렉터리: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
