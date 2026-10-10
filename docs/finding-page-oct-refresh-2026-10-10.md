# 10월 수집분을 Page 에 붙이기 — 변환은 끝났고, Gold 재빌드는 대장 수집 뒤다 (2026-10-10)

물음: 10-09·10-10 에 받은 API·데이터가 Page 공실 정확도를 올리는가, 무엇을 더 붙여야 하나.

- 방법: 저장소 산출물 실측 · 네트워크 0콜(변환·측정 모두)
- 기준선: `reports/page_accuracy_baseline_2026-10-10.json` (`scripts/page_accuracy_snapshot.py`)
- 변환 기록: `data/bronze/api_acquisition/2026-10-09/215933/import_manifest.json` (bronze, 비추적)

---

## 0. 한 줄 결론

**10월 상가정보·인허가는 표준 bronze 로 옮겼다. Gold 는 아직 안 바꿨다** — 새로 점포가 생긴
지번 **2,286곳**이 대장 없이는 측정에 못 들어오는데, 점포가 모두 사라진 측정 지번 **764곳**은
지금 바로 공실로 바뀌므로 지금 재빌드하면 공실이 한쪽으로 부푼다(격차 +9.6%p 를 키우는 방향).
대장 수집(건축HUB, 하루 쿼터 안) → 재빌드 → 기준선 대조가 다음 한 수다(§5).

---

## 1. 받은 것의 실측

| 자료 | 확인한 것 | Page 공실에 닿는가 |
|---|---|---|
| 상가정보 81거점 | 318,948행 · 기준월 `stdrYm=202606` · 요청이 `fetch_stores` 와 같다(엔드포인트·`stores_radius_m`·cx/cy) · suyu 는 최초 2페이지에서 끊겨 recovery 5페이지(4,050행)가 정본 | **닿는다** — 54거점 내용이 바뀌었다(예: garosugil +614/−511 점포). 27거점(08-30~09-24 수집분)은 직전 스냅샷과 **내용이 같다** — 원천이 분기 단위 갱신이다 |
| 서울 인허가 | 폴더 27종 중 **완주 18종**(모든 페이지 행 합 = `list_total_count`) · **9종은 첫 1,000행 프로브**(의원·약국·휴게음식점·담배소매업·즉석판매제조가공업·제과점영업·안전상비의약품판매·이용업·목욕장업). 수집 문서의 "15종"과 다르다. 체육·게임·숙박 계열 `MGTNO` 중복은 구청별 번호 체계(행은 전부 서로 다르다) | 갱신만 — 대상 15종은 기존 수집기 27종 안에 이미 있다(건수 차 1% 미만) |
| NEIS 학원·교습소 | 25,527행 · 전부 '개원' · UTF-8 정상 · 상세주소(`FA_RDNDA`)에 층 표기 **62.4%** | 작게 닿는다(§4) |
| 생활인구 61일 | 날짜 폴더 61개 | 유동 레이어 — 공실 판정 아님 |
| 토지이음 API | 코드 04 지속 | Posting 쪽 |

## 2. 변환 — `data/collectors/import_acquisition.py`

수집기와 같은 규칙으로 바꿔 수집일 폴더(`bronze/<거점>/2026-10-09/`)에 쓴다. 네트워크 0콜.

- `stores_raw.json`: 페이지 `body.items` 연결 · 행 수 = `totalCount` · 점포 ID 중복 0 일 때만.
  결과 **54거점 씀 · 27거점 동일(쓰지 않음)**. 동일 27거점은 정규형 해시가 직전 스냅샷과 일치 —
  형식이 표준과 같다는 증거이기도 하다.
- `licensing_biz.json`: `seoul_licensing` 의 (구,동) 필터·`_KEEP`·`svc` 그대로. 완주 18종은 10월 값,
  미완주 9종은 직전 거점 스냅샷의 행을 이월(54거점 08-23 · 27거점 09-24 기준). 81거점 씀.
  업종별 행 수 변화는 전부 5% 이내(bangbang 50,402 → 50,431행 · garosugil 45,946 → 46,069행).
- 다시 돌리면 81/81 `unchanged` — 멱등.
- 되돌리기: `import_manifest.json` 에 적힌 2026-10-09 파일(경로·sha256)을 지우면 직전 스냅샷이 다시 최신이 된다.

## 3. 왜 Gold 를 아직 안 바꿨나

Page 의 측정 대상(`gold/<거점>/building_vacancy.json` 행)은 **점포가 있던 건물만** 대장을 받아 만든
고정 패널이다. 수집기(`building_vacancy.run_hub`)는 기존 행을 두고 **새 건물만** 대장을 조회해 붙인다.

| 지번 단위(점포 = 비사무실 업종) | 수 |
|---|---:|
| floor_ouln 측정 지번 | 44,067 |
| 그중 10월에 점포가 **모두 사라진** 지번 → 재빌드하면 곧바로 공실 | **764** |
| 10월에 점포가 **새로 생긴** 미측정 지번 → 대장 없이는 못 들어온다 | **2,286** |
| 7월에도 점포가 있었는데 행이 없는 지번(다필지 건물의 부속 지번 포함 추정) | 1,972 |

대장 없이 재빌드하면 빠지는 쪽만 반영돼 공실이 위로 치우친다. 그래서 커밋하지 않았다.

**기존 결손 하나 — anam.** 7월 스냅샷의 점포 건물(bdMgtSn) 839동 중 대장 행은 **197동**뿐이다(23%).
`pppp_status` 의 "대표 집계 커버리지"는 **수집된 행**을 분모로 세서 anam 을 100% 로 보여 준다 — 이 게이트는
미수집 건물을 못 본다. nambu 도 8동 같은 상태다. 위 대장 수집이 이것도 같이 채운다.

10-10 저녁 이 단계를 바로 못 건 이유: 작업 트리(worktree)에 `data/.env`(키)가 없어 프리플라이트가
`[중단]` · 배터리 58% 구동(`[주의]` — 2~7배 느림). **메인 트리에서 AC 연결 후** 돌린다.

## 4. NEIS — 측정은 했고 연결은 안 했다

서빙 거점 건물에 걸리는 학원·교습소 **4,270건**(25,527건 중, 79/81거점). 이름이 상가정보와 맞는 것이
2,441건(57%) — 대부분 이미 점포로 잡혀 있다. 지금 공실로 세는 층을 '점유 확인'으로 바꾸는 것은 **465층**
= 분모 105,127층의 **0.44%**, 미확인 34,180층의 1.36%. 격차 +9.6%p 를 혼자 줄이지 못한다.

연결할 때 지킬 것(설계만, 코드 없음):
1. 매칭은 도로명주소 → PNU: 대장 표제부 `newPlatPlc`(지번 키) + 상가정보 `rdnmAdr`↔`lnoCd`. NEIS 에 좌표가 없다.
2. 층은 `building_attrs` 의 **별도 키**(예: `aca_flr_nos`)로 싣고 **두 곳에 같이** 더한다 —
   `recalc_floor_ouln` 의 `store_nos` 와 `build_page_master._aggregate` 의 `known`. 한쪽만 넣으면
   분모만 늘어 공실이 **오른다**.
3. 층 미상 학원은 `spare`(상한 배정)에 넣지 않는다 — 상가정보 flrNo 공란과 같은 업소를 두 번 센다.
4. **분모 확장은 보류.** 매칭된 층 표기 학원의 27%(821건)가 현재 분모 밖 층이다. 교습소는 주거 동에
   있을 수 있어 `capacity_floors` 규칙(점포 확인 층은 상업층)을 그대로 쓰면 아파트 층이 상가로 들어온다 —
   층별개요 용도로 주거 비중을 먼저 잰다.

## 5. 다음 한 수 — 메인 트리, AC 연결 후

```bash
python scripts/quota_preflight.py                      # [중단] 0 확인
# 상가정보가 바뀐 54거점만 — 바뀌지 않은 거점에 돌리면 대장 원본 전체를 오늘 폴더에 한 벌 더 쓴다
HUBS=$(python -c "import json;m=json.load(open('data/bronze/api_acquisition/2026-10-09/215933/import_manifest.json',encoding='utf-8'));print(' '.join(s for s,v in m['stores'].items() if v['result']=='write'))")
python -m data.collectors.building_vacancy $HUBS       # 새 건물만 대장(재개 로직) — 약 2,300지번 + anam 642동
python -m data.collectors.floor_capacity $HUBS          # 전유부와 동시에 돌리지 말 것(429 는 키 단위)
python -m data.pipelines.build_building_attrs
python -m data.pipelines.recalc_floor_ouln
python -m data.pipelines.build_page_master
python -m data.pipelines.build_vacant_units
python -m data.pipelines.build_vacant_floor_units
python -m data.pipelines.build_building_history
python -m data.pipelines.calibrate_vacancy
python -m data.pipelines.build_district_zones
python scripts/page_accuracy_snapshot.py --compare reports/page_accuracy_baseline_2026-10-10.json
python -m pytest data/tests -q && (cd apps/backend && pytest -q)
```

비교에서 먼저 볼 것: 앵커가 바뀐 거점 0 · 거점 수 81 유지 · `aligned_gap_pp` 중앙 · |격차|>10 거점 수.
⚠ `build_posting_inputs` 등 공실 유닛을 읽는 Posting 산출물은 이 목록 밖이다 — 유닛이 바뀌면 같은 날 다시 만든다.

## 6. 정정

10-10 오후 보고의 "건물의 47.8%는 점유 확인 층이 없다"는 상업층이 없는 건물(주거 등)까지 분모에 넣은 값이다.
상업층이 있는 건물 36,200동 중 확인 층이 없는 건물은 **4,112동(11.4%)** 이다.
