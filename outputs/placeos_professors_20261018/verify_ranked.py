from pathlib import Path
import zipfile
import xml.etree.ElementTree as E
d=Path(__file__).parent
a=zipfile.ZipFile(d/'PlaceOS_교수_통합명단_추가전백업.xlsx')
b=zipfile.ZipFile(d/'PlaceOS_교수_통합명단.xlsx')
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def cells(z,p):
    strings=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
    out={}
    for c in E.fromstring(z.read(p)).findall('.//m:sheetData/m:row/m:c',ns):
        v=c.find('m:v',ns); f=c.find('m:f',ns)
        value=v.text if v is not None else None
        if c.get('t')=='s': value=strings[int(value)]
        elif c.get('t')=='inlineStr': value=''.join(c.find('m:is',ns).itertext())
        if value is not None or f is not None:out[c.get('r')]=(value,f.text if f is not None else None)
    return out
for p in ['xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml']:
    assert cells(a,p)==cells(b,p),p
    print(p,'existing cell values/formulas preserved')
assert b.testzip() is None
new=cells(b,'xl/worksheets/sheet3.xml')
assert sum(1 for k in new if k.startswith('D') and int(k[1:])>=6)==67
print('67 added, no existing cell changes, valid ZIP')
