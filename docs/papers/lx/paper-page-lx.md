# LX 투고본 · 공공행정자료 결합 기반 상업용 공실 정보의 데이터 품질과 계산 재현성

> **투고처**: 「지적과 국토정보」 하반기호 (한국국토정보공사 공간정보연구원 · KCI 등재) · 마감 2026-10-11
> **상위 원고**: [../paper-page.md](../paper-page.md) — 수치·결과는 거기서만 가져오고, 거기에 없는 값은 쓰지 않는다
> **규칙**: [../AGENTS.md](../AGENTS.md) · **수치 출처**: [../evidence-index.md](../evidence-index.md) "P2 · Page"
> **국내 문헌 후보**: [../page-study/literature-domestic-lx-20260929.md](../page-study/literature-domestic-lx-20260929.md)
>
> **분량 판단 (2026-09-29)**: 상위 원고 본문은 공백 제외 약 1만 2천 자다. 투고 기준 "A4 15매 내외"를
> 넘지 않으므로 **축약이 아니라 재구성**이다 — 관련 연구를 독립 절로 세우고 국내 문헌을 더하고,
> 결론을 공간정보 행정 독자에게 맞춘다. 줄여야 할 것은 없다. **한계 절은 줄이지 않는다.**
>
> **상태**: 골격 + §2(선행연구) 초안. 나머지 절은 상위 원고의 어느 절을 옮길지만 적어 두었다.
> 이 파일은 `docs/papers/paper-*.md` 가 아니라 `verify_paper_submission.py` 의 검사 대상이 아니다 —
> 그래서 `TODO` 를 남길 수 있다. 투고 전에 TODO 가 0 이어야 한다.

## 제출 서류 체크 (검색 결과 기준 — 투고 안내 원문 미확인)

- [ ] 투고 원고 (A4 15매 내외)
- [ ] 학술지 논문 투고 신청서
- [ ] 저작권 이양 동의서
- [ ] 개인정보 수집·이용·제3자 제공 동의서
- [ ] 표절 검사 결과 확인서
- [ ] 연구윤리 서약 (submission-plan §D 에 적힌 항목 — 위 목록과 대조 필요)

<!-- TODO(투고규정): lxsiri.re.kr 「학술지 논문투고」 원문으로 서식(글자 크기·줄간격)·초록 분량·주제어 수·
     참고문헌 양식·본문 인용 방식을 확인한다. 이 세션에서는 그 페이지가 egress 차단이었다. -->

---

## 국문 초록

<!-- 옮길 곳: ../paper-page.md 「초록」 — 그대로 쓰되 투고 규정의 분량에 맞춘다. 수치는 PAGE-D 근거 그대로. -->

**주제어:** 공공행정자료, 공실 정보, 데이터 품질, 계산 재현성, 순서 민감도

## Abstract

<!-- 2026-09-29 초안: ../paper-page.md 「초록」 8문장을 문장 단위로 옮겼다. 새 주장·새 수치 없음.
     수치 근거: 66 hubs · 52,642 → PAGE-D01 / 66/66 반복 → PAGE-D04 / 셀 재합산·보존 서빙 → PAGE-D08 /
     Gold→서빙 → PAGE-D09 / 198 · 65 hubs → PAGE-D05. 국문 초록을 고치면 이 번역도 같이 고친다.
     분량(단어 수) 제한은 투고규정 원문 확인 후 맞춘다 — 현재 211 단어. -->

Commercial vacancy information built by linking public administrative data provides detailed spatial outputs, yet computational consistency and real-world vacancy accuracy require different forms of validation. This study evaluates frozen processed data from PlaceOS for structural consistency, computational reproducibility under fixed inputs, and sensitivity to the row order of building polygons. The scope of inspection covers 52,642 master polygons across 66 analysis hubs, and the denominators to which each rule applies are distinguished from items that could not be evaluated. In earlier repeated runs, comparisons of the master, coverage, and serving outputs matched in 66 of 66 hubs, and agreement was also confirmed in an independent cell re-aggregation and in a comparison from the processed (Gold) layer to the served responses. However, in 198 earlier order-permutation trials, although hub-level aggregates did not change, grid-cell membership or cell numerators and denominators were affected in 65 hubs. This shows that reproducing results from fixed inputs must be distinguished from the order invariance of spatial outputs. Because independent ground truth and temporal alignment of the source observations were not available, real-world vacancy accuracy and the effect of error correction were not evaluated. The study proposes a validation and reporting procedure that does not extend successful computational reproduction to claims of spatial stability or real-world accuracy.

**Keywords:** public administrative data, vacancy information, data quality, computational reproducibility, order sensitivity

---

## 1. 서론

<!-- 옮길 곳: ../paper-page.md §1.1(문제의식) · §1.2(RQ·가설) · §1.3(기여와 범위).
     LX 독자에 맞춘 한 단락을 §1.1 앞에 더한다: 지적·건물 행정자료가 필지·건물 단위로 정비돼 있어도
     "어느 건물 몇 층이 비었는가"는 행정 통계가 직접 답하지 않는 질문이라는 점.
     수치를 새로 넣지 않는다. -->

## 2. 선행연구

본 연구와 맞닿는 선행연구는 세 갈래로 정리된다. 첫째는 필지·건물 단위 행정자료를 공간정보로 결합하는 연구이고, 둘째는 공공 건물 자료와 가공 데이터의 품질을 평가하는 연구이며, 셋째는 상업용 부동산의 공실을 추정하거나 설명하는 연구이다. 본 연구는 둘째 갈래에 속하지만, 품질의 대상을 원천 자료의 정확성이 아니라 결합 이후 **가공 산출물의 계산적 성질**로 둔다는 점에서 기존 논의와 구분된다. 이 절은 체계적 문헌고찰이 아니며, 각 문헌은 확인한 범위를 참고문헌에 함께 적는다.

### 2.1 필지·건물 행정자료의 결합

<!-- TODO(문헌): 국내 — 필지(PNU)와 건물 정보의 연계 구조와 그 어려움.
     후보 K3(김창환·이원희, 2014) · K5(김승범, 2015) · K4(이종원 외, 2021).
     K4 는 주소 기반 결합이므로 "본 연구는 결합 키를 PNU 로 둔다"는 대비에만 쓴다.
     원문(최소 초록) 확인 전에는 내용을 쓰지 않는다 — 장부 상태가 '초록확인' 이상일 때만. -->

본 연구의 입력은 건물 폴리곤, 건축물대장, 점포 및 인허가 자료를 필지 고유번호(PNU)로 결합한 것이다. 이때 표시 객체인 폴리곤, 집계 객체인 지번, 출력 객체인 격자는 서로 다른 관측 단위이며, 같은 지번에 속한 폴리곤 사이의 값 차이를 곧바로 결합 오류로 볼 수 없다. 결합 단위의 이러한 구분은 이후 절의 검사 단위를 정하는 근거가 된다. [자료의 관측 단위와 파생 경로](../data-specification.md)

### 2.2 공공 건물 자료와 가공 데이터의 품질

<!-- TODO(문헌): 국내 — 건물 데이터 품질 요소와 대장 등록정보의 오류.
     후보 K1(김병선 외, 2022, 본 학술지) — 기하·위치·시맨틱 품질 요소와 본 연구의 검사 축(계산 재현·순서 민감도)을 대비.
     후보 K2(이성화, 2010) — 층별현황·전유부의 등록 오류가 본 연구의 층 정보 미확정 범위와 전유부 제외의 배경.
     요약에 나온 오류 유형 수 등 수치는 원문 대조 전 금지. -->

국외 연구에서 Marsden과 Pingry(2018)는 정보시스템 연구에서 데이터 수집·검증·품질의 설명이 모델 선택에 비해 충분히 다루어지지 않는 문제를 지적하며, 자료의 유형이나 규모만으로 품질을 보증할 수 없다고 본다. 본 연구는 이를 입력의 관측 단위·선택 경로·관측시점과 검증 범위를 명시할 배경으로만 사용하며, 전문을 확보하지 못했으므로 해당 논문의 품질 임계값이나 검증 체계를 구현했다고 주장하지 않는다. Alsudais(2021)는 널리 쓰이는 공개 자료(Inside Airbnb)에서도 객체의 의미와 연결 관계, 사용 릴리스의 특정이 재현에 영향을 주는 문제를 다룬다. 본 연구는 이를 지번·폴리곤·층의 구분과 입력 묶음의 특정에 참고하되, 그 논문의 오류 유형이나 비율을 공실 자료의 품질 기준으로 옮기지 않는다. Timmerman과 Bronselaer(2019)는 규칙 기반 품질 측정에서 판정의 불확실성을 다루는 틀을 제안하였다. 본 연구의 `pass/fail/not_evaluable` 구분과 층 배정 상·하한은 이 문제의식과 관련되지만, 해당 논문의 모형을 적용한 결과는 아니다.

재현성의 용어는 National Academies of Sciences, Engineering, and Medicine(2019)을 따른다. 같은 입력 자료·계산 단계·분석 조건에서 일관된 결과를 얻는 계산 재현성(reproducibility)과 새 자료로 같은 질문을 다시 확인하는 반복 검증(replicability)을 구분하며, 이에 따라 본 연구의 Gold→서빙 대조는 계산 재현 범위에 속한다. 동일 내용의 행 순서 변형은 어느 쪽에도 속하지 않는 별도의 출력 민감도 검사로 둔다. Sandve 외(2013)가 권고한 결과 생성 경로·버전·중간 결과의 보존은 본 연구의 인벤토리·파일 해시·실행 기록과 연결되지만, 해시의 존재가 원본의 접근 가능성이나 정확성을 보장하지는 않는다.

### 2.3 상업용 공실의 추정과 설명

<!-- TODO(문헌): 국내 — 상가 공실 연구가 조사통계·건물 표본을 이용한 요인 분석이라는 점.
     후보 K6(주택금융연구) · K7(국토계획) 중 원문이 열리는 쪽 하나. 둘 다 안 열리면 이 단락은
     R-ONE 조사통계의 성격(아래 문장)으로만 간다. 요약의 계수 부호·유의성은 옮기지 않는다. -->

본 연구가 외부 대조 맥락으로 쓰는 R-ONE 자료는 한국부동산원의 지역·분기 단위 조사통계로, 본 연구의 건물·지번 단위 파생값과 관측 단위가 다르다. 따라서 두 값의 차이를 곧바로 오차로 읽을 수 없으며, 앵커는 개별 건물이나 호실의 공실 정답을 대신하지 않는다. [R-ONE 앵커의 위치와 해석 범위 — 상위 원고 §2.2](../paper-page.md) 본 연구는 공실의 원인이나 수준을 설명하는 대신, 행정자료 결합으로 만든 공실 대리값이 어떤 계산적 조건에서 재현되고 어디서 흔들리는지를 묻는다.

### 2.4 본 연구의 위치

선행연구는 결합의 구조(2.1), 원천과 가공 자료의 품질(2.2), 공실의 수준과 요인(2.3)을 각각 다루어 왔다. 본 연구는 이 셋이 만나는 자리에서, 공공행정자료를 결합한 공실 산출물에 대해 **동일 입력의 계산 재현**과 **입력 순서에 대한 공간 출력의 불변성**을 분리하여 보고하는 사례 연구이다. 순서 민감도 검사를 위 문헌의 제안으로 돌리거나 새로운 일반 이론으로 주장하지 않으며, 현실 공실 정확도는 독립 정답이 없어 평가 범위 밖에 둔다.

## 3. 자료와 방법

<!-- 옮길 곳: ../paper-page.md §2.1–2.4 전부. 표는 그대로. 수치는 PAGE-D 근거 그대로.
     "조건 D"(동결 66거점)가 현재 서빙 거점 수와 다르다는 점을 §3.1 첫 문단에 한 줄로 밝힌다 —
     동결 자료의 거점 수이지 현재 서비스 규모가 아니다. -->

## 4. 결과

<!-- 옮길 곳: ../paper-page.md §3.1–3.6 전부. 가설 판정표(§3.6) 포함. -->

## 5. 논의

<!-- 옮길 곳: ../paper-page.md §4.1–4.4. -->

## 6. 한계

<!-- 옮길 곳: ../paper-page.md §5 전부 — 줄이지 않는다. 현실 정확도 미평가 · 독립 검토 표본 전부 unresolved. -->

## 7. 결론 및 정책적 함의

<!-- 옮길 곳: ../paper-page.md §6 결론.
     TODO(사람): 정책 함의 한 단락 — 독자는 공간정보 행정(지자체·공사)이다.
     이 결합을 행정이 쓸 때 무엇을 함께 공개·보고해야 하는가(입력 묶음 특정 · 검사 단위 · 미평가 항목)로 닫는다.
     새 수치 금지. 후보 K8(서울시 상가 공실률 추정 연구용역)은 "행정 수요" 근거로만, 서지 확인 후. -->

## 참고문헌

<!-- 국외 5편은 ../paper-page.md 「참고문헌」 그대로(확인 범위 병기 포함).
     국내 문헌은 장부 상태가 '서지대조' 이상인 것만 추가한다. 인용 양식은 투고규정 확인 후 통일. -->

Alsudais, A. (2021). Incorrect data in the widely used Inside Airbnb dataset. *Decision Support Systems, 141*, 113453. https://doi.org/10.1016/j.dss.2020.113453. 검토 판본: 저자 공개본 arXiv:2007.03019v2.

Marsden, J. R., & Pingry, D. E. (2018). Numerical data quality in IS research and the implications for replication. *Decision Support Systems, 115*, A1–A7. https://doi.org/10.1016/j.dss.2018.10.007. 확인 범위: 출판사 공개 초록·서론.

National Academies of Sciences, Engineering, and Medicine. (2019). *Reproducibility and Replicability in Science*. Washington, DC: The National Academies Press. https://doi.org/10.17226/25303. 확인 범위: 제3장 중 용어 정의 및 구분.

Sandve, G. K., Nekrutenko, A., Taylor, J., & Hovig, E. (2013). Ten simple rules for reproducible computational research. *PLOS Computational Biology, 9*(10), e1003285. https://doi.org/10.1371/journal.pcbi.1003285.

Timmerman, Y., & Bronselaer, A. (2019). Measuring data quality in information systems research. *Decision Support Systems, 126*, 113138. https://doi.org/10.1016/j.dss.2019.113138. 확인 범위: UGent 기관 공개 초록·서지.
