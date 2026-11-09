"""건물에너지(가스) 월별 실시간 조회(services/building_energy_live) — 2026-11-09. 네트워크 없이."""
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services import building_energy_live as E

client = TestClient(app)
PNU = "1114012500100660009"

XML_OK = """<?xml version="1.0" encoding="UTF-8"?><response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
<body><items><item><useYm>202604</useYm><useQty>1200.5</useQty><sigunguCd>11140</sigunguCd></item>
<item><useYm>202604</useYm><useQty>99.5</useQty><sigunguCd>11140</sigunguCd></item></items><totalCount>2</totalCount></body></response>""".encode()
XML_KEY = b"<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"


def test_parse_xml_json_and_errors():
    rows, total = E.parse(XML_OK)
    assert total == 2 and rows[0]["useYm"] == "202604" and rows[0]["useQty"] == "1200.5"
    rows, _ = E.parse(b'{"response":{"header":{"resultCode":"00"},"body":{"items":{"item":{"useYm":"202605","useQty":"3"}},"totalCount":1}}}')
    assert rows == [{"useYm": "202605", "useQty": "3"}]
    for bad in (XML_KEY, b"<response><header><resultCode>22</resultCode><resultMsg>LIMITED</resultMsg></header></response>"):
        try:
            E.parse(bad)
            raise AssertionError("expected EnergyError")
        except E.EnergyError:
            pass
    assert E.parse(b"<response><header><resultCode>03</resultCode></header><body><items/></body></response>")[0] == []


def test_summarise_sums_the_lot_by_month_and_keeps_fields():
    s = E.summarise([{"useYm": "202604", "useQty": "1,200.5"}, {"useYm": "202604", "useQty": "99.5"},
                     {"useYm": "202603", "useQty": "0"}, {"useYm": "", "useQty": "5"}])
    assert s["months"] == [{"ym": "202603", "qty": 0.0, "n": 1}, {"ym": "202604", "qty": 1300.0, "n": 2}]
    assert s["unit"] is None and s["fields"] == ["useQty", "useYm"]


def test_jibun_and_months():
    assert E.jibun_of(PNU) == {"sigunguCd": "11140", "bjdongCd": "12500", "bun": "0066", "ji": "0009"}
    assert E.jibun_of("1114012500200660009") is None and E.jibun_of("x") is None     # 산 지번 · 형식 아님
    assert E.months_back(date(2026, 1, 15), 3) == ["202512", "202511", "202510"]


def test_monthly_fallback_and_window(monkeypatch):
    monkeypatch.setattr(E.settings, "data_go_kr_service_key", "dummy", raising=False)
    calls = []

    def fake(op, params, key, base=None):
        calls.append(params.get("useYm"))
        if "useYm" not in params:
            return [{"useYm": "202605", "useQty": "1"}]          # 한 달만 → 한 달씩으로 넘어간다
        return [{"useYm": params["useYm"], "useQty": "10"}] if params["useYm"] in ("202605", "202604") else []
    monkeypatch.setattr(E, "_get", fake)
    out = E.energy(PNU, "gas", today=date(2026, 11, 9))
    assert out["status"] == "ok" and out["query"] == "monthly" and len(calls) == 1 + E.MONTHS
    assert [m["ym"] for m in out["months"]] == ["202604", "202605"] and out["window"] == ["202505", "202610"]


def test_refused_is_soft_and_names_the_apply_page(monkeypatch):
    monkeypatch.setattr(E.settings, "data_go_kr_service_key", "dummy", raising=False)

    def refuse(op, params, key, base=None):
        raise E.EnergyError("SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    monkeypatch.setattr(E, "_get", refuse)
    out = E.energy(PNU, "gas")
    assert out["status"] == "refused" and "NOT_REGISTERED" in out["error"] and out["apply_url"].endswith("15135963/openapi.do")
    assert E.energy(PNU, "gas")["status"] == "backoff"


def test_http_401_403_is_refused_with_the_code(monkeypatch):
    assert E.http_reason(403, b"Forbidden") == "HTTP 403 Forbidden"
    assert E.http_reason(401, b"<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></OpenAPI_ServiceResponse>") \
        == "HTTP 401 SERVICE_KEY_IS_NOT_REGISTERED_ERROR"
    monkeypatch.setattr(E.settings, "data_go_kr_service_key", "dummy", raising=False)
    calls = []

    def forbid(op, params, key, base=None):
        calls.append(1)
        raise E.EnergyError("HTTP 403 Forbidden")
    monkeypatch.setattr(E, "_get", forbid)
    out = E.energy(PNU, "gas")
    # 주소마다 한 번씩만(한 달씩 18콜로 번지지 않는다) · 어느 주소가 무엇이라 했는지 남긴다
    assert out["status"] == "refused" and len(calls) == len(E.ENDPOINTS)
    assert out["error"].startswith("건축HUB: HTTP 403 Forbidden") and "구 건물에너지정보 서비스: HTTP 403 Forbidden" in out["error"]


def test_falls_through_to_the_endpoint_that_accepts_the_key(monkeypatch):
    monkeypatch.setattr(E.settings, "data_go_kr_service_key", "dummy", raising=False)
    seen = []

    def by_base(op, params, key, base=None):
        seen.append(base)
        if "1611000" not in base:
            raise E.EnergyError("HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
        return [{"useYm": "202604", "useQty": "10"}, {"useYm": "202605", "useQty": "12"}]
    monkeypatch.setattr(E, "_get", by_base)
    out = E.energy(PNU, "gas")
    assert out["status"] == "ok" and out["endpoint"] == "구 건물에너지정보 서비스" and out["query"] == "all"
    assert [m["ym"] for m in out["months"]] == ["202604", "202605"]
    assert len(seen) == 3 and "1613000" in seen[0]


def test_route():
    body = client.get(f"/api/v1/buildings/{PNU}-1/energy").json()
    assert body["kind"] == "gas" and body["status"] in ("no_key", "error", "backoff")
    assert client.get(f"/api/v1/buildings/{PNU}-1/energy", params={"kind": "water"}).status_code == 422
