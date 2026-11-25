"""층 배치도 사진 — 건물주가 올린 실제 배치도가 Page 의 개략 배치도를 대신한다 (2026-11-22).

잠그는 것: ① 공개 조건은 매물과 같다(게시 중 + 소유자 확인) ② 올릴 때 위치·기기 정보(EXIF·XMP·주석)를 뗀다 — 클라이언트를 믿지 않는다
③ 형식·크기·총량 상한 ④ 본인만 올리고 지운다 ⑤ 매물을 지우면 사진도 지워진다 ⑥ 표가 없는 DB 에서도 매물 기능은 선다.
아래 바이트·주소·이름은 테스트 전용 합성값이다(일부러 만든 최소 JPEG/PNG).
"""
from __future__ import annotations

import base64
import zlib

from sqlalchemy import func, select

from app.models.direct import DirectFloorPlan
from app.services import direct_floor_plans as fp
from tests.conftest import DIRECT_REGISTRY

SECRET = b"GPS-LAT-37.5665-LNG-126.9780"


def _jpeg(width: int = 800, height: int = 600, pad: int = 150) -> bytes:
    """EXIF(APP1) · IPTC(APP13) · 주석(COM)을 일부러 넣은 최소 JPEG."""
    seg = lambda marker, body: bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2, "big") + body  # noqa: E731
    app0 = seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    app1 = seg(0xE1, b"Exif\x00\x00" + SECRET)
    app13 = seg(0xED, b"Photoshop 3.0\x00" + SECRET)
    com = seg(0xFE, b"secret-comment")
    sof = seg(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
    sos = seg(0xDA, b"\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00")
    return b"\xff\xd8" + app0 + app1 + app13 + com + sof + sos + b"\x12\x34\x56" * pad + b"\xff\xd9"


def _png(width: int = 640, height: int = 480) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", b"Comment\x00" + SECRET)
            + chunk(b"eXIf", SECRET) + chunk(b"IDAT", zlib.compress(b"\x00" * 64)) + chunk(b"IEND", b""))


def _seg(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2, "big") + body


def _chunk(kind: bytes, body: bytes, crc: int | None = None) -> bytes:
    return len(body).to_bytes(4, "big") + kind + body + (zlib.crc32(kind + body) if crc is None else crc).to_bytes(4, "big")


def _sof(width: int = 400, height: int = 300) -> bytes:
    return _seg(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")


_SOS = _seg(0xDA, b"\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00")
_SCAN = b"\x12\x34\xff\x00\x56\xff\xd0\x78" * 20                    # 채움(FF00)·재시작(RST0)이 섞인 엔트로피 데이터


def _body(raw: bytes, mime: str = "image/jpeg") -> dict:
    return {"mime": mime, "data": base64.b64encode(raw).decode()}


def _put(env, owner, lid, raw: bytes, mime: str = "image/jpeg"):
    return env.client.put(f"{env.base}/listings/{lid}/floor-plan", headers=owner, json=_body(raw, mime))


def _stored(env, lid) -> DirectFloorPlan:
    with env.session() as db:
        return db.execute(select(DirectFloorPlan).where(DirectFloorPlan.listing_id == lid)).scalars().one()


def test_upload_strips_location_and_device_metadata_and_reads_the_size(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    r = _put(env, owner, lid, _jpeg(800, 600))
    assert r.status_code == 200, r.text
    meta = r.json()
    assert (meta["width"], meta["height"]) == (800, 600)
    assert meta["url"].startswith(f"/api/v1/direct/listings/{lid}/floor-plan?v=")
    assert "확인하지 않아요" in meta["notice"]                       # 사진이 실제와 같다고 보증하지 않는다
    stored = _stored(env, lid)
    assert SECRET not in stored.data and b"secret-comment" not in stored.data and b"Exif" not in stored.data
    assert stored.data.startswith(b"\xff\xd8") and stored.data.endswith(b"\xff\xd9")
    assert b"\x12\x34\x56" * 150 in stored.data                       # 화소 데이터는 그대로다
    assert stored.size_bytes == len(stored.data)


def test_png_metadata_is_stripped_too(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    assert _put(env, owner, lid, _png(640, 480), "image/png").status_code == 200
    stored = _stored(env, lid)
    assert SECRET not in stored.data and b"tEXt" not in stored.data and b"eXIf" not in stored.data
    assert stored.data.startswith(b"\x89PNG") and stored.data.endswith(b"IEND\xaeB`\x82")
    assert (stored.width, stored.height) == (640, 480)


def test_visible_only_when_the_listing_is_public(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    # 소유자 확인 전: 본인만 본다
    lid = env.client.post(f"{env.base}/listings", headers=owner, json=env.listing_body()).json()["id"]
    assert _put(env, owner, lid, _jpeg()).status_code == 200
    url = f"{env.base}/listings/{lid}/floor-plan"
    assert env.client.get(url).status_code == 404                                       # 익명
    mine = env.client.get(url, headers=owner)
    assert mine.status_code == 200 and mine.headers["content-type"] == "image/jpeg"
    assert env.client.get(url, headers=env.signup("other@example.com")).status_code == 404   # 다른 사람
    assert env.client.get(f"{env.base}/me/listings", headers=owner).json()["items"][0]["floor_plan"]["width"] == 800

    # 확인·게시 뒤: 누구나 본다 — 목록·상세에 floor_plan 이 실린다
    env.client.post(f"{env.base}/listings/{lid}/submit", headers=owner,
                    json={"relation": "owner", "registry_number": DIRECT_REGISTRY, "owner_name": "홍길동"})
    vid = env.client.get("/api/v1/admin/direct/verifications", headers=env.admin).json()["items"][0]["id"]
    env.client.post(f"/api/v1/admin/direct/verifications/{vid}", headers=env.admin, json={"decision": "verified"})
    public = env.client.get(url)
    assert public.status_code == 200 and public.headers["content-type"] == "image/jpeg"
    assert public.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in public.headers["content-security-policy"]
    # 공유 캐시(CDN)에 두지 않는다 — 신고로 숨기거나 지운 사진이 캐시에서 계속 나가지 않게(2026-11-22 리뷰 반영)
    assert public.headers["cache-control"].startswith("private") and "public" not in public.headers["cache-control"]
    listed = env.client.get(f"{env.base}/listings", params={"district_id": "garosugil"}).json()["items"][0]
    assert listed["floor_plan"]["url"].startswith(f"/api/v1/direct/listings/{lid}/floor-plan")
    assert env.client.get(f"{env.base}/listings/{lid}").json()["floor_plan"]["height"] == 600
    # 숨기면 사진도 사라진다
    env.client.post(f"{env.base}/listings/{lid}/status", headers=owner, json={"action": "pause"})
    assert env.client.get(url).status_code == 404


def test_replace_changes_the_cache_key_and_delete_removes_it(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    first = _put(env, owner, lid, _jpeg(800, 600)).json()
    second = _put(env, owner, lid, _png(900, 700), "image/png").json()
    assert second["url"] != first["url"] and (second["width"], second["height"]) == (900, 700)
    with env.session() as db:
        assert db.execute(select(func.count()).select_from(DirectFloorPlan)).scalar() == 1   # 한 매물에 한 장
    assert env.client.delete(f"{env.base}/listings/{lid}/floor-plan", headers=owner).status_code == 204
    assert env.client.get(f"{env.base}/listings/{lid}/floor-plan").status_code == 404
    assert env.client.get(f"{env.base}/listings/{lid}").json()["floor_plan"] is None


def test_only_the_owner_can_upload_or_delete(direct_env):
    env = direct_env
    owner, other = env.signup("owner@example.com"), env.signup("other@example.com")
    lid = env.publish(owner)
    assert _put(env, other, lid, _jpeg()).status_code == 404
    assert env.client.put(f"{env.base}/listings/{lid}/floor-plan", json=_body(_jpeg())).status_code in (401, 403)
    _put(env, owner, lid, _jpeg())
    assert env.client.delete(f"{env.base}/listings/{lid}/floor-plan", headers=other).status_code == 404
    assert env.client.get(f"{env.base}/listings/{lid}/floor-plan").status_code == 200


def test_rejects_wrong_kind_size_and_broken_data(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    assert _put(env, owner, lid, _png(), "image/jpeg").status_code == 422            # mime 이 아니라 바이트로 본다
    assert _put(env, owner, lid, _jpeg(), "image/png").status_code == 422
    assert _put(env, owner, lid, _jpeg(50, 50)).status_code == 422                    # 너무 작다
    assert _put(env, owner, lid, _jpeg(9000, 600)).status_code == 422                 # 너무 크다
    assert _put(env, owner, lid, b"\xff\xd8\xff\xe0\x00").status_code == 422          # 깨진 JPEG
    assert _put(env, owner, lid, b"not an image at all" * 20).status_code == 422
    bad64 = env.client.put(f"{env.base}/listings/{lid}/floor-plan", headers=owner,
                           json={"mime": "image/jpeg", "data": "!!!" * 60})
    assert bad64.status_code == 422
    gif = env.client.put(f"{env.base}/listings/{lid}/floor-plan", headers=owner, json={"mime": "image/gif", "data": "A" * 200})
    assert gif.status_code == 422                                                     # 스키마가 막는다
    big = _put(env, owner, lid, _jpeg(pad=fp.MAX_BYTES // 3 + 10_000))               # 떼고 나서도 한 장 상한을 넘는다
    assert big.status_code == 413
    with env.session() as db:
        assert db.execute(select(func.count()).select_from(DirectFloorPlan)).scalar() == 0   # 거절된 것은 남지 않는다


def test_owner_total_is_capped(direct_env, monkeypatch):
    env = direct_env
    monkeypatch.setattr(fp, "MAX_OWNER_TOTAL", 2_000)
    owner = env.signup("owner@example.com")
    a, b = env.publish(owner), env.publish(owner, address="서울 강남구 신사동 000-1")
    assert _put(env, owner, a, _jpeg(pad=100)).status_code == 200
    assert _put(env, owner, b, _jpeg(pad=1500)).status_code == 413
    assert _put(env, owner, a, _jpeg(pad=100)).status_code == 200                     # 같은 매물을 바꿔 올리는 것은 총량에서 뺀다


def test_deleting_the_listing_deletes_the_photo(direct_env):
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    _put(env, owner, lid, _jpeg())
    assert env.client.delete(f"{env.base}/listings/{lid}", headers=owner).status_code == 204
    with env.session() as db:
        assert db.execute(select(func.count()).select_from(DirectFloorPlan)).scalar() == 0


def test_listings_still_work_when_the_table_is_missing(direct_env):
    """배포(자동)와 마이그레이션(수동) 사이 — 배치도 표가 없어도 매물 기능은 서고 사진 칸만 준비 중이다."""
    env = direct_env
    owner = env.signup("owner@example.com")
    lid = env.publish(owner)
    with env.session() as db:
        DirectFloorPlan.__table__.drop(bind=db.connection())
        db.commit()
    listed = env.client.get(f"{env.base}/listings", params={"district_id": "garosugil"})
    assert listed.status_code == 200 and listed.json()["items"][0]["floor_plan"] is None
    assert env.client.get(f"{env.base}/me/listings", headers=owner).status_code == 200
    assert _put(env, owner, lid, _jpeg()).status_code == 503
    assert env.client.get(f"{env.base}/listings/{lid}/floor-plan").status_code == 404
    assert env.client.delete(f"{env.base}/listings/{lid}", headers=owner).status_code == 204   # 삭제·탈퇴도 깨지지 않는다


# ── 메타데이터 떼기 — 허용 목록(2026-11-22 리뷰 반영) ─────────────────────────────

def test_jpeg_metadata_after_the_scan_or_after_eoi_is_dropped():
    """거부 목록일 때 새던 길: 스캔 뒤(점진 JPEG 의 스캔 사이) EXIF · EOI 뒤 덧붙은 자료 · APP2(MPF) · APP3."""
    raw = (b"\xff\xd8" + _seg(0xE3, b"Meta\x00" + SECRET) + _seg(0xE2, b"MPF\x00" + SECRET) + _sof() + _SOS + _SCAN
           + _seg(0xE1, b"Exif\x00\x00" + SECRET) + _SOS + _SCAN + b"\xff\xd9" + b"TRAILER" + _seg(0xE1, SECRET))
    clean, width, height = fp.sanitize(raw, "image/jpeg")
    assert SECRET not in clean and b"TRAILER" not in clean and b"MPF" not in clean and b"Meta" not in clean
    assert clean.endswith(b"\xff\xd9") and clean.count(b"\xff\xd9") == 1          # EOI 에서 끝난다
    assert clean.count(_SCAN) == 2 and (width, height) == (400, 300)               # 화소(두 스캔)는 그대로


def test_jpeg_keeps_only_jfif_and_adobe_app_segments():
    raw = (b"\xff\xd8" + _seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + _seg(0xE0, b"OTHER" + SECRET)
           + _seg(0xEE, b"Adobe\x00\x64\x00\x00\x00\x00\x01") + _seg(0xE2, b"ICC_PROFILE\x00" + SECRET)
           + _seg(0xFE, SECRET) + _sof() + _SOS + _SCAN + b"\xff\xd9")
    clean, _, _ = fp.sanitize(raw, "image/jpeg")
    assert b"JFIF" in clean and b"Adobe" in clean and SECRET not in clean and b"OTHER" not in clean


def test_jpeg_without_frame_scan_or_end_is_rejected():
    import pytest

    from app.services.direct_listings import DirectError
    for raw in (b"\xff\xd8" + _SOS + _SCAN + b"\xff\xd9",              # 프레임(SOF) 없음
                b"\xff\xd8" + _sof() + b"\xff\xd9",                     # 스캔 없음
                b"\xff\xd8" + _sof() + _SOS + _SCAN,                    # EOI 없음
                b"\xff\xd8" + _sof() + b"\xff\xd0" + _SOS + _SCAN + b"\xff\xd9"):   # 스캔 밖 RST
        with pytest.raises(DirectError):
            fp.sanitize(raw, "image/jpeg")


def test_png_keeps_only_allowed_chunks_and_checks_crc_and_structure():
    import pytest

    from app.services.direct_listings import DirectError
    ihdr = _chunk(b"IHDR", (640).to_bytes(4, "big") + (480).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
    idat, iend = _chunk(b"IDAT", zlib.compress(b"\x00" * 64)), _chunk(b"IEND", b"")
    sig = b"\x89PNG\r\n\x1a\n"
    clean, width, height = fp.sanitize(sig + ihdr + _chunk(b"zxIf", SECRET) + _chunk(b"prVt", SECRET) + _chunk(b"iCCP", SECRET)
                                       + idat + iend + b"TRAILER", "image/png")
    assert SECRET not in clean and b"TRAILER" not in clean and clean.endswith(iend) and (width, height) == (640, 480)
    for raw in (sig + ihdr + _chunk(b"IDAT", b"x", crc=1) + iend,       # CRC 가 틀림
                sig + ihdr + iend,                                      # IDAT 없음
                sig + _chunk(b"tEXt", b"a") + ihdr + idat + iend,       # IHDR 가 첫 청크가 아님
                sig + ihdr + idat):                                     # IEND 없음
        with pytest.raises(DirectError):
            fp.sanitize(raw, "image/png")


def test_huge_pixel_count_is_rejected_even_when_the_file_is_small():
    import pytest

    from app.services.direct_listings import DirectError
    ihdr = _chunk(b"IHDR", (4096).to_bytes(4, "big") + (4097).to_bytes(4, "big") + b"\x08\x00\x00\x00\x00")
    tiny = b"\x89PNG\r\n\x1a\n" + ihdr + _chunk(b"IDAT", zlib.compress(b"\x00" * 1000)) + _chunk(b"IEND", b"")
    assert len(tiny) < 2000
    with pytest.raises(DirectError):
        fp.sanitize(tiny, "image/png")                                  # 4096×4097 — 펼치면 브라우저가 멎는 크기
    assert fp.sanitize(b"\xff\xd8" + _sof(4096, 4096) + _SOS + _SCAN + b"\xff\xd9", "image/jpeg")[1:] == (4096, 4096)
