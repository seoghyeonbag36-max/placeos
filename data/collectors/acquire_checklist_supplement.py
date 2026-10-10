"""체크리스트 보충 확보: 인허가 전량·토지이음 API·문화시설 원본.

실행 인자는 첫 수집 실행 디렉터리. Gold에는 쓰지 않는다.
"""
from __future__ import annotations
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import requests
from data.collectors.common import BRONZE, load_env


def main() -> None:
    load_env()
    root = Path(sys.argv[1]).resolve()
    if not root.is_relative_to((BRONZE/'api_acquisition').resolve()):
        raise ValueError('수집 작업 디렉터리만 허용')
    entries: list[dict] = []
    lock = threading.Lock()
    def log(source: str, status: str, **kw: object) -> None:
        with lock:
            entries.append(dict(source=source, status=status, **kw))
            (root/'supplement_manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
            print(source,status,kw.get('rows',''),flush=True)
    def get(name: str, url: str, params: dict | None = None, suffix: str = 'json') -> bytes:
        p=root/f'{name}.{suffix}'
        if p.exists():
            return p.read_bytes()
        r=requests.get(url,params=params,timeout=(12,60))
        raw=r.content
        for k in ['DATA_GO_KR_SERVICE_KEY','EUM_API_KEY','SEOUL_OPENAPI_KEY']:
            s=os.environ.get(k,'')
            if s and s.encode() in raw:
                raise ValueError('credential_echo')
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
        meta={'endpoint':url.split(os.environ.get('SEOUL_OPENAPI_KEY','___'))[0] if 'openapi.seoul' in url else url,
              'http_status':r.status_code,'content_type':r.headers.get('content-type'),
              'requested_at':dt.datetime.now(dt.timezone.utc).isoformat(),
              'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        p.with_suffix(p.suffix+'.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        r.raise_for_status()
        return raw
    def licensing(service: str) -> None:
        n=0
        try:
            for page in range(1,801):
                start=(page-1)*1000+1
                raw=get(f'seoul/{service}/all/{page:03}',
                    f'http://openapi.seoul.go.kr:8088/{os.environ["SEOUL_OPENAPI_KEY"]}/json/{service}/{start}/{start+999}')
                j=json.loads(raw)[service]
                total=int(j['list_total_count']);rows=j.get('row') or [];n+=len(rows)
                if n>=total:
                    log(service,'complete',rows=n,total=total);return
                if not rows:raise ValueError('empty_page_before_total')
                time.sleep(.15)
            raise ValueError('page_limit')
        except Exception as e:log(service,'failed_or_partial',rows=n,error_type=type(e).__name__)
    def eum() -> None:
        for keyname in ['EUM_API_KEY','DATA_GO_KR_SERVICE_KEY']:
            try:
                raw=get(f'eum/api_probe_{keyname}',
                    'https://apis.data.go.kr/1613000/arLandUseInfoService/DTsearchLunCd',
                    {'serviceKey':os.environ[keyname],'pageNum':1,'numOfRows':100,'landUseNm':'학원'},'xml')
                doc=ET.fromstring(raw)
                code=doc.findtext('.//resultCode') or doc.findtext('.//returnReasonCode')
                msg=doc.findtext('.//resultMsg') or doc.findtext('.//returnAuthMsg')
                log(f'eum_api/{keyname}','api_success' if code in ['00','0'] else 'api_error',code=code,message=msg,
                    rows=len(doc.findall('.//item')),scope='학원 행위명 조회; 필지별 규제 판정 아님')
            except Exception as e:log(f'eum_api/{keyname}','failed',error_type=type(e).__name__)
    def culture() -> None:
        try:
            raw=get('culture/facilities_2025',
                'https://www.mcst.go.kr/servlets/eduport/front/upload/UplDownloadFile',
                {'pFileName':'2025 전국 문화기반시설 총람.xlsx',
                 'pRealName':'DEPTDATA_20251217021949027003.xlsx','pPath':'0417000000','pFlag':''},'xlsx')
            p=root/'culture/facilities_2025.xlsx'
            with zipfile.ZipFile(p) as z:
                if '[Content_Types].xml' not in z.namelist() or z.testzip():raise ValueError('invalid_xlsx')
            log('culture_facilities_2025','downloaded_valid_xlsx',bytes=len(raw),reference_date='2025-01-01')
        except Exception as e:log('culture_facilities_2025','failed',error_type=type(e).__name__)
    # 체크리스트의 주점·미용·숙박·운동·여가. 일반음식점은 주점 분류 보완에 필요.
    services=['LOCALDATA_'+x for x in ['072404','031101','031103','051801','103201','104201',
              '104101','103101','103302','030901','030505','030506','030504','072301','072302']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(eum),pool.submit(culture)]+[pool.submit(licensing,s) for s in services]
        for f in concurrent.futures.as_completed(futures):f.result()


if __name__=='__main__':main()
