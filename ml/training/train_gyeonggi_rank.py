"""경기 공개 상권 Gold 재학습과 기존 게이트 검증 후 승인된 로컬 반영."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    # 공개 상권 목록이 늘 때 새 버전의 학습 입력(`build_gyeonggi_ranking_gold --version`)으로 재학습한다(2026-11-23).
    parser.add_argument("--version", default="20261104")
    # 학습을 끝낸 후보(`candidate_dir`)가 있으면 다시 학습하지 않고 검증·반영만 한다 — 검증 코드를 고친 뒤 20분을 또 쓰지 않으려는 것이다.
    parser.add_argument("--reuse-candidate", action="store_true")
    args = parser.parse_args()
    import pandas as pd
    from ml.training import train_gnn as trainer
    from scripts.kpi_baseline import gnn_city_skill, gnn_vocab_check, SKILL, VOCAB_PASS

    root = Path(__file__).resolve().parents[2]
    gold = root / f"data/gold/gyeonggi_ranking_{args.version}"
    manifest = json.loads((gold / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["output_sha256"].items():
        assert hashlib.sha256((gold / name).read_bytes()).hexdigest() == expected, name
    nodes = pd.read_parquet(gold / "platform_store_graph_nodes.parquet")
    edges = pd.read_parquet(gold / "platform_store_graph_edges.parquet")
    hubs = set(manifest["hubs"])
    assert set(nodes.district_id.astype(str)) == hubs
    cities = {trainer._hub_cities()[hub] for hub in hubs}
    serving = root / "data/gold/platform_industry_recommend.json"
    original = serving.read_bytes()
    before = json.loads(original)
    candidate_dir = root / ("ml/artifacts/gyeonggi_candidate" if args.version == "20261104"
                            else f"ml/artifacts/gyeonggi_candidate_{args.version}")
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "recommend.json"
    reuse = args.reuse_candidate and candidate.exists() and (candidate_dir / "industry_gnn_gyeonggi.pt").exists()
    if not reuse:
        candidate.write_bytes(original)
        trainer.load_graph = lambda: (nodes.copy(), edges.copy())
        trainer._PAGE_BUILDING = gold / "page_building_features.parquet"
        trainer._ARTIFACT = candidate_dir / "industry_gnn.pt"
        trainer._RECOMMEND_JSON = candidate
        trainer.train(epochs=600, patience=80, save=True, use_demand=False,
                      use_building=True, resume=False, ckpt_every=0,
                      label_level="group_mapped", cities=cities,
                      serve_cities=cities, tag="gyeonggi")
    after = json.loads(candidate.read_text(encoding="utf-8"))
    entry = after["models"]["industry-gnn-gyeonggi"]
    skill = gnn_city_skill(after, model="industry-gnn-gyeonggi")
    vocab = gnn_vocab_check({"metrics": entry["metrics"], "districts": {
        hub: after["districts"][hub] for hub in hubs}})
    preserved = all(after["districts"][hub] == rows and
                    after["district_models"].get(hub) == before.get("district_models", {}).get(hub)
                    for hub, rows in before["districts"].items() if hub not in hubs)
    # 다른 모델은 그대로여야 한다 — 단 **이번에 교체하는 경기 모델 자신은 비교에서 뺀다**. 최초 학습(2026-11-04)에는 이 모델이 서빙 산출물에
    # 없었지만 공개 상권이 늘어 다시 학습하는 지금(2026-11-23)은 이미 있다 — 자기 자신과 같기를 요구하면 재학습이 영영 통과하지 못한다.
    preserved = preserved and after["metrics"] == before["metrics"] and all(
        after["models"][name] == value for name, value in before.get("models", {}).items()
        if name != "industry-gnn-gyeonggi")
    covered = set(entry["district_means"]) == hubs and set(entry["districts"]) == hubs
    passed = skill.get("verdict") == SKILL and vocab["verdict"] == VOCAB_PASS and preserved and covered
    report = {"skill": skill, "vocabulary": vocab, "other_models_preserved": preserved,
              "all_public_hubs_covered": covered, "passed": passed, "applied": False,
              "metrics": entry["metrics"],
              "training": {"epochs": 600, "patience": 80, "use_demand": False,
                           "use_building": True, "label_level": "group_mapped"},
              "gold_manifest_sha256": hashlib.sha256((gold / "manifest.json").read_bytes()).hexdigest()}
    if passed and args.apply:
        assert serving.read_bytes() == original, "학습 중 서빙 산출물이 변경되어 반영 중단"
        temp = serving.with_suffix(".candidate.json")
        temp.write_bytes(candidate.read_bytes())
        temp.replace(serving)
        shutil.copy2(candidate_dir / "industry_gnn_gyeonggi.pt", root / "ml/artifacts/industry_gnn_gyeonggi.pt")
        report["applied"] = True
    path = root / ("reports/gyeonggi_model_validation_2026-11-04.json" if args.version == "20261104"
                   else f"reports/gyeonggi_model_validation_{args.version}.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit("기존 실력·어휘 게이트 미통과: 서빙 변경 없음")


if __name__ == "__main__":
    main()
