"""불변 원본의 실제 SHA-256 검증 결과를 재시작 사이에 보존한다. 데이터 값은 만들지 않는다."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path


class VerifiedFileCache:
    """파일 크기·수정·변경 시각이 달라지면 반드시 다시 해시한다. Gold 값의 캐시가 아니다."""

    def __init__(self, database: Path):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database, check_same_thread=False, timeout=30, isolation_level=None)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=NORMAL')
        self.connection.execute('PRAGMA busy_timeout=30000')
        self.connection.execute('CREATE TABLE IF NOT EXISTS verified_files '
            '(path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER, ctime INTEGER, sha256 TEXT)')
        self.connection.commit()
        self.lock = threading.Lock()
        self.pending = 0

    def fingerprint(self, path: Path) -> str:
        before = path.stat()
        signature = (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        key = str(path.absolute())
        with self.lock:
            found = self.connection.execute(
                'SELECT size,mtime,ctime,sha256 FROM verified_files WHERE path=?', (key,)).fetchone()
            if found and tuple(found[:3]) == signature:
                return str(found[3])
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        after = path.stat()
        if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != signature:
            raise OSError('FILE_CHANGED_DURING_HASH')
        with self.lock:
            self.connection.execute('INSERT OR REPLACE INTO verified_files VALUES (?,?,?,?,?)',
                                    (key, *signature, checksum))
            self.pending += 1
            if self.pending >= 128:
                self.connection.commit()
                self.pending = 0
        return checksum

    def checkpoint(self) -> None:
        with self.lock:
            self.connection.commit()
            self.pending = 0

    def close(self) -> None:
        self.checkpoint()
        self.connection.close()

    def __enter__(self) -> VerifiedFileCache:
        return self

    def __exit__(self, *_args) -> None:
        self.close()
