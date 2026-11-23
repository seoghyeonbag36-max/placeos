# 고양·파주 도시 전체 확장 — 사용자 결정 다섯 가지와 진행 (2026-11-23)

> 배경: 「서울시를 만든 것처럼 고양시·파주시를 서울과 연결되게 만들고자 한다」 + 세 질문(확장 vs 별개 · 시군구 단위 품질 · 매출 데이터). 현황은 이미 **고양 5 · 파주 4 서빙 + 서울 연결 흐름**
> (`decision-goyang-paju-corridor-2026-10-26.md`)이었다. 아래는 그 위에 사용자가 11-23 에 정한 것이다.

## 1. 결정

| # | 결정 | 이 PR 에서 한 것 | 남은 것 |
|---|---|---|---|
| ① | **Page 부터 도시 전체로 넓힌다** | 시군구 점포 전수(고양 50,083 · 파주 24,550) · 서빙 거점이 덮는 몫 **12.4% · 24.3%** · 후보 29곳 중 hub-chain §0 「통과」 6곳 **등록**(서빙 아님). **11-23 추가 지시: 천장 관련 상권·건물도 같이 수집** → 「기각」(계획상가 밀집) 6곳도 보류(`deferred`)로 등록해 **12곳 수집을 시작**(`--batch gpcity`) | 6곳의 점포·폴리곤 → 대장(쿼터 · 하루에 안 끝난다) → Gold → 앵커 대조 → 서빙 등재. 「주의」 17곳은 대장 뒤 판정 |
| ② | **임대 앵커·계획상가 천장은 우선 별도 표시** — 3D 트윈 담당 팀원이 다룬다 | 임대 앵커 상권 셋(고양시청 · 탄현역 · 파주시청 소재지)은 이미 주교동·탄현·금촌으로 서 있거나 수집돼 있다. 거점마다 `ceiling_planned_store` · `ceiling_rone_anchor` 를 서빙 여부와 따로 보고서에 적었다. 인계 문서 | 3D 라이브러리·호실 형상은 담당자 몫(구현 전) |
| ③ | **품질 기준은 KPI 규칙** | 사전등록 — 계측기(`served_hub_cover.pct`) · 서빙 게이트 사전 고정 · 공유 앵커라 「정확하다」 주장 금지 | 커버리지 **목표값**은 사용자 결정 대기 |
| ④ | **매출 대리값은 확인하고 없으면 제외 · 요구 판매량을 고양·파주에 먼저** | 대리값 **없음 → 제외**(상업 이용 금지·갱신 중단·경로 미확정). 요구 판매량을 자리 상세(R4)에 고양·파주만 노출 | 조폐공사 15149767 활용신청(사용자) · 서버 쪽 업종 참고값은 안 만들었다 |
| ⑤ | **주민등록 인구·역 승하차는 우선 제외** | 손대지 않았다 | — |

## 2. 하지 않은 것 (경계)

- `ACTIVE_HUBS`·서빙 목록·Gold·프로덕션 DB·배포·푸시. 새 6곳은 `GOYANG_PAJU_CITYWIDE_SERVED_HUBS`(빈 집합)로 막혀 **서빙에 오르지 않는다**.
- 기존 거점의 반경·`partition_with`·Gold. 새 거점의 반경을 이웃과 겹치지 않게 **줄이는 쪽**으로 맞췄다.
- PPPP 네 화면·레일·진입로·랜딩. 요구 판매량은 흐름(5판) 자리 상세에 **더한 것**이고 `#/explore` 네 트랙은 그대로다.
- 매출·수요를 서울 값이나 평균으로 합성하지 않았다(없으면 「자료 없음」).

## 3. 산출물

| 층 | 파일 |
|---|---|
| 도구 | `scripts/recollect_hubs.py`(반경 변경 거점 재수집) · `scripts/citywide_store_census.py` (시군구 점포 전수 → 커버 · 행정동 표 · 후보 · 두 천장) |
| 결과 | `reports/citywide_census_goyang.json` · `reports/citywide_census_paju.json` · [finding-citywide-census-goyang-paju-2026-11-23.md](finding-citywide-census-goyang-paju-2026-11-23.md) |
| 레지스트리 | `data/config/page_hubs.py`(`GOYANG_PAJU_CITYWIDE_HUBS` 6 · `…_SERVED_HUBS` 빈 집합 · `ACTIVE_HUBS` 문지기) · `data/config/rone_districts.py`(6곳 공유 매핑) · `scripts/chain_status.py`(`_BATCH_GATES`) · `scripts/run_hub_chain_batch.py`(`--batch gpcity`) |
| 요구 판매량 | `flow/RequiredSales.tsx` · `flow/screens/Space.tsx` · `flow/spaces.ts`(`rentShared`) |
| 주의 17곳 | `GOYANG_PAJU_CAUTION_HUBS`(등록만 · 서빙 문지기 빈 집합) · `--batch gpcaution` — 12곳이 끝난 뒤 시작해 **27분에 완료**(게이트 15 통과 · 1 탈락 · 1 대표값 미산출 → finding §6). 대장 뒤 채택·기각 판정은 사람 몫 — 단일시설로 읽히면 `deferred="단일시설"` |
| 장항2동 | 사용자 선택 「기존 3곳에 partition_with + 반경 확대」: 라페스타·웨스턴돔 500/700 · 마두역 470/670(백석역과 닿지 않게) + 짝 `ilsan↔westerndom↔madu` · `ilsan↔juyeop` · `madu↔madu-east`(서로 선언). 가드 `test_janghang_partition_group_is_symmetric_and_does_not_touch_served_hubs`. **재수집(`scripts/recollect_hubs.py`)이 진행 중이다 — 11-23 21:36 기준 마두역·주엽역 인허가 스캔을 마치고 라페스타부터 대장을 이어받는 중. 끝나기 전까지 이 5곳의 Gold 는 옛 반경 기준이다** |
| 문서 | [finding-goyang-paju-sales-proxy](finding-goyang-paju-sales-proxy-2026-11-23.md) · [prereg-citywide-page-quality](prereg-citywide-page-quality-2026-11-23.md) · [handoff-3d-twin](handoff-3d-twin-goyang-paju-2026-11-23.md) |
| 가드 | `tests/test_city_registry`(배치 합 · 슬러그 충돌) · `tests/test_active_cities_match_serving`(서빙 문지기) · `RequiredSales.test`(5) · `FlowApp.test`(고양·파주 노출 · 서울 비노출) |

## 4. 수집 실행(11-23 20:22 시작)

- 실행 위치: worktree(`.env`·bronze·silver 없음) → `scripts/run_with_env_root.py --env-root <메인 트리> -- python -u scripts/run_hub_chain_batch.py --batch gpcity` — 키는 복사하지 않고 **환경변수로만** 올리고, 원천 루트(`PLACEOS_BRONZE_ROOT`·`PLACEOS_SILVER_ROOT`)는 메인 트리를 가리킨다. Gold 는 이 트리 `data/gold` 로 나간다.
- **첫 실행이 12곳 전부 「점포」에서 실패로 읽혔다** — `common.save_json` 의 로그 줄(`path.relative_to(DATA_ROOT)`)이 원천 루트가 다른 트리일 때 예외를 냈다(저장은 이미 끝난 뒤). 로그 줄만 고쳤고 가드 `data/tests/test_common_save_json.py`. `run_hub_chain_batch._bronze_root()` 도 같은 환경변수를 읽게 했다.
- 건축HUB 쿼터는 한 번에 한 거점 · 소진되면 `quota_day` 를 남기고 멈춘다 — **다음 날 같은 명령을 다시 돌려야 이어받는다**(무인 재개 작업은 메인 트리 기준이라 이 worktree 에는 걸리지 않는다 → 머지 뒤 `resume_hub_chain.py --install --batch gpcity`).
- ⚠ 디스크 여유가 8.3GB(97%)였다 — 수집이 bronze 를 늘린다. 3GB 아래로 떨어지면 멈출 것.

## 5. 다음 한 수

0. **재수집 확인**: `reports/logs/recollect-janghang.log` 에 「배치 완료」가 찍혔는지 · 5곳 `python scripts/chain_status.py ilsan westerndom madu juyeop madu-east --include-paused` 가 앵커까지 ok 인지. 끝나면 앵커 격차를 보고하고(보류 거점이라 서빙 영향 없음), 안 끝났으면 같은 명령을 다시 돌린다.

1. 12곳 수집(`--batch gpcity`)이 끝나면 같은 방식으로 `--batch gpcaution`(「주의」 17곳). 쿼터가 끝나는 날마다 같은 명령을 다시 돌려야 이어받는다.
2. 앵커 대조 전에 `rone_rent` 를 새 매핑으로 다시 돌린다(폴백 앵커 10.0 함정 — hub-chain 「앵커 폴백」).
3. 서빙 등재는 게이트를 통과한 거점만 `GOYANG_PAJU_CITYWIDE_SERVED_HUBS` 에 넣고, **공통 피처판 GNN 을 다시 학습**한다(거점 원핫 열 수가 바뀐다).
