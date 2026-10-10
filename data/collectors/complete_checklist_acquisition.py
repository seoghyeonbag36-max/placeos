"""부분 수집 복구 및 응답 기준 기간 검증. 기존 원본은 보존한다."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import requests
from data.collectors.common import BRONZE, load_env
from data.config.page_hubs import ACTIVE_HUBS


def main() -> None:
    load_env()
    root=Path(sys.argv[1]).resolve()
    if not root.is_relative_to((BRONZE/'api_acquisition').resolve()):raise ValueError('수집 디렉터리만 허용')
    results=[]
    def get(name: str,url: str,params: dict | None=None) -> dict:
        p=root/f'recovery/{name}.json'
        if p.exists():return json.loads(p.read_bytes())
        for attempt in range(3):
            try:
                r=requests.get(url,params=params,timeout=(12,45));r.raise_for_status()
                j=r.json()
                if any(os.environ[k].encode() in r.content for k in ['SEOUL_OPENAPI_KEY','DATA_GO_KR_SERVICE_KEY']):
                    raise ValueError('credential_echo')
                p.parent.mkdir(exist_ok=True,parents=True)
                with p.open('xb') as f:f.write(r.content)
                p.with_suffix('.json.meta.json').write_text(json.dumps({
                    'endpoint':url.split(os.environ['SEOUL_OPENAPI_KEY'])[0],
                    'requested_at':dt.datetime.now(dt.timezone.utc).isoformat(),
                    'http_status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)
                },indent=2),encoding='utf-8')
                return j
            except requests.RequestException:
                if attempt==2:raise
                time.sleep(1)
        raise RuntimeError('unreachable')
    for service in ['VwsmTrdarRepopQq','VwsmTrdarWrcPopltnQq']:
        try:
            n=0;quarters=set()
            for page in range(1,101):
                p=root/f'extras/{service}_{page}.json'
                # 요청 분기 필터가 적용되지 않은 기존 응답도 원본대로 보존·집계한다.
                if p.exists():j=json.loads(p.read_bytes())
                else:
                    start=(page-1)*1000+1
                    j=get(f'{service}/{page:03}',f'http://openapi.seoul.go.kr:8088/{os.environ["SEOUL_OPENAPI_KEY"]}/json/{service}/{start}/{start+999}/20262')
                b=j[service];rows=b['row'];n+=len(rows);total=int(b['list_total_count'])
                quarters.update(str(r.get('STDR_YYQU_CD')) for r in rows)
                if n>=total:break
                if not rows:raise ValueError('empty_page')
            results.append({'source':service,'status':'complete' if n==total else 'partial','rows':n,'total':total,
                            'actual_quarters':sorted(quarters),'note':'요청 분기 필터 미적용 확인. 응답 전체 기간 자료로 표시'})
        except Exception as e:results.append({'source':service,'status':'failed','error_type':type(e).__name__})
    try:
        service='SPOP_LOCAL_RESD_DONG'
        j=get('living_latest_probe',f'http://openapi.seoul.go.kr:8088/{os.environ["SEOUL_OPENAPI_KEY"]}/json/{service}/1/1')
        row=j[service]['row'][0];date=str(row['STDR_DE_ID']);n=0
        for page in range(1,31):
            start=(page-1)*1000+1
            j=get(f'living/{date}/{page:03}',f'http://openapi.seoul.go.kr:8088/{os.environ["SEOUL_OPENAPI_KEY"]}/json/{service}/{start}/{start+999}/{date}')
            b=j[service];rows=b['row'];n+=len(rows);total=int(b['list_total_count'])
            if any(str(r['STDR_DE_ID'])!=date for r in rows):raise ValueError('date_filter_not_applied')
            if n>=total:break
        results.append({'source':service,'status':'complete_day' if n==total else 'partial','date':date,'rows':n,'total':total,
                        'note':'API 첫 행에서 확인한 제공일 하루치. 전체 과거 기간 아님'})
    except Exception as e:results.append({'source':'living_population','status':'failed','error_type':type(e).__name__})
    try:
        hub=ACTIVE_HUBS['suyu'];n=0
        for page in range(1,101):
            j=get(f'stores/suyu/{page:03}','https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius',{
                'serviceKey':os.environ['DATA_GO_KR_SERVICE_KEY'],'type':'json','numOfRows':1000,'pageNo':page,
                'radius':hub.stores_radius_m,'cx':hub.cx,'cy':hub.cy})
            b=j['body'];rows=b['items'];n+=len(rows);total=int(b['totalCount'])
            if n>=total:break
        results.append({'source':'stores/suyu','status':'complete' if n==total else 'partial','rows':n,'total':total,
                        'note':'최초 수집 중 네트워크 실패를 새 원본으로 복구'})
    except Exception as e:results.append({'source':'stores/suyu','status':'failed','error_type':type(e).__name__})
    (root/'recovery_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:print(r,flush=True)


if __name__=='__main__':main()
