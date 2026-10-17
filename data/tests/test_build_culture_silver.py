"""전시·공연 Silver — 합성 행으로 좌표 스왑·분류·중복·결손 중단·거점 귀속을 고정한다."""
import json
from types import SimpleNamespace

import pytest

from data.pipelines import build_culture_silver as m

HUBS = {"a": SimpleNamespace(cx=127.0000, cy=37.5000, stores_radius_m=700),
        "b": SimpleNamespace(cx=127.0050, cy=37.5000, stores_radius_m=700)}


def row(name, addr, subj="공연장", x="37.5000", y="127.0000", **kw):
    return {"FAC_NAME": name, "ADDR": addr, "SUBJCODE": subj, "X_COORD": x, "Y_COORD": y,
            "GNGU": "중구", "PHNE": "010-0000-0000", "HOMEPAGE": "http://x", **kw}


def test_x_is_latitude_y_is_longitude():
    assert m.parse_coords(row("가", "나")) == (37.5, 127.0)
    # 스왑된(경도, 위도 순) 값은 서울 범위 밖이라 걸러진다
    assert m.parse_coords(row("가", "나", x="127.0", y="37.5"))[0] is None


def test_polluted_coordinate_becomes_null_not_dropped():
    out, stats = m.normalize([row("한국미술관", "주소", x="37.5718961547884~2")], "2026-10-17", HUBS)
    assert len(out) == 1 and out[0]["lat"] is None and out[0]["coord_issue"] == "coord_unparseable"
    assert out[0]["hub_slug"] is None and stats["coord_issue"] == 1


def test_industry_is_exact_match_only():
    rows = [row("A", "1", "공연장"), row("B", "2", "문화예술회관"), row("C", "3", "미술관/갤러리"),
            row("D", "4", "도서관"), row("E", "5", "기타"), row("F", "6", "공연장 ")]
    out, _ = m.normalize(rows, "d", HUBS)
    assert [f["industry"] for f in out] == ["culture", "culture", "culture", None, None, "culture"]


def test_same_address_different_facility_not_merged_but_true_duplicate_is():
    rows = [row("세종문화회관", "세종로 175"), row("세종문화회관 미술관", "세종로 175", "미술관/갤러리"),
            row("살롱 쿤스트", "서교동 1", "미술관/갤러리"), row("살롱쿤스트", "서교동 1", "미술관/갤러리")]
    out, stats = m.normalize(rows, "d", HUBS)
    assert [f["name"] for f in out] == ["세종문화회관", "세종문화회관 미술관", "살롱 쿤스트"]
    assert out[2]["dup_count"] == 2 and stats["duplicates_merged"] == 1


def test_same_key_far_apart_is_not_merged():
    rows = [row("롯데뮤지엄", "x", x="37.5000"), row("롯데뮤지엄", "x", x="37.5100")]
    out, _ = m.normalize(rows, "d", HUBS)
    assert len(out) == 2


def test_missing_key_fields_stop_promotion():
    with pytest.raises(ValueError, match="결손"):
        m.normalize([row("", "주소")], "d", HUBS)


def test_nearest_hub_wins_and_outside_radius_is_null():
    # a 중심에서 ~170m, b 중심에서 ~290m 지점 → a
    assert m.assign_hub(37.5, 127.0020, HUBS)[0] == "a"
    assert m.assign_hub(37.5, 127.0030, HUBS)[0] == "b"
    assert m.assign_hub(37.6, 127.0, HUBS) == (None, None)


def test_contact_fields_are_not_carried_to_silver():
    out, _ = m.normalize([row("A", "1")], "d", HUBS)
    assert "PHNE" not in out[0] and "HOMEPAGE" not in out[0]


def test_build_refuses_manifest_mismatch(tmp_path):
    run = tmp_path / "2026-10-17"
    run.mkdir()
    (run / "culturalSpaceInfo.json").write_text(json.dumps([row("A", "1")]), encoding="utf-8")
    (run / "culturalSpaceInfo.manifest.json").write_text(json.dumps(
        {"rows": 2, "list_total_count": 2, "collected_at": "x", "service": "s", "dataset_id": "d",
         "rows_sha256": "h"}), encoding="utf-8")
    with pytest.raises(ValueError, match="매니페스트"):
        m.build(tmp_path, tmp_path / "s", tmp_path / "g")
