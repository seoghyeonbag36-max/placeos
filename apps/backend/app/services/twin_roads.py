"""3D 트윈 주변 실제 도로 — `GET /buildings/{id}/twin` 응답에 붙는 도로 중심선 (2026-11-06).

OpenStreetMap 도로를 OpenFreeMap 벡터 타일(z14, 키 없음 · `tiles.openfreemap.org`)에서 읽어 건물 반경 300m 안만 뽑는다.
- 타일 경계 여백(buffer)을 잘라 이웃 타일과 겹치는 선을 없앤다.
- 이름은 같은 타일의 transportation_name 선을 선분마다 대조해 붙인다(이름이 다른 길이 한 선으로 이어진 경우가 있어서).
- 표준 라이브러리만 쓴다(벡터 타일 해석 포함). 외부 의존성 없음.

## 이 값이 아닌 것

- **폭(m)은 실측이 아니다.** 보도 포함 전체 폭과 한쪽 보도 폭을 도로 등급으로 추정한다(아는 길만 `WIDTH_OVERRIDES`).
  실측 폭이 필요하면 도로명주소 전자지도 실폭도로로 바꾼다.
- 출처 표기 필수: 「© OpenStreetMap 기여자 (ODbL)」 — `roads_source` 로 내보내고 트윈 화면이 표시한다.
- 카카오맵 화면·API 결과는 저장할 수 없어 여기서 쓰지 않는다(화면이 같은 좌표를 여는 비교 링크만 둔다).

## 실패해도 트윈은 산다

`roads_for_twin` 은 예외를 내지 않는다 — 타일을 못 받으면 `roads=[]` + `roads_error` 이고 건물·층 응답은 그대로다.
첫 실패는 한 번 더 시도한다 — 새로 뜬 Cloud Run 인스턴스의 첫 외부 연결이 늦어 첫 요청만 도로가 비던 문제(2026-11-08 배포 직후
두 번 관측). 두 번 다 실패하면 `_FAIL_BACKOFF_S` 동안 타일 서버를 다시 치지 않는다(장애 때 트윈 요청마다 타임아웃을 기다리지 않게).
실패는 로그(`twin_roads`)로 남겨 원인을 Cloud Run 로그에서 본다.

    roads = roads_near(lat, lng)                          # [{n, c, w, sw, ow, line:[[lat, lng], ...]}, ...]
    check = address_road_check(ring, road_addr, roads)    # 도로명주소의 도로가 건물 바로 앞에 있는지
"""
from __future__ import annotations

import gzip
import json
import logging
import math
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Callable, Iterable

Fetch = Callable[[int, int, int], bytes]

TILEJSON_URL = 'https://tiles.openfreemap.org/planet'
Z = 14
SOURCE = {'by': '© OpenStreetMap 기여자', 'license': 'ODbL', 'license_url': 'https://www.openstreetmap.org/copyright', 'via': 'OpenFreeMap 벡터 타일'}
M_PER_DEG = 111320.0

# 등급별 기본 폭(보도 포함 전체 m, 한쪽 보도 m) — 추정치
CLASS_WIDTH = {'motorway': (36, 0), 'trunk': (36, 3), 'primary': (30, 4), 'secondary': (24, 3.5), 'tertiary': (16, 3),
               'minor': (8, 1.2), 'service': (4.5, 0), 'pedestrian': (5, 5), 'busway': (8, 0)}
# 이름별 폭(아는 길만). 상하행이 나뉜 큰길은 한쪽을 그릴 때 절반 가까이로 줄입니다(roads_near).
WIDTH_OVERRIDES = {'성수이로': (25, 3), '연무장길': (10, 1.5), '상원길': (6, 0), '아차산로': (30, 4), '뚝섬로': (30, 4),
                   '왕십리로': (25, 3.5), '성수일로': (20, 3), '광나루로': (30, 4)}
SKIP_SERVICE = {'parking_aisle', 'driveway', 'drive-through'}
_FAIL_BACKOFF_S = 15.0       # 타일 서버가 두 번 연달아 실패한 뒤 다시 치지 않는 시간(60초 → 15초: 일시 장애로 도로가 오래 비지 않게)
_TIMEOUT_S = 8.0             # 요청 하나의 제한 시간(5초 → 8초: 새 인스턴스의 첫 연결 DNS·TLS 여유)
_last_fail = 0.0
log = logging.getLogger("twin_roads")


# ── 벡터 타일(Mapbox Vector Tile) 최소 해석기 ─────────────────────────────
def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s
        if c < 0x80: return r, i
        s += 7

def _fields(b: bytes):
    """(필드 번호, 선 형식, 값) — 값은 int(varint) 또는 bytes(길이 지정 · 32/64비트)."""
    i, n = 0, len(b)
    while i < n:
        key, i = _varint(b, i); f, wt = key >> 3, key & 7
        if wt == 0: v, i = _varint(b, i)
        elif wt == 1: v, i = b[i:i + 8], i + 8
        elif wt == 2:
            ln, i = _varint(b, i); v, i = b[i:i + ln], i + ln
        elif wt == 5: v, i = b[i:i + 4], i + 4
        else: raise ValueError(f'지원하지 않는 선 형식 {wt}')
        yield f, wt, v

def _packed(b: bytes) -> list[int]:
    out, i = [], 0
    while i < len(b):
        v, i = _varint(b, i); out.append(v)
    return out

def _value(b: bytes):
    import struct
    for f, wt, v in _fields(b):
        if f == 1: return v.decode('utf-8')
        if f == 2: return struct.unpack('<f', v)[0]
        if f == 3: return struct.unpack('<d', v)[0]
        if f in (4, 5): return v if f == 5 or v < 1 << 63 else v - (1 << 64)
        if f == 6: return (v >> 1) ^ -(v & 1)
        if f == 7: return bool(v)
    return None

def _clip(a, b, ext):
    """선분 a→b 를 [0, ext] 정사각형으로 자른 (t0, t1) — Liang–Barsky."""
    t0, t1 = 0.0, 1.0
    for pa, pb in ((a[0], b[0]), (a[1], b[1])):
        d = pb - pa
        for p, q in ((-d, pa), (d, ext - pa)):
            if p == 0:
                if q < 0: return None
            else:
                r = q / p
                if p < 0: t0 = max(t0, r)
                else: t1 = min(t1, r)
    return (t0, t1) if t0 <= t1 else None

def decode_lines(pbf: bytes, x: int, y: int, z: int = Z, layers: Iterable[str] = ('transportation', 'transportation_name')) -> list[tuple[str, dict, list[list[float]]]]:
    """타일의 선(LINESTRING)을 [(층 이름, 속성, [[위도, 경도], …]), …]로. 타일 경계 밖 여백은 잘라 냅니다."""
    if pbf[:2] == b'\x1f\x8b': pbf = gzip.decompress(pbf)
    want, out, n = set(layers), [], 2 ** z
    for f, _, layer in _fields(pbf):
        if f != 3: continue
        name, feats, keys, vals, ext = None, [], [], [], 4096
        for lf, _, lv in _fields(layer):
            if lf == 1: name = lv.decode('utf-8')
            elif lf == 2: feats.append(lv)
            elif lf == 3: keys.append(lv.decode('utf-8'))
            elif lf == 4: vals.append(_value(lv))
            elif lf == 5: ext = lv
        if name not in want: continue
        to_ll = lambda px, py: [math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / ext) / n)))), (x + px / ext) / n * 360 - 180]
        for ft in feats:
            tags, gtype, geom = [], 0, []
            for ff, _, fv in _fields(ft):
                if ff == 2: tags = _packed(fv)
                elif ff == 3: gtype = fv
                elif ff == 4: geom = _packed(fv)
            if gtype != 2: continue
            props = {keys[tags[k]]: vals[tags[k + 1]] for k in range(0, len(tags) - 1, 2)}
            # 명령: MoveTo(1) · LineTo(2), 인자는 지그재그 부호 차이값
            lines, cur, cx, cy, i = [], [], 0, 0, 0
            while i < len(geom):
                cmd, cnt = geom[i] & 7, geom[i] >> 3; i += 1
                if cmd in (1, 2):
                    for _ in range(cnt):
                        dx, dy = geom[i], geom[i + 1]; i += 2
                        cx += (dx >> 1) ^ -(dx & 1); cy += (dy >> 1) ^ -(dy & 1)
                        if cmd == 1:
                            if len(cur) > 1: lines.append(cur)
                            cur = [(cx, cy)]
                        else: cur.append((cx, cy))
            if len(cur) > 1: lines.append(cur)
            for ln in lines:
                runs, run = [], []
                for a, b in zip(ln, ln[1:]):
                    k = _clip(a, b, ext)
                    if not k: continue
                    pa = (a[0] + (b[0] - a[0]) * k[0], a[1] + (b[1] - a[1]) * k[0]); pb = (a[0] + (b[0] - a[0]) * k[1], a[1] + (b[1] - a[1]) * k[1])
                    if run and abs(run[-1][0] - pa[0]) < 1e-9 and abs(run[-1][1] - pa[1]) < 1e-9: run.append(pb)
                    else:
                        if len(run) > 1: runs.append(run)
                        run = [pa, pb]
                if len(run) > 1: runs.append(run)
                for r in runs: out.append((name, props, [to_ll(px, py) for px, py in r]))
    return out


# ── 타일 받기 (캐시) ────────────────────────────────────────────────────
_lock = threading.Lock()

def _get(url: str, timeout: float = _TIMEOUT_S) -> bytes:
    req = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'PlaceOS-twin-roads/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data

@lru_cache(maxsize=1)
def _tile_template() -> str:
    return json.loads(_get(TILEJSON_URL))['tiles'][0]

@lru_cache(maxsize=512)
def fetch_tile(x: int, y: int, z: int = Z) -> bytes:
    with _lock: tpl = _tile_template()
    return _get(tpl.replace('{z}', str(z)).replace('{x}', str(x)).replace('{y}', str(y)))


# ── 반경 안 도로 ─────────────────────────────────────────────────────────
def _tile_of(lat: float, lng: float, z: int = Z) -> tuple[int, int]:
    n = 2 ** z
    return int((lng + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

def _simplify(pts, tol):
    if len(pts) < 3: return pts
    i, dm = 0, 0.0
    for k in range(1, len(pts) - 1):
        d = _seg_dist(pts[k], pts[0], pts[-1])
        if d > dm: i, dm = k, d
    if dm <= tol: return [pts[0], pts[-1]]
    return _simplify(pts[:i + 1], tol)[:-1] + _simplify(pts[i:], tol)

def roads_near(lat: float, lng: float, radius_m: float = 300, fetch: Fetch | None = None,
               width_overrides: dict | None = None) -> list[dict]:
    """(lat, lng) 반경 radius_m 안 도로 중심선. 선은 [[위도, 경도], …](소수 6자리, 0.3m 단순화).
    `fetch` 를 안 주면 모듈의 `fetch_tile` 을 부를 때 찾는다(테스트가 모듈 속성을 갈아끼울 수 있게)."""
    fetch = fetch or fetch_tile
    kx = M_PER_DEG * math.cos(math.radians(lat))
    to_m = lambda p: ((p[1] - lng) * kx, (p[0] - lat) * M_PER_DEG)
    to_ll = lambda q: [round(lat + q[1] / M_PER_DEG, 6), round(lng + q[0] / kx, 6)]
    dlat, dlng = radius_m / M_PER_DEG, radius_m / kx
    (x0, y0), (x1, y1) = _tile_of(lat + dlat, lng - dlng), _tile_of(lat - dlat, lng + dlng)
    tiles = [(tx, ty) for tx in range(x0, x1 + 1) for ty in range(y0, y1 + 1)]
    # 타일(보통 1~4장)을 동시에 받아 응답 지연을 줄입니다(호스팅 60초 제한 안에서 여유 있게).
    with ThreadPoolExecutor(max_workers=min(4, len(tiles))) as ex:
        blobs = list(ex.map(lambda t: fetch(t[0], t[1], Z), tiles))
    feats = [f for (tx, ty), blob in zip(tiles, blobs) for f in decode_lines(blob, tx, ty)]
    names = [((p.get('name:ko') or p.get('name')), p.get('class'), [to_m(q) for q in ll]) for layer, p, ll in feats if layer == 'transportation_name' and (p.get('name:ko') or p.get('name'))]
    W = {**WIDTH_OVERRIDES, **(width_overrides or {})}
    clip_box = radius_m * 1.3
    out = []
    for layer, p, ll in feats:
        if layer != 'transportation': continue
        cls, sub = p.get('class'), p.get('subclass')
        if cls == 'path' and sub == 'pedestrian': cls = 'pedestrian'
        if cls not in CLASS_WIDTH or p.get('brunnel') == 'tunnel': continue
        if cls == 'service' and p.get('service') in SKIP_SERVICE: continue
        pts = [to_m(q) for q in ll]
        if min(_seg_dist((0, 0), a, b) for a, b in zip(pts, pts[1:])) > radius_m: continue
        runs, cur = [], []
        for q in pts:
            if abs(q[0]) < clip_box and abs(q[1]) < clip_box: cur.append(q)
            else:
                if len(cur) > 1: runs.append(cur)
                cur = []
        if len(cur) > 1: runs.append(cur)

        def name_of(q):
            nm, best = None, 3.0
            for n, c2, l in names:
                if c2 != p.get('class'): continue
                for a, b in zip(l, l[1:]):
                    d = _seg_dist(q, a, b)
                    if d < best: best, nm = d, n
            return nm

        for run in runs:
            pieces, seg, cn = [], [run[0]], None
            for i, (a, b) in enumerate(zip(run, run[1:])):
                nm = name_of(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
                if i and nm != cn: pieces.append((cn, seg)); seg = [a]
                seg.append(b); cn = nm
            pieces.append((cn, seg))
            for nm, s in pieces:
                w, sw = W.get(nm, CLASS_WIDTH[cls])
                if p.get('oneway') == 1 and cls in ('trunk', 'primary', 'secondary', 'tertiary'): w, sw = round(w * .5 + 1), min(sw, 3)   # 상하행 분리 도로의 한쪽
                out.append({'n': nm or '', 'c': cls, 'w': w, 'sw': sw, 'ow': 1 if p.get('oneway') == 1 else 0, 'line': [to_ll(q) for q in _simplify(s, .3)]})
    return out


# ── 주소 도로 검사 ───────────────────────────────────────────────────────
_ROAD_RE = re.compile(r'([가-힣A-Za-z0-9]+(?:대로|로|길))\s*(?:지하\s*)?\d')

def road_name_of(road_addr: str | None) -> str | None:
    """'서울 성동구 연무장길 41' → '연무장길'. 못 찾으면 None."""
    m = _ROAD_RE.findall(road_addr or '')
    return m[-1] if m else None

def address_road_check(ring: list[list[float]], road_addr: str | None, roads: list[dict], max_gap_m: float = 12.0) -> dict:
    """도로명주소의 도로가 건물 바로 앞에 있는지: 건물 외곽선에서 그 도로 가장자리(중심선 − 폭/2)까지 거리.
    ring = [[위도, 경도], …] 건물 외곽선. 반환 {name, gap_m, ok, found}."""
    name = road_name_of(road_addr)
    if not name or len(ring) < 3: return {'name': name, 'gap_m': None, 'ok': False, 'found': False}
    lat0 = sum(p[0] for p in ring) / len(ring); lng0 = sum(p[1] for p in ring) / len(ring)
    kx = M_PER_DEG * math.cos(math.radians(lat0))
    to_m = lambda p: ((p[1] - lng0) * kx, (p[0] - lat0) * M_PER_DEG)
    poly = [to_m(p) for p in ring]
    edges = list(zip(poly, poly[1:] + poly[:1]))
    best = None
    for r in roads:
        if r['n'] != name: continue
        line = [to_m(p) for p in r['line']]
        for a, b in zip(line, line[1:]):
            n = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / 1.0))
            for k in range(n + 1):
                q = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                d = min(_seg_dist(q, e0, e1) for e0, e1 in edges) - r['w'] / 2
                if best is None or d < best: best = d
    if best is None: return {'name': name, 'gap_m': None, 'ok': False, 'found': False}
    gap = round(max(best, 0.0), 1)
    return {'name': name, 'gap_m': gap, 'ok': gap <= max_gap_m, 'found': True}


# ── 트윈 응답에 붙일 묶음 ────────────────────────────────────────────────
def roads_for_twin(lat: float, lng: float, ring: list[list[float]] | None = None, road_addr: str | None = None,
                   radius_m: float = 300, fetch: Fetch | None = None) -> dict:
    """`/buildings/{id}/twin` 응답에 그대로 합칠 값. 타일을 못 받아도 예외를 내지 않고 빈 도로와 사유를 돌려준다(트윈은 계속 보이게).
    반환 {roads, roads_source, road_check, roads_error}. 블로킹 네트워크 호출이라 라우터는 `run_in_threadpool` 로 부른다."""
    global _last_fail
    source = {**SOURCE, 'radius_m': radius_m}
    if fetch is None and time.monotonic() - _last_fail < _FAIL_BACKOFF_S:
        return {'roads': [], 'roads_source': source, 'road_check': None, 'roads_error': 'backoff'}
    err: Exception | None = None
    for attempt in (1, 2):   # 첫 실패는 한 번 더 — 받은 타일은 캐시에 남아 두 번째 시도는 빠진 것만 다시 받는다
        try:
            roads = roads_near(lat, lng, radius_m, fetch=fetch)
            break
        except Exception as e:   # 네트워크 · 타일 형식 오류 — 도로만 빼고 트윈은 그대로
            err = e
            log.warning("twin roads attempt %d failed at (%.5f, %.5f): %s: %s", attempt, lat, lng, type(e).__name__, e)
    else:
        if fetch is None:
            _last_fail = time.monotonic()
        return {'roads': [], 'roads_source': source, 'road_check': None, 'roads_error': type(err).__name__}
    check = address_road_check(ring, road_addr, roads) if ring else None
    return {'roads': roads, 'roads_source': source, 'road_check': check, 'roads_error': None}
