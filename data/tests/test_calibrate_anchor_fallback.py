"""calibrate_vacancy — R-ONE 값이 없으면 라벨이 R-ONE 이라고 말하지 않는다 (2026-10-31)."""
from data.pipelines import calibrate_vacancy as cv


def test_anchor_label_and_flag_follow_the_data(monkeypatch):
    monkeypatch.setattr(cv, "_rone_latest", lambda kind: {"has-value": 18.2} if kind == "vac_mid" else {})
    assert cv.anchor_of("has-value") == 18.2
    assert cv.anchor_of("no-value") == cv.ANCHOR_FALLBACK
