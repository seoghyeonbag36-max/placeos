"""실제 해시의 재사용·변경 감지·재시작 보존을 검사한다."""
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from data.validation.verified_file_cache import VerifiedFileCache


def test_verified_cache_survives_restart_and_invalidates_changed_file(tmp_path):
    path=tmp_path/'raw.bin';path.write_bytes(b'original')
    database=tmp_path/'cache.sqlite3'
    with VerifiedFileCache(database) as cache:
        assert cache.fingerprint(path)==hashlib.sha256(b'original').hexdigest()
    with VerifiedFileCache(database) as cache:
        assert cache.fingerprint(path)==hashlib.sha256(b'original').hexdigest()
        path.write_bytes(b'changed-value')
        assert cache.fingerprint(path)==hashlib.sha256(b'changed-value').hexdigest()
        path.unlink()
        with pytest.raises(FileNotFoundError):cache.fingerprint(path)


def test_parallel_checks_record_only_actual_hashes(tmp_path):
    paths=[]
    for i in range(20):
        p=tmp_path/str(i);p.write_bytes(str(i).encode());paths.append(p)
    with VerifiedFileCache(tmp_path/'cache.sqlite3') as cache:
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes=list(pool.map(cache.fingerprint,paths))
        assert hashes==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
