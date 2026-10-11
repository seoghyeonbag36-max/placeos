"""수집 승격은 원본 해시가 깨지거나 Bronze 경로를 벗어나면 실패한다."""
import hashlib
import json
import pytest
from data.pipelines import promote_collected_context as pipeline


def test_promotion_rejects_changed_raw_response(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "BRONZE", tmp_path)
    raw = tmp_path / "raw.json"
    raw.write_bytes(b"original")
    (tmp_path / "manifest.json").write_text(json.dumps({"entries": [{"path": "raw.json",
        "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}]}), encoding="utf-8")
    raw.write_bytes(b"changed")
    with pytest.raises(ValueError, match="해시"):
        pipeline.verify(tmp_path)


def test_promotion_rejects_manifest_path_escape(monkeypatch, tmp_path):
    root = tmp_path / "bronze"
    root.mkdir()
    monkeypatch.setattr(pipeline, "BRONZE", root)
    (root / "manifest.json").write_text(json.dumps({"entries": [{"path": "../outside.json", "sha256": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="경로 이탈"):
        pipeline.verify(root)
