"""실제 확보 원본의 건수·해시·키 비노출을 검증하고 사용자용 인수서를 쓴다."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from data.collectors.common import BRONZE, DATA_ROOT, load_env
from data.config.page_hubs import ACTIVE_HUBS
from data.collectors.seoul_licensing import SERVICES as LICENSE_SERVICES


def main() -> None:
    load_env()
    root=Path(sys.argv[1]).resolve()
    if not root.is_relative_to((BRONZE/'api_acquisition').resolve()):raise ValueError('수집 디렉터리만 허용')
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    original=read(root/'manifest.json')['entries']
    supplement=read(root/'supplement_manifest.json')
    recovery=read(root/'recovery_manifest.json')
    failures=[];facts={};all_ids=set();store_rows=0
    for slug in ACTIVE_HUBS:
        folder=root/('recovery/stores/suyu' if slug=='suyu' else f'stores/{slug}')
        rows=[];totals=set()
        for p in sorted(folder.glob('*.json')):
            if p.name.endswith('.meta.json'):continue
            b=read(p)['body'];rows.extend(b['items']);totals.add(int(b['totalCount']))
        ids=[r.get('bizesId') for r in rows]
        if totals!={len(rows)}:failures.append(f'stores/{slug}: total mismatch')
        if len(set(ids))!=len(ids):failures.append(f'stores/{slug}: duplicate ID within scope')
        if not rows or None in ids:failures.append(f'stores/{slug}: empty or missing ID')
        store_rows+=len(rows);all_ids.update(ids)
    facts['stores']={'hubs':len(ACTIVE_HUBS),'rows_with_hub_overlap':store_rows,'unique_store_ids':len(all_ids)}
    licensing=[]
    for e in supplement:
        if not e['source'].startswith('LOCALDATA_'):continue
        service=e['source'];n=0;ids=set();duplicates=0;totals=set()
        for p in sorted((root/f'seoul/{service}/all').glob('*.json')):
            if p.name.endswith('.meta.json'):continue
            b=read(p)[service];totals.add(int(b['list_total_count']))
            for r in b['row']:
                key=(r.get('OPNSFTEAMCODE'),r.get('MGTNO'))
                if key in ids:duplicates+=1
                ids.add(key);n+=1
        if e['status']!='complete' or totals!={n} or duplicates:
            failures.append(f'{service}: incomplete/count/duplicate check')
        licensing.append({'service':service,'rows':n,'duplicates':duplicates})
    facts['licensing']={'services':len(licensing),'rows':sum(x['rows'] for x in licensing),'details':licensing}
    rone=[e for e in original if e['source'].startswith('rone/')]
    for e in rone:
        n=0
        for p in (root/e['source']).glob('*.json'):
            if p.name.endswith('.meta.json'):continue
            n+=len(read(p)['SttsApiTblData'][1]['row'])
        if n!=e['total'] or e['status']!='complete':failures.append(e['source']+': count')
    facts['rone']={'tables':len(rone),'rows':sum(e.get('rows',0) for e in rone)}
    for service in ['VwsmTrdarRepopQq','VwsmTrdarWrcPopltnQq']:
        paths=list((root/'extras').glob(service+'_*.json'))+list((root/'recovery'/service).glob('*.json'))
        n=0;totals=set();keys=set();duplicates=0
        for p in paths:
            if p.name.endswith('.meta.json'):continue
            b=read(p)[service];totals.add(int(b['list_total_count']))
            for r in b['row']:
                key=(r.get('STDR_YYQU_CD'),r.get('TRDAR_CD'))
                if key in keys:duplicates+=1
                keys.add(key);n+=1
        if totals!={n} or duplicates:failures.append(service+': count/duplicate')
    retry_path=root/'eum_retry_manifest.json'
    if retry_path.exists():
        retry_info=read(retry_path)
        if retry_info['status']=='downloaded_valid_zip':
            retry_file=root/retry_info['path']
            if hashlib.sha256(retry_file.read_bytes()).hexdigest()!=retry_info['sha256']:
                failures.append('eum/lrgt: sha256')
    for e in original:
        if e['status']!='complete' or not e['source'].startswith('seoul/Vwsm'):continue
        service=e['source'].split('/')[1];quarter=e['source'].split('/')[2];n=0
        for p in (root/e['source']).glob('*.json'):
            if p.name.endswith('.meta.json'):continue
            rows=read(p)[service]['row'];n+=len(rows)
            if any(str(r.get('STDR_YYQU_CD'))!=quarter for r in rows):failures.append(e['source']+': period')
        if n!=e['total']:failures.append(e['source']+': count')
    hashes=0
    for p in root.rglob('*.meta.json'):
        m=read(p);raw=Path(str(p)[:-len('.meta.json')])
        if not raw.exists() or hashlib.sha256(raw.read_bytes()).hexdigest()!=m['sha256']:
            failures.append(str(p.relative_to(root))+': sha256')
        hashes+=1
    secrets=[os.environ[k].encode() for k in ['DATA_GO_KR_SERVICE_KEY','SEOUL_OPENAPI_KEY','REB_RONE_API_KEY','EUM_API_KEY'] if os.environ.get(k)]
    for p in root.rglob('*'):
        if p.is_file() and p.suffix in ['.json','.xml','.html']:
            body=p.read_bytes()
            if any(s in body for s in secrets):failures.append(str(p.relative_to(root))+': secret exposed')
    facts.update({'checked_response_hashes':hashes,'failures':failures,'validation_passed':not failures})
    (root/'validation.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
    rel=root.relative_to(DATA_ROOT).as_posix()
    lines=['# PlaceOS API·데이터 실제 확보 결과 — 2026-10-09','',
           f'원본 위치: `{rel}/` (이 문서가 있는 data 폴더 기준).',
           '기존 인증키를 사용해 실제 응답·원본을 확보했다. API 키 신규 발급·신청 완료를 뜻하지 않는다. 나이스·KOPIS 발급은 사용자 담당이다.',
           '원본은 별도 Bronze 실행 폴더에 보존했으며 서비스 Gold와 모델에는 아직 반영하지 않았다.','',
           '## 확보 결과','',
           '| 자료 | 실제 확보 범위 | 상태 | 원본 위치 |','|---|---|---|---|',
           f'| 상가정보 | 서빙 {len(ACTIVE_HUBS)}개 거점 수집 반경 전량, {store_rows:,}행 / 중복 제거 점포 ID {len(all_ids):,}개 | 완료 | `stores/`, 수유는 `recovery/stores/suyu/` |',
           f'| 서울 대상 업종 인허가 | {len(licensing)}개 서비스, {facts["licensing"]["rows"]:,}행. 원천이 제공한 휴폐업 포함 전체 페이지 | 완료 | `seoul/LOCALDATA_*/all/` |',
           f'| R-ONE | 임대료·소규모/중대형 공실률 9개 통계표, {facts["rone"]["rows"]:,}행 | API 제공 분기 시계열 전량 | `rone/` |',
           '| 서울 상권 영역 | 1,650행 | 완료 | `seoul/TbgisTrdarRelm/all/` |',
           '| 서울 추정매출 | 2026년 2분기 21,133행 | 해당 분기 전량 | `seoul/VwsmTrdarSelngQq/20262/` |',
           '| 서울 점포·개폐업 | 2026년 2분기 75,912행 | 해당 분기 전량 | `seoul/VwsmTrdarStorQq/20262/` |',
           '| 서울 길단위인구·상권변화 | 2026년 2분기 각 1,648 / 1,650행 | 해당 분기 전량 | `seoul/VwsmTrdarFlpopQq/`, `seoul/VwsmTrdarIxQq/` |',
           '| 서울 상주·직장인구 | 2021년 1분기~2026년 2분기, 각 35,908 / 36,027행 | 응답 전체 기간 전량 | `extras/`와 `recovery/VwsmTrdar*/` |',
           '| 서울 시간대 생활인구 | API 첫 행 제공일 2026-07-31 하루, 10,176행 | 하루치 전량; 전체 이력 아님 | `recovery/living/20260731/` |',
           '| 토지이음 법령·조례 | 공식 llmt.zip | 다운로드·ZIP CRC 확인 | `eum/llmt.zip` |',
           '| 토지이음 행위제한 | 공식 arhist.zip | 다운로드·ZIP CRC 확인 | `eum/arhist.zip` |',
           '| 토지이음 쉬운규제안내서 | 공식 lrgt.zip 재시도 원본 | 다운로드·ZIP CRC 확인 (재시도 명세 참조) | `eum/lrgt_retry.zip` |',
           '| 토지이음 API 명세 | 공식 Swagger | 확보 | `eum/swagger.json` |',
           '| 문화기반시설 | 문체부 2025 전국 문화기반시설 총람 XLSX (2025-01-01 기준) | 원본 다운로드·파일 구조 확인 | `culture/facilities_2025.xlsx` |',
           '| 건축물대장 | 상가 원천에서 확인한 지번 1곳의 표제부 1건 | API 정상 응답 확인; 전수 재수집 아님 | `extras/building_title_probe.json` |','',
           '상가 행 수는 겹치는 거점 반경 때문에 같은 점포를 포함한다. 합산 행 수를 전국 또는 서울의 점포 수로 쓰지 않는다. 원본 수집일은 원천의 기준일·갱신일과 다르다.',
           '서울 상주·직장인구는 분기 요청 인자가 실제로 필터링되지 않아 응답의 기준분기 필드를 전수 확인하고 전체 기간 자료로 바로잡았다.','',
           '## 미확보·제약','',
           '| 항목 | 확인된 이유 | 다음 조치 |','|---|---|---|',
           '| 토지이음 행위제한 API 호출 | EUM_API_KEY와 공공데이터 키 모두 코드 30, 등록되지 않은 서비스키. URL 인코딩 중복 아님 | [해당 API](https://www.data.go.kr/data/15058410/openapi.do) 활용신청·권한 확인 필요. ZIP 원본은 확보 |',
           '| 서울 상권 소득·소비 | 기존 서비스 ERROR-500. 공식 안내에 갱신 중단 명시 | [공식 설명](https://data.seoul.go.kr/dataList/OA-21278/A/1/datasetView.do) 참고. 다른 공간단위로 임의 대체하지 않음 |',
           '| 서울 2026년 3분기 매출·점포·유동·변화지표 | INFO-200, 제공 자료 없음 | 공표 후 재조회 |',
           '| 서울 생활인구 2026-10-01 | INFO-200 | 확보된 하루치 기준일을 명시하고 추후 갱신 |',
           '| 나이스·KOPIS | 키 미설정 | 사용자 직접 발급 담당 |',
           '| 국세청 휴폐업 상태 | 조회할 사업자등록번호와 점포 연결자료 없음 | 참여 사업자 자료 확보 후 조회 |',
           '| 실제 매출·손익·생존 성과 | POS/PMS/회계·사업자 제공자료 없음 | 체크리스트의 사업자 요청 항목 확보 |',
           '| 전국 인허가 별도 파일·관광 데이터랩·지구단위계획 도형/고시 | 이번 실행에서 추가 확보하지 않음. 현 서빙 서울 인허가는 위 범위 수집 | 필요 지역·기간·제공 방식에 맞춘 별도 수집 |','',
           '## 검증 및 인수','',
           f'- 원본 응답 {hashes:,}개 SHA256 대조, 점포 ID·인허가 식별자 중복 및 페이지 건수 검증.',
           '- 인증키 원문이 저장된 JSON/XML/HTML에 포함되지 않았는지 확인.',
           f'- 검증 결과: {"통과" if not failures else "실패: validation.json 확인"}. 세부 증거: `validation.json`.',
           '- `manifest.json`: 최초 실행 결과. `supplement_manifest.json`: 인허가 전량·문화시설·토지이음 API 응답.',
           '- `recovery_manifest.json`: 수유 재수집·인구 기간 검증 결과. 최초 실패·부분 기록은 삭제하지 않고 복구 결과와 함께 보존.',
           '- `extras_manifest.json`의 인구 부분 수집 기록은 `recovery_manifest.json`에서 전량 확보로 갱신됨.',
           '- 기존 표준 수집 경로에 자동 덮어쓰지 않았으므로 서비스에서 새 자료를 읽으려면 별도 정규화·집계·검증 연결이 필요하다.','',
           '## 대상 업종 인허가 서비스별 건수','',
           '| 업종 | 서비스 | 확보 행 수 |','|---|---|---|']
    labels={service:name for name,service in LICENSE_SERVICES.items()}
    lines += [f'| {labels.get(x["service"], "")} | {x["service"]} | {x["rows"]:,} |' for x in licensing]
    retry=root/'eum_retry_manifest.json'
    if retry.exists():
        item=read(retry)
        lines += ['', '쉬운규제안내서 ZIP 재시도: '+item['status']+'. 상세: `eum_retry_manifest.json`.']
    (DATA_ROOT/'placeos-data-acquisition-result-2026-10-09.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(facts,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
