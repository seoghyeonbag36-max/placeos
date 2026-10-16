"""'의견 보내기'(방문자 의견)를 운영 서버에서 받아 CSV·엑셀(.xlsx)로 저장한다.

python scripts/export_visitor_feedback.py                 # exports/visitor_feedback/visitor_feedback.{csv,xlsx}
python scripts/export_visitor_feedback.py --no-xlsx       # CSV 만

.xlsx 는 openpyxl 이 있어야 만든다(`pip install openpyxl` — 서버 requirements 에는 넣지 않는다).

토큰: 환경변수 ADMIN_TOKEN, 없으면 secrets/admin_token.txt 한 줄(gitignore). 인자로는 받지
않는다 — 셸 기록에 남는다. 서버는 `GET /api/v1/visitor-feedback`(X-Admin-Token) 이다.

⚠ 연락처가 들어 있다. 저장소가 공개라 `exports/` 는 gitignore 이며, 파일을 커밋·공유하지 않는다.
⚠ 매 실행이 서버의 **거울**이다(덮어쓴다). 운영자가 삭제 요청을 받아 서버에서 지운 의견이
  로컬 사본에 남지 않게 하려는 것이다(방문자 의견 삭제 = 연락처 삭제).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://placeos.web.app"
DEFAULT_OUT = ROOT / "exports" / "visitor_feedback" / "visitor_feedback.csv"
TOKEN_FILE = ROOT / "secrets" / "admin_token.txt"
PAGE = 100  # 서버 상한(le=100)

CATEGORY = {"review": "후기", "bug": "오류 제보", "suggestion": "제안"}
STATUS = {"received": "접수", "reviewing": "검토 중", "completed": "처리 완료"}
NOTIFY = {"sent": "발송", "failed": "실패", "disabled": "미설정", "pending": "대기"}
HEADER = ["접수일시(KST)", "유형", "내용", "페이지", "연락처", "처리상태", "메일알림", "ID"]


def read_token() -> str:
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if not token and TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        sys.exit("ADMIN_TOKEN 이 없다: 환경변수로 주거나 secrets/admin_token.txt 에 한 줄로 적는다.")
    return token


def fetch_all(base: str, token: str) -> list[dict]:
    rows: list[dict] = []
    with httpx.Client(timeout=30, headers={"X-Admin-Token": token}) as client:
        offset = 0
        while True:
            r = client.get(f"{base}/api/v1/visitor-feedback", params={"limit": PAGE, "offset": offset})
            if r.status_code == 403:
                sys.exit("403: 토큰이 틀렸거나 서버에 ADMIN_TOKEN 이 없다.")
            if r.status_code == 429:
                sys.exit(f"429: 토큰 시도 제한. {r.headers.get('Retry-After', '?')}초 뒤 다시.")
            r.raise_for_status()
            page = r.json()
            rows += page
            if len(page) < PAGE:
                return rows
            offset += PAGE


def kst(iso: str) -> str:
    """서버는 UTC 로 준다. 엑셀에서 바로 정렬되도록 KST 문자열로 낸다."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:  # 서버 DateTime(timezone=True) 이지만 SQLite 는 tz 를 떼고 준다
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")


def to_line(r: dict) -> list[str]:
    return [
        kst(r["created_at"]),
        CATEGORY.get(r["category"], r["category"]),
        r["message"],
        r["page"],
        r.get("contact") or "",
        STATUS.get(r["status"], r["status"]),
        NOTIFY.get(r["notification_status"], r["notification_status"]),
        r["id"],
    ]


def guard_cell(v: str) -> str:
    """엑셀 수식 주입 방지 — 방문자 입력이 = + - @ 로 시작하면 수식으로 실행된다."""
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def write_csv(path: Path, lines: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: BOM 이 있어야 엑셀이 한글을 깨지 않고 연다.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows([[guard_cell(c) for c in line] for line in lines])


def write_xlsx(path: Path, lines: list[list[str]]) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment
    except ImportError:
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "방문자 의견"
    ws.append(HEADER)
    for line in lines:
        ws.append([guard_cell(c) for c in line])
    for col, width in zip("ABCDEFGH", (20, 10, 60, 24, 24, 10, 10, 34)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):  # 긴 의견이 한 줄로 잘리지 않게 줄바꿈
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"API 주소 (기본 {DEFAULT_BASE})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="CSV 경로")
    ap.add_argument("--no-xlsx", action="store_true", help=".xlsx 는 만들지 않는다(CSV 만)")
    args = ap.parse_args()

    rows = fetch_all(args.base.rstrip("/"), read_token())
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    lines = [to_line(r) for r in rows]
    write_csv(args.out, lines)
    print(f"{len(lines)}건 → {args.out}")
    if not args.no_xlsx:
        xlsx = args.out.with_suffix(".xlsx")
        print(f"{len(lines)}건 → {xlsx}" if write_xlsx(xlsx, lines) else "openpyxl 이 없어 xlsx 는 건너뜀 (pip install openpyxl)")


if __name__ == "__main__":
    main()
