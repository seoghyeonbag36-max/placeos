"""부산 조사 범위와 전유부 소요 추정의 근거를 읽기 전용으로 집계한다."""
from __future__ import annotations
import contextlib
import html
import io
import json
import math
import sys
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import collect_regional_research_ledgers as source
from scripts.run_busan_research import STORES
from data.collectors.building_vacancy import group_by_building, NON_STOREFRONT_LCLS

OUT = ROOT / 'output/busan-research-2026-11-06'
OUT.mkdir(parents=True, exist_ok=True)
snapshot = STORES / 'stores_complete.json'
raw = source.read(snapshot)
rows = raw['rows']
groups = defaultdict(list)
for r in rows:
    groups[str(r['adongCd'])].append(r)
details, all_pnus = [], set()
for code, stores in sorted(groups.items()):
    with contextlib.redirect_stdout(io.StringIO()):
        buildings = group_by_building(stores)
    pnus, invalid = set(), 0
    for b in buildings.values():
        p = str(b.get('lnoCd') or '')
        if len(p) == 19 and p.isdigit() and p.startswith('26'):
            pnus.add(p)
        else:
            invalid += 1
    all_pnus |= pnus
    details.append(dict(gu=stores[0]['signguNm'], dong=stores[0]['adongNm'], code=code,
        stores=len(stores), buildings=len(buildings), pnus=sorted(pnus), invalid_pnu_buildings=invalid,
        excluded_stores=sum(s.get('indsLclsNm') in NON_STOREFRONT_LCLS for s in stores),
        missing_building_key=sum(s.get('indsLclsNm') not in NON_STOREFRONT_LCLS and not s.get('bldMngNo') for s in stores),
        legal_dongs=sorted({s['ldongNm'] for s in stores})))
by_gu = []
for gu in sorted({r['gu'] for r in details}):
    ds = [d for d in details if d['gu'] == gu]
    by_gu.append(dict(gu=gu, dongs=len(ds), stores=sum(d['stores'] for d in ds),
        pnus=len(set().union(*(set(d['pnus']) for d in ds))),
        invalid_pnu_buildings=sum(d['invalid_pnu_buildings'] for d in ds),
        dong_names=[d['dong'] for d in ds]))
reference = source.read(OUT / 'busan_expos_reference_sample.json')
n = len(all_pnus)
scenarios = [dict(name=name, pages_per_parcel=factor, calls=math.ceil(n*factor),
                 days_at_10000=math.ceil(n*factor/10000), days_at_5000=math.ceil(n*factor/5000))
             for name, factor in [('모든 지번 1페이지인 하한', 1), ('전주·광주 완료 표본 평균 적용', reference['mean_pages']),
                                  ('부산 대형건물 증가 가정', max(3,reference['mean_pages']*1.5))]]
sources = [
 ('점포 원본 API', 'https://www.data.go.kr/data/15012005/openapi.do'),
 ('건축HUB 제공 항목', 'https://www.hub.go.kr/portal/psg/idx-intro-openApi.do'),
 ('전포카페거리·서면 관계', 'https://visitbusan.net/archive/dataSearch/view.nm?dataSid=METADATA012800'),
 ('서면시장 소재지', 'https://access.visitkorea.or.kr/ms/detail.do?cotId=149fdf66-7cb1-46b7-b9c2-ba8316b06a00'),
 ('광복로·국제시장 연결', 'https://www.bsjunggu.go.kr/tour/index.junggu?idx=55999&menuCd=DOM_000000201002000000'),
 ('해리단길 우동 소재', 'https://japanese.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=194909'),
 ('광안리·민락·남천 지역', 'https://www.suyeong.go.kr/tour/index.suyeong'),
 ('기장시장 대라리 소재', 'https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid=7a346d2b-7e23-485c-831d-6fe669ef9f94'),
]
examples = [
 ('서면이 위치한 부전동', lambda r:r['signguNm']=='부산진구' and r['ldongNm']=='부전동', 3),
 ('전포카페거리가 위치한 전포동', lambda r:r['signguNm']=='부산진구' and r['ldongNm']=='전포동', 2),
 ('남포·광복 지역', lambda r:r['signguNm']=='중구' and r['ldongNm'].startswith(('남포동','광복동')), 4),
 ('해리단길이 위치한 우동', lambda r:r['signguNm']=='해운대구' and r['ldongNm']=='우동', 5),
 ('광안리 주변 광안·민락·남천동', lambda r:r['signguNm']=='수영구' and r['ldongNm'] in ('광안동','민락동','남천동'), 6),
 ('기장시장이 위치한 기장읍 대라리', lambda r:r['signguNm']=='기장군' and '기장읍 대라리' in r.get('lnoAdr',''), 7),
]
example_rows=[]
for title, filt, idx in examples:
    ss=[r for r in rows if filt(r)]
    example_rows.append(dict(name=title, stores_in_legal_area=len(ss),
        observed_administrative_dongs=sorted({r['adongNm'] for r in ss}), source=sources[idx][1]))
summary=dict(observed_at=raw['observed_at'],source_period='202609',stores=len(rows),
    districts=len(by_gu),administrative_dongs=len(details),target_unique_pnus=n,
    invalid_pnu_buildings=sum(d['invalid_pnu_buildings'] for d in details),
    excluded_stores=sum(d['excluded_stores'] for d in details),
    missing_building_key=sum(d['missing_building_key'] for d in details),
    source_snapshot=snapshot.relative_to(ROOT).as_posix(),source_sha256=source.fingerprint(snapshot),
    source='SDSC storeListInDong ctprvnCd=26; 158 pages; building grouping as current collector',seed=False)
result=dict(summary=summary,reference_sample=reference,scenarios=scenarios,by_district=by_gu,
    by_administrative_dong=details,representative_areas=example_rows,public_sources=sources)
source.atomic_json(OUT/'busan_scope_evidence.json',result)

def num(v):return f'{v:,}'
def table(headers,data):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(str(c) for c in r)+' |\n' for r in data)

text=f'''# 부산 수집 범위와 전유부 수집 소요 추정

조회 기준: {raw['observed_at']} (한국시간). 소상공인 상가정보 기준월: 2026년 9월.

## 핵심 결과

부산 {len(by_gu)}개 구·군, 원본에 관측된 {len(details)}개 행정동의 등록 점포 {num(len(rows))}개를 확인했다. 현재 수집기의 건물 그룹화·지번 검증 규칙을 적용하면 전유부 대상은 중복 제거 {num(n)}지번이다. 이는 계획 수립용 집계이며 부산 대장 수집은 아직 시작하지 않았다.

전유부는 지번당 최소 1콜이며 100행을 넘으면 추가 페이지를 받는다. 0건 정상 응답도 1콜을 쓴다. 현재 코드의 전유부 일일 요청 제한은 10,000콜이다. 이는 로컬 가드 값이며 같은 키의 다른 작업, 실제 API 제한, 재시도에 따라 가용량이 줄어든다.

## 소요 시간: 실제 대상 수와 가정을 분리

{table(['계산 시나리오','지번당 페이지','추정 콜 수','하루 10,000콜','하루 5,000콜'],[(s['name'],f"{s['pages_per_parcel']:.3f}",num(s['calls']),str(s['days_at_10000'])+'일',str(s['days_at_5000'])+'일') for s in scenarios])}

전주·광주 완료 지번 무작위 표본 {reference['sample_size']}개의 지번당 페이지 평균은 {reference['mean_pages']:.3f}, 중앙값은 {reference['median_pages']}, 최대는 {reference['max_pages']}페이지다. 여러 페이지인 지번은 {reference['multipage']}개다. 이 평균은 부산 측정값이 아니며, 완료된 지번에 한정되어 표본 편향과 도시 간 건물 구성 차이가 있다. 위 표는 예상치와 민감도 계산이고 완료 약속이 아니다. 마지막 행의 배수 역시 가정이다.

표의 일수는 부산 전유부에 해당 일일 호출량을 쓸 수 있는 수집일 기준이다. 시작일의 잔여 쿼터에 따라 날짜가 달라지며, AC 전원·네트워크·절전·디스크 공간·오류 재시도에 따라 늦어진다. 층별개요는 별도 오퍼레이션이지만 같은 작업기가 순회하므로 실제 처리시간을 추가한다. Gold 검증 시간도 별도다. 부산 전유부 최초 수집 후 실제 페이지 평균으로 다시 추정해야 한다.

## 실제 수집 범위

- 선정 방식: 소상공인 상가정보 `storeListInDong`, `divId=ctprvnCd`, `key=26`의 전체 페이지. 특정 유명 상권만 선정하지 않는다.
- 위치 구분: API의 구·군 / 행정동 / 법정동. 아래 행정동 이름은 API 원본 관측값이며 최신 행정구역 공표 목록과 동일하다고 가정하지 않는다.
- 대장 호출 단위: 등재 점포를 기존 `bldMngNo` 건물 그룹화 규칙으로 묶고 유효한 부산 PNU를 중복 제거한다. 여러 건물이 같은 지번을 쓰면 한 번 조회한다.
- 전체 등재 점포 중 기존 규칙으로 제외되는 업종: {num(summary['excluded_stores'])}개 점포. 제외 업종은 기존 코드의 `NON_STOREFRONT_LCLS`를 그대로 따른다.
- 제외 업종을 뺀 뒤 건물관리번호가 없는 점포: {num(summary['missing_building_key'])}개. 유효 PNU가 없는 건물 그룹: {num(summary['invalid_pnu_buildings'])}개. 빠진 값을 추정해 채우지 않는다.
- 점포가 등재되지 않은 빈 건물과 도시 전체 건물은 범위에 포함됐다고 주장하지 않는다.
- 상권 경계·공실률·임대료·매출·유동인구·감성·공식 R-ONE 상권 매핑은 이 수집만으로 만들어지지 않는다. 서비스용 Page 승격은 별도 검증이 필요하다.
- 현재 자동 순서는 전주·광주 원본 및 Gold 검증 → 부산이다. 부산은 별도 원장으로 돌고 기존 경기 수집은 보류한다.

## 구·군별 대상

지번 수는 각 구·군 안에서 중복 제거했다. 전체 합계는 부산 전역에서 다시 중복 제거한 값이다.

{table(['구·군','관측 행정동','등록 점포','대장 대상 지번','PNU 오류 건물'],[(d['gu'],d['dongs'],num(d['stores']),num(d['pnus']),d['invalid_pnu_buildings']) for d in by_gu])}

## 대표 상권과 조사 지역의 관계

다음은 공식 관광 자료에서 위치를 확인할 수 있는 대표 사례다. **이 6개만 수집하는 것이 아니며, 표의 점포 수는 상권 경계 내부 수가 아니라 이름에 표시한 법정동 지역 전체의 등록 점포 수**다. 공식 상권 경계 폴리곤을 적용하지 않았다. 같은 동의 다른 골목·생활 상권도 포함된다.

{table(['대표 사례 / 집계한 지역','법정동 지역 점포','원본 관측 행정동'],[(e['name'],num(e['stores_in_legal_area']),' · '.join(e['observed_administrative_dongs'])) for e in example_rows])}

## 전체 행정동별 수집 목록

{table(['구·군','행정동','행정동 코드','등록 점포','대장 대상 지번','PNU 오류 건물'],[(d['gu'],d['dong'],d['code'],num(d['stores']),num(len(d['pnus'])),d['invalid_pnu_buildings']) for d in sorted(details,key=lambda x:(x['gu'],x['code']))])}

## 출처와 재현 근거

'''
for title,url in sources:text+=f'- [{title}]({url})\n'
text+=f'''\n- 실제 API 원본: `{snapshot.relative_to(ROOT).as_posix()}`. 158개 페이지 전체 수신·totalCount 일치·점포 고유키 중복 없음·부산 시도코드 검증 후 집계.
- 원본 SHA-256: `{summary['source_sha256']}`.
- 집계 규칙: `scripts/run_busan_research.py`의 `build_plan()`과 같은 행정동별 `group_by_building()`·유효 PNU 중복 제거.
- 표본 원본: `data/bronze/regional_research_ledgers/2026-11-03/expos/*/complete.json` 중 전주·광주 대상 완료 지번. 표본 난수 고정값 20261106.
- 실측 집계에는 seed를 사용하지 않았다. 소요 콜 수와 일수는 명시한 가정에 따른 추정이다.
'''
(OUT/'부산_수집범위와_소요일수.md').write_text(text,encoding='utf-8')

# 외부 스크립트·폰트 없이 열리는 공유용 HTML. 모든 원본 행정동을 유지한다.
def ht(headers,data):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in data)+'</tbody></table>'
parts=[]
for line in text.splitlines():
    if line.startswith('|'):continue
    if not line:continue
    if line.startswith('# '):parts.append('<h1>'+html.escape(line[2:])+'</h1>')
    elif line.startswith('## '):parts.append('<h2>'+html.escape(line[3:])+'</h2>')
    else:parts.append('<p>'+html.escape(line)+'</p>')
    if line=='## 소요 시간: 실제 대상 수와 가정을 분리':parts.append(ht(['시나리오','페이지/지번','추정 콜','1만콜/일','5천콜/일'],[(s['name'],round(s['pages_per_parcel'],3),num(s['calls']),s['days_at_10000'],s['days_at_5000']) for s in scenarios]))
    elif line=='## 구·군별 대상':parts.append(ht(['구·군','행정동','점포','지번','PNU 오류'],[(d['gu'],d['dongs'],num(d['stores']),num(d['pnus']),d['invalid_pnu_buildings']) for d in by_gu]))
    elif line=='## 대표 상권과 조사 지역의 관계':parts.append(ht(['대표 사례 / 지역','지역 점포','행정동'],[(e['name'],num(e['stores_in_legal_area']),' · '.join(e['observed_administrative_dongs'])) for e in example_rows]))
    elif line=='## 전체 행정동별 수집 목록':parts.append(ht(['구·군','행정동','코드','점포','지번','PNU 오류'],[(d['gu'],d['dong'],d['code'],num(d['stores']),num(len(d['pnus'])),d['invalid_pnu_buildings']) for d in sorted(details,key=lambda x:(x['gu'],x['code']))]))
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>부산 수집 범위 · 2026-11-06</title><style>body{margin:0;background:#f3f5f7;color:#162333;font:16px/1.8 "Malgun Gothic",sans-serif}main{max-width:1100px;margin:36px auto;background:white;padding:44px}h1{font-size:32px;line-height:1.4}h2{margin-top:38px;border-top:2px solid #193b54;padding-top:18px;font-size:22px}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}th{background:#193b54;color:white;text-align:left}td,th{padding:9px 12px;border-bottom:1px solid #dbe2e8}tr:nth-child(even){background:#f4f7fa}p{overflow-wrap:anywhere}@media print{body{background:white}main{margin:0;padding:0}thead{display:table-header-group}tr{break-inside:avoid}}</style><main>'''+''.join(parts)+'</main></html>'
page = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', page)
page = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', page)
page = re.sub(r'`([^`]+)`', r'<code>\1</code>', page)
(OUT/'부산_수집범위와_소요일수.html').write_text(page,encoding='utf-8')
with zipfile.ZipFile(OUT/'busan-research-materials.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in OUT.iterdir():
        if path.suffix in ('.md','.html','.json'):
            archive.write(path,path.name)
print(json.dumps(dict(summary=summary,reference=reference,scenarios=scenarios,by_gu=by_gu),ensure_ascii=False,indent=2))
