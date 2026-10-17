"""제출 원고의 근거·링크와 Word 패키지 무결성을 검수한다.

사용: python docs/papers/verify_paper_submission.py [--src 원고폴더] [--docx Word폴더] [--stamp YYYYMMDD]
  기본값은 build_papers_docx.py 와 같다(원고: docs/papers 또는 docs/papers/논문 초안, Word: docs/papers/output, 날짜 20260919).
"""
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import json
import math
import re
import posixpath
from lxml import etree

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--src',type=Path,default=None)
ap.add_argument('--docx',type=Path,default=BASE/'output')
ap.add_argument('--stamp',default='20260919')
args=ap.parse_args()
SRC=(args.src or (BASE if (BASE/'paper-platform.md').exists() else BASE/'논문 초안')).resolve()
DOCX=args.docx.resolve()

idx=(BASE/'evidence-index.md').read_text(encoding='utf-8-sig')
idx=idx.replace('pp','%p')
results=[]
for track in ('Platform','Page','Posting','Program'):
    src=(SRC/f'paper-{track.lower()}.md').read_text(encoding='utf-8-sig')
    assert '<!-- FILL' not in src and '<!-- TODO' not in src,track
    assert all(x in src for x in ('초록','서론','결론','참고문헌')),track
    assert '연구질문 RQ와 가설' in src and '가설 검증 결과' in src,track
    expected=3 if track in ('Platform','Program') else 4
    for number in range(1,expected+1):
        assert f'**RQ{number}.' in src and f'**H{number}:' in src,(track,number)
        assert f'| H{number} ' in src,(track,number,'판정 누락')
    for target in re.findall(r'\]\(([^)]+)\)',src):
        if not target.startswith('http'):
            assert (SRC/target.split('#')[0]).exists(),(track,target)
    body=re.sub(r'^#+\s+\d+(?:\.\d+)*\.?\s+','',src,flags=re.M)
    absent=sorted(x for x in set(re.findall(r'[0-9]+\.[0-9]+%?|[0-9]{3,}',body)) if x not in idx)
    assert not absent,(track,absent)
    path=DOCX/f'PlaceOS_{track}_논문_{args.stamp}.docx'
    with ZipFile(path) as z:
        assert z.testzip() is None
        root=etree.fromstring(z.read('word/document.xml'))
        text=''.join(root.xpath('//w:t/text()',namespaces=NS))
        assert all(x in text for x in ('초록','서론','결론','참고문헌')),track
        assert '연구질문 RQ와 가설' in text and '가설 검증 결과' in text,track
        for number in range(1,expected+1):
            assert f'RQ{number}.' in text and f'H{number}:' in text,(track,number,'Word 누락')
        assert '�' not in text
        # Word에서 다시 저장하면 추가 글꼴이 임베딩된다. 개수 대신 연결 무결성을 검사한다.
        font_table=etree.fromstring(z.read('word/fontTable.xml'))
        font_rels=etree.fromstring(z.read('word/_rels/fontTable.xml.rels'))
        rels={rel.get('Id'):rel for rel in font_rels}
        embedded=font_table.xpath('//w:embedRegular | //w:embedBold | //w:embedItalic | //w:embedBoldItalic',namespaces=NS)
        assert len(embedded)>=2,(track,'임베딩 글꼴 부족')
        assert font_table.xpath('//w:embedRegular',namespaces=NS) and font_table.xpath('//w:embedBold',namespaces=NS)
        for entry in embedded:
            rel=rels[entry.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            assert rel.get('Type','').endswith('/font') and rel.get('TargetMode')!='External'
            target=posixpath.normpath(posixpath.join('word',rel.get('Target','')))
            assert target.startswith('word/fonts/') and target.endswith('.odttf')
            assert z.getinfo(target).file_size>32,(track,'빈 임베딩 글꼴')
            assert entry.get('{'+NS['w']+'}fontKey'),(track,'글꼴 복호화 키 누락')
        assert not root.xpath('//w:trHeight[@w:hRule="exact"]',namespaces=NS)
        styles=etree.fromstring(z.read('word/styles.xml'))
        heading_ids={style.get('{'+NS['w']+'}styleId') for style in styles.findall('w:style',NS)
            if style.find('w:name',NS) is not None and
            re.sub(r'\s+','',style.find('w:name',NS).get('{'+NS['w']+'}val','')).lower() in {'heading1','heading2'}}
        headings=[paragraph for paragraph in root.findall('.//w:p',NS)
            if paragraph.find('w:pPr/w:pStyle',NS) is not None and
            paragraph.find('w:pPr/w:pStyle',NS).get('{'+NS['w']+'}val') in heading_ids]
        assert len(headings)>6
        for n in z.namelist():
            if n.endswith('.xml'): etree.fromstring(z.read(n))
    results.append({'track':track,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'structure_verified'})

# 학습을 재실행하지 않고 보존된 대응표의 집계만 검산한다.
report=json.loads((ROOT/'reports/gnn_category2_mcnemar_2026-08-27.json').read_text(encoding='utf-8'))
for pair in report['mcnemar']:
    a,b=pair['a_only_hit'],pair['b_only_hit']
    assert pair['both_hit']+pair['both_miss']+a+b==pair['n']
    assert a+b==pair['discordant']
    chi=((abs(a-b)-1)**2/(a+b)) if a+b else 0
    assert round(chi,3)==pair['chi2']
    assert round(math.erfc(math.sqrt(chi/2)),4)==pair['p_value']
    assert round((b-a)/pair['n']*100,2)==pair['delta_pp']
suffix='' if args.stamp=='20260919' else f'-{args.stamp}'
out=BASE/f'page-study/private/submission-structural-checks{suffix}.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'documents':results,'mcnemar_summary_check':'passed','visual_qa':'separate'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'documents':len(results),'status':'passed','mcnemar_summary':'passed'},ensure_ascii=False))
