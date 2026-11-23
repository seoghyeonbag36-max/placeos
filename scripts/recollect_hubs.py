"""반경·`partition_with` 가 바뀐 거점을 다시 받는다 — 점포·폴리곤은 새 범위로 강제 재수집하고, 대장(건축HUB)은 **새로 생긴 건물만** 이어 받고, Gold·앵커를 다시 세운다.

왜 필요한가: 수집기는 이미 받은 것을 건너뛰므로(`stores_raw.json 이미 존재 — 건너뜀`) 레지스트리의 반경을 키워도 산출물은 옛 범위 그대로다.
`run_hub_chain_batch` 의 `stage_done` 도 산출물(anchor)만 봐서 「완료」로 친다. 그래서 ① 점포·폴리곤만 `--force` 로 새 범위에 맞춰 다시 받고
② 실패 표식(`redo_from = stores`)을 남겨 배치가 대장 단계부터 다시 밀게 한다 — 대장은 받은 건물을 건너뛰어 쿼터는 새 건물분만 쓴다.

    python scripts/recollect_hubs.py ilsan westerndom madu juyeop madu-east        # 키가 이 트리에 없으면 run_with_env_root.py 로 감싼다

⚠ 건축HUB 쿼터는 한 번에 한 거점 — 다른 수집기와 동시에 돌리지 않는다. 쿼터가 끝나면 배치가 `quota_day` 를 남기고 멈춘다(다음 날 같은 명령).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(mod: list[str]) -> int:
    r = subprocess.run([sys.executable, "-u", "-m", *mod], cwd=ROOT)
    return r.returncode


def main(argv: list[str]) -> int:
    slugs = [a for a in argv if not a.startswith("-")]
    if not slugs:
        raise SystemExit("사용법: recollect_hubs.py <slug> [<slug> ...]")
    from data.config.page_hubs import ALL_HUBS
    import scripts.run_hub_chain_batch as batch

    unknown = [s for s in slugs if s not in ALL_HUBS]
    if unknown:
        raise SystemExit(f"미등록 거점: {' '.join(unknown)}")
    for s in slugs:
        h = ALL_HUBS[s]
        print(f"■ {s} — 반경 {h.radius_m}/{h.stores_radius_m}m · 짝 {', '.join(h.partition_with) or '없음'}", flush=True)
        # 점포·폴리곤은 새 범위로 다시 받는다(상가정보 · V-World — 건축HUB 쿼터와 별개)
        if run(["data.collectors.vworld_bldg", s, "--force"]) != 0 or \
                run(["data.collectors.building_vacancy", s, "--no-ledger", "--force"]) != 0:
            raise SystemExit(f"{s}: 점포·폴리곤 재수집 실패 — 중단(표식을 남기지 않았다)")
        # 대장부터 다시 밀도록 표식을 남긴다 — stage_done 이 산출물보다 앞선 단계(stores)를 돌려준다
        marker = batch._marker(s)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"step": "반경 변경 재수집", "redo_from": "stores", "attempts": 1,
                                      "at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False),
                          encoding="utf-8")
    # 대장 이어받기 · 층별개요 · Gold · 앵커 — 표식이 있는 거점만 대장 단계부터 민다
    return run(["scripts.run_hub_chain_batch", "--hubs", ",".join(slugs)])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
