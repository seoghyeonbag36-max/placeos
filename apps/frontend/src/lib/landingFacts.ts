/**
 * 랜딩이 말하는 숫자 — 한 곳에만 둔다 (2026-10-08).
 *
 * 거점 수는 이 저장소에서 문서마다 세 번 낡았다(CLAUDE.md 「거점」 행). 랜딩은 방문자가 가장 먼저 읽는
 * 자리라, 낡은 숫자가 거기 남으면 그날부터 거짓 광고가 된다. 그래서 숫자를 컴포넌트 문장 안에 흩뿌리지 않고
 * 여기 두고, `apps/backend/tests/test_landing_facts.py` 가 서빙 거점 수(`data.config.page_hubs.ACTIVE_HUBS` 중
 * 사이트에 보이는 도시 — `lib/siteScope.SITE_CITIES`)와 이 값이 어긋나면 운다. 거점을 늘리거나 줄였을 때 그 테스트가 알려 주는 대로 이 값만 고친다.
 *
 * 단일 기준은 `python scripts/pppp_status.py` 다. 여기에 **적지 않는** 것 — 정확도·예측 성능·고객 수·가격:
 * 공실 예측(LSTM) 두 축은 아직 확인 대기이고(CLAUDE.md KPI①), 파일럿 실적은 없으며, 요금은 정해지지 않았다.
 */
export const LANDING_HUBS = 81;

/** 보이는 지역 — 2026-10-26 고양·파주를 서빙하며 「서울」에서 늘었고, 10-29 「서울·경기」, 10-31 「서울·경기·광주」, 그 뒤 「서울·경기·광주·전주」(158곳)가 됐다.
 *  2026-11-10 사용자 결정으로 사이트는 **서울만** 보인다(`lib/siteScope`) — 서울 밖 데이터는 그대로 있지만 화면에 안 나오니 랜딩도 서울 거점 수만 말한다.
 *  거점 수와 같이 움직인다(`LANDING_HUBS` = 보이는 도시의 서빙 거점 수 — `tests/test_landing_facts.py`) */
export const LANDING_REGION = "서울";
