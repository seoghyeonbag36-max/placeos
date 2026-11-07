"""3D 트윈 실제 도로(services/twin_roads) — 네트워크 없이 tests/fixtures/twin_roads 의 실제 타일 2장으로 돈다.

타일: OpenFreeMap z14 (13974, 6345) · (13974, 6346) — 성수동. © OpenStreetMap 기여자 (ODbL).
시험 좌표: A 37.54234, 127.055999(앞 도로 연무장길) · B 37.5469, 127.058114(성수이로).
"""
import math
import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services import twin_roads as T

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, 'fixtures', 'twin_roads')
def fetch(x, y, z):
    p = os.path.join(FIX, f'{z}_{x}_{y}.pbf.gz')
    if not os.path.exists(p): raise FileNotFoundError(p)
    with open(p, 'rb') as f: return f.read()

# 시안(Case 2)의 A · B 건물: 중심 · 정면 방위 · 가로 · 깊이 → 외곽선
SITES = {'A': (37.54234, 127.055999, 199, 16, 12, '서울 성동구 연무장길 41', '연무장길'),
         'B': (37.5469, 127.058114, 282, 48, 26, '서울 성동구 성수이로 113', '성수이로')}
def ring_of(lat, lng, face, W, D):
    r = math.radians(face); bx, bz = r - math.pi / 2, r; kx = 111320 * math.cos(math.radians(lat))
    pts = []
    for x, z in ((-W / 2, -D / 2), (W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2)):
        e = x * math.sin(bx) + z * math.sin(bz); n = x * math.cos(bx) + z * math.cos(bz)
        pts.append([lat + n / 111320, lng + e / kx])
    return pts

class DecodeTest(unittest.TestCase):
    def test_lines_inside_tile(self):
        lines = T.decode_lines(fetch(13974, 6345, 14), 13974, 6345)
        self.assertGreater(sum(1 for l, *_ in lines if l == 'transportation'), 500)
        self.assertTrue(any(p.get('name:ko') == '성수이로' for l, p, _ in lines if l == 'transportation_name'))
        n = 2 ** 14; lo0, lo1 = 13974 / n * 360 - 180, 13975 / n * 360 - 180
        for _, _, c in lines:
            for la, lo in c: self.assertTrue(lo0 - 1e-9 <= lo <= lo1 + 1e-9)   # 경계 여백을 잘라 냄

class RoadsNearTest(unittest.TestCase):
    def test_counts_and_names(self):
        for k, (lat, lng, face, W, D, addr, road) in SITES.items():
            rs = T.roads_near(lat, lng, 300, fetch=fetch)
            self.assertEqual(len(rs), 42, k)                          # 시안 Case 2와 같은 구간 수
            self.assertIn(road, {r['n'] for r in rs})
            for r in rs:
                self.assertGreaterEqual(len(r['line']), 2); self.assertGreater(r['w'], r['sw'] * 2 - 1e-9)
    def test_widths(self):
        rs = T.roads_near(*SITES['B'][:2], 300, fetch=fetch)
        self.assertEqual({r['w'] for r in rs if r['n'] == '성수이로'}, {25})
        self.assertTrue(all(r['w'] == 16 for r in rs if r['n'] == '광나루로'))   # 상하행 분리 도로의 한쪽

class AddressRoadTest(unittest.TestCase):
    def test_road_name(self):
        self.assertEqual(T.road_name_of('서울특별시 성동구 연무장길 41'), '연무장길')
        self.assertEqual(T.road_name_of('성동구 성수이로7길 12-3'), '성수이로7길')
        self.assertEqual(T.road_name_of('서울 강남구 테헤란로 지하 101'), '테헤란로')
        self.assertIsNone(T.road_name_of('성동구 성수동2가 289-5'))
    def test_front_road(self):
        for k, (lat, lng, face, W, D, addr, road) in SITES.items():
            rs = T.roads_near(lat, lng, 300, fetch=fetch)
            c = T.address_road_check(ring_of(lat, lng, face, W, D), addr, rs)
            self.assertTrue(c['ok'], (k, c)); self.assertLessEqual(c['gap_m'], 1.0, (k, c))   # 정면이 도로 가장자리에서 0.5m
    def test_wrong_road(self):
        lat, lng, face, W, D, *_ = SITES['A']
        rs = T.roads_near(lat, lng, 300, fetch=fetch)
        c = T.address_road_check(ring_of(lat, lng, face, W, D), '서울 성동구 상원길 10', rs)
        self.assertFalse(c['ok']); self.assertFalse(c['found'])
        far = T.address_road_check(ring_of(lat + .0008, lng, face, W, D), '서울 성동구 연무장길 41', rs)   # 북쪽으로 약 90m 옮긴 건물
        self.assertFalse(far['ok']); self.assertGreater(far['gap_m'], 12)

class TwinBundleTest(unittest.TestCase):
    def test_bundle(self):
        lat, lng, face, W, D, addr, _ = SITES['A']
        b = T.roads_for_twin(lat, lng, ring_of(lat, lng, face, W, D), addr, fetch=fetch)
        self.assertEqual(len(b['roads']), 42); self.assertTrue(b['road_check']['ok']); self.assertEqual(b['roads_source']['license'], 'ODbL')
    def test_network_failure_is_soft(self):
        def boom(x, y, z): raise OSError('offline')
        b = T.roads_for_twin(37.54, 127.05, fetch=boom)
        self.assertEqual(b['roads'], []); self.assertEqual(b['roads_error'], 'OSError')



# ── 트윈 응답에 합쳐지는가 (라우터 · 스키마) ──────────────────────────────────
API = "/api/v1"
client = TestClient(app)


def _first_building_id() -> str:
    from app.services import floor_vacancy
    return floor_vacancy.load("garosugil")["units"][0]["building_id"]


def test_twin_response_carries_roads(monkeypatch):
    """실제 타일로 만든 묶음이 응답 스키마를 그대로 통과하고 출처가 남는다."""
    lat, lng, face, W, D, addr, _ = SITES['A']
    bundle = T.roads_for_twin(lat, lng, ring_of(lat, lng, face, W, D), addr, fetch=fetch)
    seen = {}

    def fake(lat_, lng_, ring, road_addr):
        seen.update(lat=lat_, ring=ring, road_addr=road_addr)
        return bundle
    monkeypatch.setattr(T, "roads_for_twin", fake)
    body = client.get(f"{API}/buildings/{_first_building_id()}/twin", params={"district": "garosugil"}).json()
    assert len(body["roads"]) == 42 and body["roads_error"] is None
    assert body["roads_source"]["by"] == "© OpenStreetMap 기여자" and body["roads_source"]["license"] == "ODbL"
    assert body["road_check"] == bundle["road_check"]
    assert seen["lat"] == body["lat"] and seen["ring"] == body["ring"] and seen["road_addr"] == body["road_addr"]


def test_twin_survives_tile_outage():
    """타일 서버가 죽어도(conftest 가 막아 둔 상태) 트윈은 200 이고 도로만 빈다."""
    r = client.get(f"{API}/buildings/{_first_building_id()}/twin", params={"district": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["roads"] == [] and body["roads_error"] and body["road_check"] is None
    assert body["floors"] and body["ring"]


def test_backoff_after_failure(monkeypatch):
    """실패 직후에는 타일 서버를 다시 치지 않는다."""
    calls = []

    def boom(x, y, z):
        calls.append((x, y))
        raise OSError("offline")
    monkeypatch.setattr(T, "fetch_tile", boom)
    first = T.roads_for_twin(37.54, 127.05)
    second = T.roads_for_twin(37.54, 127.05)
    assert first["roads_error"] == "OSError" and second["roads_error"] == "backoff"
    assert len(calls) >= 1 and all(c in calls[:4] for c in calls)
