"""네이버 HUB 이관 헬퍼 · .env 값 해석(2026-11-08) — 네트워크 없음."""
from __future__ import annotations

import pytest

from data.collectors import naver_api
from data.run_collection import _env_value, _load_env


@pytest.fixture
def env(monkeypatch):
    for k in ("NAVER_HUB_CLIENT_ID", "NAVER_HUB_CLIENT_SECRET", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    naver_api._warned.clear()
    return monkeypatch


def test_hub_keys_use_hub_for_verified_paths(env):
    env.setenv("NAVER_HUB_CLIENT_ID", "hid")
    env.setenv("NAVER_HUB_CLIENT_SECRET", "hsec")
    url, headers, mode = naver_api.search_request("blog")
    assert mode == "hub" and url == "https://naverapihub.apigw.ntruss.com/search/v1/blog"
    assert headers == {"X-NCP-APIGW-API-KEY-ID": "hid", "X-NCP-APIGW-API-KEY": "hsec"}
    assert naver_api.search_request("cafearticle")[2] == "hub"


def test_unverified_hub_path_falls_back_to_legacy(env, capsys):
    env.setenv("NAVER_HUB_CLIENT_ID", "hid")
    env.setenv("NAVER_HUB_CLIENT_SECRET", "hsec")
    env.setenv("NAVER_CLIENT_ID", "lid")
    env.setenv("NAVER_CLIENT_SECRET", "lsec")
    url, headers, mode = naver_api.search_request("news")      # 11-08: HUB 앱에서 비활성(401)
    assert mode == "legacy" and url.startswith("https://openapi.naver.com/v1/search/news")
    assert headers == {"X-Naver-Client-Id": "lid", "X-Naver-Client-Secret": "lsec"}
    naver_api.search_request("news")
    assert capsys.readouterr().out.count("옛 방식") == 1, "같은 안내는 한 번만"


def test_legacy_only_and_no_keys(env):
    assert naver_api.search_request("blog") is None
    env.setenv("NAVER_CLIENT_ID", "lid")
    env.setenv("NAVER_CLIENT_SECRET", "lsec")
    assert naver_api.search_request("blog")[2] == "legacy"
    with pytest.raises(ValueError):
        naver_api.search_request("nope")


def test_datalab_stays_legacy_even_with_hub_keys(env):
    env.setenv("NAVER_HUB_CLIENT_ID", "hid")
    env.setenv("NAVER_HUB_CLIENT_SECRET", "hsec")
    assert naver_api.datalab_request() is None, "HUB 경로를 모르는 데이터랩을 HUB 로 부르면 안 된다"
    env.setenv("NAVER_CLIENT_ID", "lid")
    env.setenv("NAVER_CLIENT_SECRET", "lsec")
    url, headers, mode = naver_api.datalab_request()
    assert mode == "legacy" and url.endswith("/v1/datalab/search") and headers["Content-Type"] == "application/json"


@pytest.mark.parametrize("raw,want", [
    ("abc", "abc"),
    ("abc   # 메모", "abc"),                 # 값 뒤 주석 — 예전에는 「abc   # 메모」 전체가 값이었다
    ("   # 설명", ""),                       # .env.example 템플릿 줄 — 예전에는 KEY 가 「# 설명」이 됐다
    ('"a #b"', "a #b"),                     # 따옴표 값은 그대로
    ("'x' # c", "x"),
    ("a#b", "a#b"),                         # 공백 없는 # 는 값의 일부
])
def test_env_value(raw, want):
    assert _env_value(raw) == want


def test_load_env_skips_template_lines(tmp_path, monkeypatch):
    monkeypatch.delenv("PLACEOS_TEST_A", raising=False)
    monkeypatch.delenv("PLACEOS_TEST_B", raising=False)
    p = tmp_path / ".env"
    p.write_text("# 설명 줄\nPLACEOS_TEST_A=값A   # 메모\nPLACEOS_TEST_B=          # 템플릿 설명\n", encoding="utf-8")
    _load_env(p)
    import os
    assert os.environ["PLACEOS_TEST_A"] == "값A"
    assert "PLACEOS_TEST_B" not in os.environ
