"""[Platform] 서울시 문화공간 정보 수집기 — 전시·공연 업종 시설 마스터의 Bronze 원천.

서울 열린데이터광장 「서울시 문화공간 정보」(OA-15487, 서비스 `culturalSpaceInfo`)를 전량(약 1,100행,
2콜) 받아 **원응답 그대로** Bronze 에 쌓는다. 가공·유형 분류·거점 귀속은 Silver 이후의 몫이다.

이용허락: 공공누리 1유형(출처표시 · 상업적 이용 및 변경 가능), 갱신주기 수시 — 2026-10-17 상세 페이지 확인.
⇒ 화면·문서에 쓸 때 출처를 「서울 열린데이터광장 · 서울시 문화공간 정보」로 표시한다.

원천 특성(docs/finding-exhibit-performance-sources-2026-10-16.md §2-A):
- 시설 고유 ID 가 없다(`NUM` 은 순번). 키는 Silver 에서 만든다.
- ⚠ `X_COORD` 가 위도, `Y_COORD` 가 경도다(이름과 반대). 이 수집기는 **바꾸지 않고** 그대로 둔다.
- 갱신일·기준일 필드가 없다 → 수집일을 매니페스트에 남긴다.

Bronze 는 append-only 다: 같은 수집일 파일이 이미 있으면 덮어쓰지 않고 멈춘다.
실행: python -m data.collectors.seoul_culture_space
"""
from __future__ import annotations

import hashlib
import json
import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import bronze_dir, load_env, save_json, today

SERVICE = "culturalSpaceInfo"
SLUG = "culture"                 # Bronze 폴더: data/bronze/culture/{수집일}/
RAW_NAME = f"{SERVICE}.json"
MANIFEST_NAME = f"{SERVICE}.manifest.json"
DATASET_ID = "OA-15487"
LICENSE = "공공누리 1유형(출처표시, 상업적 이용 및 변경 가능)"
ATTRIBUTION = "서울 열린데이터광장 · 서울시 문화공간 정보"
_PAGE = 1000
_MAX_PAGES = 10                  # 폭주 방지: 1만 행을 넘으면 원천이 바뀐 것이다


def _url(start: int, end: int, key: str = "{KEY}") -> str:
    return f"http://openapi.seoul.go.kr:8088/{key}/json/{SERVICE}/{start}/{end}/"


def fetch_all(key: str) -> tuple[list[dict], int, int]:
    """전량 페이징. (행, 서버가 말한 list_total_count, 호출 수). 오류 응답·건수 불일치는 예외."""
    rows: list[dict] = []
    total = 0
    calls = 0
    start = 1
    while calls < _MAX_PAGES:
        resp = requests.get(_url(start, start + _PAGE - 1, key), timeout=30)
        resp.raise_for_status()
        body = resp.json()
        calls += 1
        if SERVICE not in body:
            msg = body.get("RESULT", {}).get("MESSAGE", str(body)[:200])
            raise RuntimeError(f"{SERVICE}: {msg}")
        payload = body[SERVICE]
        rows.extend(payload.get("row", []))
        total = int(payload.get("list_total_count", 0))
        start += _PAGE
        if start > total:
            break
    if len(rows) != total:
        raise RuntimeError(f"{SERVICE}: 받은 행 {len(rows)} != list_total_count {total} — 저장하지 않는다")
    return rows, total, calls


def build_manifest(rows: list[dict], total: int, calls: int, collected_at: str) -> dict:
    """요청 URL(키 제외)·호출 수·건수·응답 해시. 해시는 행을 정렬 키로 직렬화해 순서에 흔들리지 않는다."""
    digest = hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "service": SERVICE,
        "dataset_id": DATASET_ID,
        "request_url_template": _url(1, _PAGE),
        "calls": calls,
        "list_total_count": total,
        "rows": len(rows),
        "rows_sha256": digest,
        "collected_at": collected_at,
        "source_ref_date": None,          # 원천이 기준일을 주지 않는다
        "license": LICENSE,
        "attribution": ATTRIBUTION,
    }


def collect() -> dict | None:
    load_env()
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[seoul_culture_space] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return None

    day = today()
    folder = bronze_dir(SLUG, day)
    if (folder / RAW_NAME).exists() or (folder / MANIFEST_NAME).exists():
        raise FileExistsError(f"{folder} 에 오늘 수집분이 이미 있다 — Bronze 는 덮어쓰지 않는다")

    rows, total, calls = fetch_all(key)
    manifest = build_manifest(rows, total, calls, day)
    save_json(rows, SLUG, RAW_NAME, day)
    save_json(manifest, SLUG, MANIFEST_NAME, day)
    return manifest


def main() -> None:
    manifest = collect()
    if manifest:
        print(f"[seoul_culture_space] {manifest['rows']}행 · {manifest['calls']}콜 · {manifest['rows_sha256'][:12]}")


if __name__ == "__main__":
    main()
