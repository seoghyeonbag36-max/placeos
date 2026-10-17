"""culturalSpaceInfo 수집기 — 네트워크 없이 합성 응답으로 페이징·무결성·덮어쓰기 금지를 검증한다."""
import pytest

from data.collectors import seoul_culture_space as mod


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def _fake_get(total, page=mod._PAGE, drop=0):
    """total 행짜리 서비스. drop>0 이면 마지막 페이지에서 행을 덜 준다(건수 불일치 재현)."""
    def get(url, timeout):
        start = int(url.rstrip("/").split("/")[-2])
        end = min(start + page - 1, total)
        rows = [{"NUM": str(i), "FAC_NAME": f"시설{i}"} for i in range(start, end + 1)]
        if drop and end == total:
            rows = rows[:-drop]
        return _Resp({mod.SERVICE: {"list_total_count": total, "row": rows}})
    return get


def test_fetch_all_pages_until_total(monkeypatch):
    monkeypatch.setattr(mod, "requests", type("R", (), {"get": staticmethod(_fake_get(2150))}))
    rows, total, calls = mod.fetch_all("KEY")
    assert (len(rows), total, calls) == (2150, 2150, 3)
    assert rows[0]["NUM"] == "1" and rows[-1]["NUM"] == "2150"


def test_fetch_all_refuses_short_response(monkeypatch):
    monkeypatch.setattr(mod, "requests", type("R", (), {"get": staticmethod(_fake_get(1096, drop=3))}))
    with pytest.raises(RuntimeError, match="list_total_count"):
        mod.fetch_all("KEY")


def test_error_response_raises(monkeypatch):
    err = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    monkeypatch.setattr(mod, "requests", type("R", (), {"get": staticmethod(lambda url, timeout: _Resp(err))}))
    with pytest.raises(RuntimeError, match="해당하는 데이터"):
        mod.fetch_all("KEY")


def test_manifest_has_no_key_and_hash_ignores_row_key_order():
    a = [{"NUM": "1", "FAC_NAME": "가"}]
    b = [{"FAC_NAME": "가", "NUM": "1"}]
    ma = mod.build_manifest(a, 1, 1, "2026-10-17")
    assert ma["rows_sha256"] == mod.build_manifest(b, 1, 1, "2026-10-17")["rows_sha256"]
    assert "{KEY}" in ma["request_url_template"]
    assert ma["source_ref_date"] is None and "공공누리 1유형" in ma["license"]


def test_collect_does_not_overwrite_same_day_bronze(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "load_env", lambda: None)
    monkeypatch.setenv("SEOUL_OPENAPI_KEY", "KEY")
    monkeypatch.setattr(mod, "requests", type("R", (), {"get": staticmethod(_fake_get(5))}))
    monkeypatch.setattr(mod, "bronze_dir", lambda slug, day=None: tmp_path)
    monkeypatch.setattr(mod, "save_json", lambda obj, slug, name, day=None: (tmp_path / name).write_text("x"))
    first = mod.collect()
    assert first["rows"] == 5 and (tmp_path / mod.RAW_NAME).exists()
    with pytest.raises(FileExistsError):
        mod.collect()
