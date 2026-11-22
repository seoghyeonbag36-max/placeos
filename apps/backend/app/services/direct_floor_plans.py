"""층 배치도 사진 — 건물주가 매물(층)마다 올리는 실제 배치도 한 장 (2026-11-22).

Page 의 개략(가상) 배치도는 공공데이터로 그린 모양이라 실제 벽·기둥·출입구와 다르다. 건물주가 이 층의 실제 배치도 사진을
올리면 그 층에서는 사진이 개략 배치도 **대신** 보인다(공개 조건은 매물과 같다 — 게시 중 + 소유자 확인 verified · L3).

- 사진은 DB 에 바이트로 둔다(Cloud Run 은 디스크가 없고 버킷을 새로 들이지 않는다). 한 장 1.5MB · 한 사람 30MB · JPEG/PNG 만.
- 올릴 때 서버가 **촬영 위치·기기 정보(EXIF·XMP·ICC·주석·덧붙은 자료)를 뗀다.** Pillow 가 없어 JPEG/PNG 조각을 직접 읽고,
  **남길 조각만 적은 허용 목록**으로 옮긴다(EOI·IEND 뒤는 버린다) — 화소는 건드리지 않는다.
  클라이언트가 먼저 줄이고 다시 그려 보내지만(lib/floorPlanImage.ts) 서버는 그것을 믿지 않는다.
- ⛔ 사진은 건물주 **본인이** 올린다. PlaceOS 가 그려 넣거나 고쳐 주지 않는다. 사진에 있는 것이 사실이라는 보증도 아니다 —
  화면은 「건물주가 올린 배치도 · 확인되지 않은 자료」로 밝힌다.
- 배치도 표(`direct_floor_plans`)는 b8c9d0e1f2a3 다음 리비전(c9d0e1f2a3b4)이다. 표가 없는 DB 에서도 매물 기능은 그대로 서고,
  배치도 칸만 「준비 중」(503)이다.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from app.models.direct import DirectFloorPlan, DirectListing
from app.services.direct_listings import DirectError, _now, aware, get_owned

ALLOWED_MIMES = ("image/jpeg", "image/png")
MAX_BYTES = 1_500_000            # 한 장(떼고 난 뒤 바이트)
MAX_OWNER_TOTAL = 30_000_000     # 한 사람이 올린 사진 전체
MIN_SIDE, MAX_SIDE = 100, 4096   # 변마다 이 안 — 브라우저는 1600px 로 줄여 보낸다(lib/floorPlanImage)
MAX_PIXELS = MAX_SIDE * MAX_SIDE  # 작게 압축된 거대 해상도(펼치면 수백 MB)를 막는다 — 보는 사람의 브라우저가 멎지 않게
NOT_READY = "배치도 사진 기능을 준비하고 있어요(데이터베이스 표가 아직 없습니다)."
NOTICE = ("건물주가 직접 올린 배치도 사진이에요. PlaceOS 는 사진이 실제와 같은지 확인하지 않아요 — "
          "현장에서 도면과 대조해 주세요.")

# ── 메타데이터 떼기 — **남길 것만 적는다**(허용 목록). 모르는 조각은 버린다(2026-11-22 리뷰 반영: 거부 목록은 APP3·MPF·
#    스캔 뒤 EXIF·EOI 뒤 덧붙은 자료를 놓쳤다). 화소(엔트로피 부호 · IDAT)는 그대로 옮긴다.
_JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
_JPEG_KEEP = {0xC4, 0xCC, 0xDB, 0xDD} | _JPEG_SOF          # DHT · DAC · DQT · DRI · SOFn
_JPEG_KEEP_APP = {0xE0: b"JFIF\x00", 0xEE: b"Adobe"}       # APP0 JFIF · APP14 Adobe(색 변환) — 나머지 APPn(EXIF·XMP·ICC·MPF…) · 주석은 버린다
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_KEEP = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"sBIT", b"pHYs"}


def table_ready(db: Session) -> bool:
    return inspect(db.connection()).has_table(DirectFloorPlan.__tablename__)


def _bad(message: str, status: int = 422) -> DirectError:
    return DirectError(status, message)


def _broken(kind: str) -> DirectError:
    return _bad(f"{kind} 사진이 깨져 있어요")


def _strip_jpeg(raw: bytes) -> tuple[bytes, int, int]:
    """허용한 조각만 옮기고 EOI 에서 끝낸다 — EOI 뒤(트레일러·덧붙은 사진·숨긴 자료)는 버린다."""
    if not raw.startswith(b"\xff\xd8\xff"):
        raise _bad("JPEG 사진이 아니에요")
    out = bytearray(b"\xff\xd8")
    n, i = len(raw), 2
    width = height = 0
    seen_sos = False
    while True:
        if i >= n or raw[i] != 0xFF:
            raise _broken("JPEG")                     # EOI 없이 끝났거나 마커 자리에 다른 바이트
        while i < n and raw[i] == 0xFF:               # 채움 바이트
            i += 1
        if i >= n:
            raise _broken("JPEG")
        marker = raw[i]
        i += 1
        if marker == 0xD9:                            # EOI
            if not (width and height and seen_sos):
                raise _broken("JPEG")
            out += b"\xff\xd9"
            return bytes(out), width, height
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # 길이 없는 마커가 스캔 밖에 — 정상 사진에는 없다
            raise _broken("JPEG")
        if i + 2 > n:
            raise _broken("JPEG")
        length = int.from_bytes(raw[i:i + 2], "big")
        end = i + length
        if length < 2 or end > n:
            raise _broken("JPEG")
        body = raw[i + 2:end]
        segment = bytes((0xFF, marker)) + raw[i:end]
        i = end
        if marker == 0xDA:                            # SOS — 머리를 옮기고, 엔트로피 데이터는 다음 마커 **직전까지만**
            out += segment
            seen_sos = True
            j = i
            while j < n:
                if raw[j] == 0xFF and j + 1 < n and (raw[j + 1] == 0x00 or 0xD0 <= raw[j + 1] <= 0xD7):
                    j += 2                            # 채움(FF00) · 재시작 마커(RSTn)는 데이터의 일부
                    continue
                if raw[j] == 0xFF:
                    break                             # 진짜 마커 — 다음 스캔(점진 JPEG)·표·EOI
                j += 1
            out += raw[i:j]
            i = j
            continue
        if marker in _JPEG_SOF:
            if length < 8:
                raise _broken("JPEG")
            height = int.from_bytes(body[1:3], "big")
            width = int.from_bytes(body[3:5], "big")
            out += segment
        elif marker in _JPEG_KEEP:
            out += segment
        elif marker in _JPEG_KEEP_APP and body.startswith(_JPEG_KEEP_APP[marker]):
            out += segment
        # 그 밖(APP1~15 의 EXIF·XMP·ICC·MPF·제조사 자료 · 주석 · 모르는 마커)은 버린다


def _strip_png(raw: bytes) -> tuple[bytes, int, int]:
    """허용한 청크만 옮긴다 — 첫 청크는 IHDR · IDAT 가 하나 이상 · CRC 가 맞아야 한다 · IEND 뒤는 버린다."""
    import zlib

    if not raw.startswith(_PNG_SIG):
        raise _bad("PNG 사진이 아니에요")
    out = bytearray(_PNG_SIG)
    n, i = len(raw), len(_PNG_SIG)
    width = height = 0
    first, seen_idat = True, False
    while i + 12 <= n:
        length = int.from_bytes(raw[i:i + 4], "big")
        kind = raw[i + 4:i + 8]
        end = i + 12 + length
        if end > n:
            raise _broken("PNG")
        if zlib.crc32(raw[i + 4:i + 8 + length]) != int.from_bytes(raw[i + 8 + length:end], "big"):
            raise _broken("PNG")                      # 손상·조작된 청크
        if first:
            if kind != b"IHDR" or length != 13:
                raise _broken("PNG")
            width = int.from_bytes(raw[i + 8:i + 12], "big")
            height = int.from_bytes(raw[i + 12:i + 16], "big")
            first = False
        seen_idat = seen_idat or kind == b"IDAT"
        if kind in _PNG_KEEP:
            out += raw[i:end]
        i = end
        if kind == b"IEND":
            if not seen_idat:
                raise _broken("PNG")
            return bytes(out), width, height
    raise _broken("PNG")


def sanitize(raw: bytes, mime: str) -> tuple[bytes, int, int]:
    """형식을 바이트로 확인하고(확장자·mime 을 믿지 않는다) 위치·기기 정보를 뗀 사진과 가로·세로를 돌려준다."""
    if mime not in ALLOWED_MIMES:
        raise _bad("JPEG 또는 PNG 사진만 올릴 수 있어요")
    clean, width, height = _strip_jpeg(raw) if mime == "image/jpeg" else _strip_png(raw)
    if min(width, height) < MIN_SIDE or max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
        raise _bad(f"사진 크기는 변마다 {MIN_SIDE}~{MAX_SIDE}px 안이어야 해요")
    if len(clean) > MAX_BYTES:
        raise DirectError(413, f"사진이 너무 커요(한 장 {MAX_BYTES // 1_000_000}.{MAX_BYTES % 1_000_000 // 100_000}MB 까지)")
    return clean, width, height


def _owner_total(db: Session, user_id: str, *, excluding: str | None = None) -> int:
    q = (select(func.coalesce(func.sum(DirectFloorPlan.size_bytes), 0))
         .join(DirectListing, DirectListing.id == DirectFloorPlan.listing_id)
         .where(DirectListing.owner_user_id == user_id))
    if excluding:
        q = q.where(DirectFloorPlan.listing_id != excluding)
    return int(db.execute(q).scalar() or 0)


def save(db: Session, user_id: str, listing_id: str, mime: str, data_b64: str) -> dict[str, Any]:
    """내 매물에 배치도 사진을 올리거나 바꾼다(한 매물에 한 장)."""
    if not table_ready(db):
        raise DirectError(503, NOT_READY)
    listing = get_owned(db, user_id, listing_id)
    if listing.status in ("hidden", "closed"):
        raise DirectError(409, "숨김·종료된 매물에는 사진을 올릴 수 없어요")
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _bad("사진 데이터를 읽지 못했어요") from exc
    if len(raw) > MAX_BYTES * 2:                      # 떼기 전 상한 — 떼고 나서 MAX_BYTES 를 다시 본다
        raise DirectError(413, "사진이 너무 커요")
    clean, width, height = sanitize(raw, mime)
    if _owner_total(db, user_id, excluding=listing.id) + len(clean) > MAX_OWNER_TOTAL:
        raise DirectError(413, f"올린 사진이 너무 많아요(한 사람 {MAX_OWNER_TOTAL // 1_000_000}MB 까지) — 안 쓰는 사진을 지워 주세요")
    now = _now()
    row = db.execute(select(DirectFloorPlan).where(DirectFloorPlan.listing_id == listing.id)).scalars().first()
    if row is None:
        row = DirectFloorPlan(listing_id=listing.id, created_at=now)
        db.add(row)
    row.mime, row.width, row.height, row.size_bytes, row.data, row.updated_at = mime, width, height, len(clean), clean, now
    db.commit()
    db.refresh(row)
    return describe(row)


def remove(db: Session, user_id: str, listing_id: str) -> None:
    if not table_ready(db):
        raise DirectError(503, NOT_READY)
    listing = get_owned(db, user_id, listing_id)
    db.execute(sa_delete(DirectFloorPlan).where(DirectFloorPlan.listing_id == listing.id))
    db.commit()


def remove_for_listings(db: Session, listing_ids: list[str]) -> None:
    """매물 삭제·탈퇴에서 부른다 — 표가 아직 없는 DB 에서도 깨지지 않게 존재를 본다."""
    if listing_ids and table_ready(db):
        db.execute(sa_delete(DirectFloorPlan).where(DirectFloorPlan.listing_id.in_(listing_ids)))


def get_image(db: Session, listing_id: str) -> DirectFloorPlan | None:
    if not table_ready(db):
        return None
    return db.execute(select(DirectFloorPlan).where(DirectFloorPlan.listing_id == listing_id)).scalars().first()


def _meta(listing_id: str, width: int, height: int, size_bytes: int, updated_at: Any) -> dict[str, Any]:
    """화면에 싣는 메타 — 바이트는 싣지 않는다. url 의 v 는 바꿔 올렸을 때 브라우저 캐시를 깨는 값이다."""
    updated = aware(updated_at)
    return {
        "url": f"/api/v1/direct/listings/{listing_id}/floor-plan?v={int(updated.timestamp() * 1000) if updated else 0}",
        "width": width, "height": height, "size_bytes": size_bytes,
        "updated_at": updated.isoformat() if updated else None,
        "notice": NOTICE,
    }


def describe(row: DirectFloorPlan) -> dict[str, Any]:
    return _meta(row.listing_id, row.width, row.height, row.size_bytes, row.updated_at)


def attach(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """목록·상세 dict 마다 `floor_plan`(없으면 None)을 단다. 표가 없으면 모두 None — 매물 기능은 그대로 선다."""
    for item in items:
        item["floor_plan"] = None
    ids = [it["id"] for it in items if it.get("id")]
    if not ids or not table_ready(db):
        return items
    rows = db.execute(select(DirectFloorPlan.listing_id, DirectFloorPlan.width, DirectFloorPlan.height,
                             DirectFloorPlan.size_bytes, DirectFloorPlan.updated_at)
                      .where(DirectFloorPlan.listing_id.in_(ids))).all()
    by_id = {r.listing_id: r for r in rows}
    for item in items:
        r = by_id.get(item.get("id"))
        if r is not None:
            item["floor_plan"] = _meta(r.listing_id, r.width, r.height, r.size_bytes, r.updated_at)
    return items
