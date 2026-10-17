"""공개 업종 Bronze를 Silver로 정규화한다. 결손 키와 충돌은 승격을 중단한다."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

from data.collectors.acquire_industry_public import LICENSES
from data.config.page_hubs import ACTIVE_HUBS

ROOT = Path(__file__).resolve().parents[2]


def validate_match_text(fields: dict, name_field: str, address_field: str) -> None:
    """손실 디코딩된 연결 키는 추정 복원하지 않고 승격을 중단한다."""
    for field in (name_field, address_field):
        if '\ufffd' in str(fields.get(field) or ''):
            raise ValueError(f'corrupted_match_text: {field}')


class DiskRows:
    """원본 전체를 메모리에 올리지 않도록 임시 JSONL에 보관한다."""

    def __init__(self, folder: Path) -> None:
        handle = tempfile.NamedTemporaryFile(dir=folder, suffix='.jsonl', delete=False)
        self.path = Path(handle.name)
        handle.close()
        self.count = 0

    def extend(self, rows: list[dict]) -> None:
        with self.path.open('a', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                self.count += 1

    def __iter__(self):
        with self.path.open(encoding='utf-8') as stream:
            for line in stream:
                yield json.loads(line)

    def __len__(self) -> int:
        return self.count


def write_rows(stream: Any, rows: Any) -> None:
    """배열을 순차 기록해 메모리 사용량을 제한한다."""
    stream.write('[')
    for index, row in enumerate(rows):
        if index:
            stream.write(',')
        stream.write(json.dumps(row, ensure_ascii=False))
    stream.write(']')


def clean(value: Any) -> Any:
    """공백 문자열은 null로 정리하고 실제 0은 보존한다."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def normalize(rows: list[dict], keys: tuple[str, ...], source: str,
              source_path: str, sha256: str, collected_on: str,
              as_of: date | None = None, *, allow_corrupted_text: bool = False,
              preserve_observations: bool = False) -> list[dict]:
    """식별키 결손과 동일 키의 상충 관측은 실패한다. 테스트 원천은 합성이다."""
    found: dict[tuple, dict] = {}
    observations = []
    reference_date = as_of or datetime.now(ZoneInfo('Asia/Seoul')).date()
    for index, raw in enumerate(rows):
        row = {k: clean(v) for k, v in raw.items()}
        if not allow_corrupted_text and (source in LICENSES or source == 'acaInsTiInfo' or source.startswith('stores/')):
            name_field, address_field = (
                ('ACA_NM', 'FA_RDNMA') if source == 'acaInsTiInfo' else
                ('bizesNm', 'rdnmAdr') if source.startswith('stores/') else
                ('BPLCNM', 'RDNWHLADDR'))
            try:
                validate_match_text(row, name_field, address_field)
            except ValueError as exc:
                raise ValueError(f'{source_path}: row={index + 1}: {exc}') from exc
        planned = False
        if source == 'schoolInfo' and row.get('FOND_YMD') is not None:
            raw_date = str(row['FOND_YMD'])
            if not re.fullmatch(r'\d{8}', raw_date):
                raise ValueError(f'{source_path}: row={index + 1}: invalid_foundation_date')
            try:
                planned = datetime.strptime(raw_date, '%Y%m%d').date() > reference_date
            except ValueError as exc:
                raise ValueError(f'{source_path}: row={index + 1}: invalid_foundation_date') from exc
        missing_keys = [k for k in keys if row.get(k) is None]
        if missing_keys and not (planned and missing_keys == ['SD_SCHUL_CODE']):
            raise ValueError(f"{source_path}: row={index + 1}: missing_identity {keys}")
        identity = None if missing_keys else tuple(str(row[k]) for k in keys)
        # 원천 행 위치는 관측 구분용이며 학교 식별키를 대신하지 않는다.
        observation_key = identity if identity is not None else ('source_row', source_path, index + 1)
        if observation_key in found and found[observation_key]["fields"] != row:
            raise ValueError(f"{source_path}: row={index + 1}: conflicting_identity {identity}")
        found[observation_key] = {"identity": list(identity) if identity else None, "fields": row,
                           "provenance": {"source": source, "source_path": source_path,
                                          "source_sha256": sha256, "collected_on": collected_on}}
        if source == 'schoolInfo':
            found[observation_key]['foundation_status'] = 'planned' if planned else 'not_future' if row.get('FOND_YMD') else 'unknown'
            found[observation_key]['foundation_label'] = '(예정)' if planned else None
            found[observation_key]['status_as_of'] = reference_date.isoformat()
            found[observation_key]['source_row_1based'] = index + 1
        if preserve_observations:
            found[observation_key]['source_row_1based'] = index + 1
            observations.append(found[observation_key])
    return observations if preserve_observations else list(found.values())


def match(rows: list[dict], stores: list[dict], name_field: str,
          address_field: str) -> list[dict]:
    """이름과 전체 도로명주소가 모두 같은 경우만 후보로 삼는다."""
    def token(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())
    index: dict[tuple[str, str], set[str]] = defaultdict(set)
    for store in stores:
        validate_match_text(store, 'bizesNm', 'rdnmAdr')
        name, address = token(store.get("bizesNm")), token(store.get("rdnmAdr"))
        if name and address:
            index[name, address].add(str(store["bizesId"]))
    results = []
    for row in rows:
        fields = row["fields"]
        validate_match_text(fields, name_field, address_field)
        name, address = token(fields.get(name_field)), token(fields.get(address_field))
        candidates = sorted(index.get((name, address), set())) if name and address else []
        status = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
        results.append({"identity": row["identity"], "status": status,
                        "store_id": candidates[0] if status == "matched" else None,
                        "candidate_store_ids": candidates,
                        "reason": "exact_name_and_full_address" if candidates else
                                  "missing_name_or_address" if not name or not address else "no_exact_candidate"})
    return results


def build(run: Path, previous: Path, output: Path, report_path: Path,
          quarantine_path: Path | None = None) -> dict:
    """임시 디스크를 정리하며 빌더를 실행한다."""
    with tempfile.TemporaryDirectory(prefix='industry-silver-') as folder:
        return _build(run, previous, output, report_path, Path(folder), quarantine_path)


def _build(run: Path, previous: Path, output: Path, report_path: Path, scratch: Path,
           quarantine_path: Path | None = None) -> dict:
    """전체 원본 검증 후 출력한다. 기존 산출물은 덮어쓰지 않는다."""
    targets = [output, report_path] + ([quarantine_path] if quarantine_path else [])
    if len({path.resolve() for path in targets}) != len(targets):
        raise ValueError('output_paths_must_be_distinct')
    if any(path.exists() for path in targets):
        raise FileExistsError("기존 산출물은 덮어쓰지 않습니다")
    datasets: dict[str, DiskRows] = defaultdict(lambda: DiskRows(scratch))
    quarantined: dict[str, DiskRows] = defaultdict(lambda: DiskRows(scratch))
    raw_counts: Counter[str] = Counter()
    manifests = []
    errors = []

    def ingest(path: Path, source: str, rows: list[dict], keys: tuple[str, ...], date: str) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifests.append({"path": str(path), "sha256": digest, "raw_rows": len(rows), "collected_on": date})
        raw_counts[source] += len(rows)
        try:
            records = normalize(rows, keys, source, str(path), digest, date,
                                allow_corrupted_text=quarantine_path is not None and source in LICENSES,
                                preserve_observations=quarantine_path is not None)
            accepted = []
            rejected = []
            for record in records:
                damaged = [field for field in ('BPLCNM', 'RDNWHLADDR')
                           if source in LICENSES and '\ufffd' in str(record['fields'].get(field) or '')]
                if quarantine_path is not None and damaged:
                    rejected.append({**record, 'raw_fields': rows[record['source_row_1based'] - 1],
                                     'quarantine_reason': 'corrupted_match_text', 'damaged_fields': damaged})
                else:
                    accepted.append(record)
            datasets[source].extend(accepted)
            if rejected:
                quarantined[source].extend(rejected)
        except ValueError as exc:
            errors.append(str(exc))

    for service, key in [("acaInsTiInfo", "ACA_ASNUM"), ("schoolInfo", "SD_SCHUL_CODE")]:
        paths = sorted(p for p in (run / service).glob("*.json") if p.stem.isdigit())
        if not paths:
            errors.append(f"missing_source: {service}")
        for path in paths:
            blocks = json.loads(path.read_bytes())[service]
            rows = [r for block in blocks for r in block.get("row", [])]
            ingest(path, service, rows, ("ATPT_OFCDC_SC_CODE", key), "2026-10-17")
    # 기본 식별키 검증이 실패하면 대용량 재고를 읽기 전에 중단한다.
    if errors:
        result = {"status": "blocked", "errors": errors, "sources": manifests,
                  "rows": {k: len(v) for k, v in datasets.items()},
                  "silver_written": False,
                  "not_processed": ["school_locations", "school_students", "licenses", "stores", "matching"],
                  "note": "Identity validation failed; no partial Silver was promoted."}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return result
    for path in sorted(p for p in (run / "school_locations_file").glob("*.json") if p.stem.isdigit()):
        ingest(path, "school_locations", json.loads(path.read_bytes()), ("SCHOOL_ID",), "2026-10-17")
    for path in sorted((run / "school_students").glob("????_??.json")):
        year, kind = path.stem.split("_")
        rows = [dict(r, requested_year=year, requested_kind=kind) for r in json.loads(path.read_bytes())["list"]]
        ingest(path, "school_students", rows, ("requested_year", "requested_kind", "SCHUL_CODE"), "2026-10-17")
    for source, service in LICENSES.items():
        paths = sorted(p for p in (previous / "seoul" / service / "all").glob("*.json") if p.stem.isdigit())
        if not paths:
            errors.append(f"missing_source: {service}")
        for path in paths:
            ingest(path, source, json.loads(path.read_bytes())[service]["row"],
                   ("OPNSFTEAMCODE", "MGTNO"), "2026-10-09")
    for slug in ACTIVE_HUBS:
        folder = previous / ("recovery/stores/suyu" if slug == "suyu" else f"stores/{slug}")
        paths = sorted(p for p in folder.glob("*.json") if p.stem.isdigit())
        if not paths:
            errors.append(f"missing_source: stores/{slug}")
        for path in paths:
            ingest(path, f"stores/{slug}", json.loads(path.read_bytes())["body"]["items"], ("bizesId",), "2026-10-09")
    for source in ("school_locations", "school_students"):
        if not datasets[source]:
            errors.append(f"missing_source: {source}")
    # 페이지를 가로지르는 중복도 같은 계약으로 검증한다.
    for source in datasets.keys() | quarantined.keys():
        seen = {}
        # 격리 행도 식별키 충돌 검증에 포함한다. 격리는 잘못된 키를 우회하는 수단이 아니다.
        for records in (datasets.get(source, ()), quarantined.get(source, ())):
            for row in records:
                key = tuple(row["identity"]) if row['identity'] else ('source_row', row['provenance']['source_path'], row['source_row_1based'])
                digest = hashlib.sha256(json.dumps(row['fields'], sort_keys=True).encode()).hexdigest()
                if key in seen and seen[key] != digest:
                    errors.append(f"{source}: conflicting_identity_across_pages: {key}")
                seen[key] = digest
    accounting = {source: {'raw_rows': count, 'accepted_rows': len(datasets.get(source, ())),
                           'quarantined_rows': len(quarantined.get(source, ()))}
                  for source, count in raw_counts.items()}
    if quarantine_path is not None:
        for source, counts in accounting.items():
            if counts['accepted_rows'] + counts['quarantined_rows'] != counts['raw_rows']:
                errors.append(f'{source}: row_accounting_mismatch')
    status = 'partial_quarantined' if quarantine_path is not None and quarantined else 'validated'
    result = {"status": "blocked" if errors else status, "errors": errors,
              "sources": manifests, "rows": {k: len(v) for k, v in datasets.items()},
              "limitations": ["실제 영업 시작·종료와 행정 등록일은 다르다.",
                              "이름과 전체 주소가 같은 연결 후보이며 실제 동일 점포 확정이 아니다.",
                              "학교 원천 간 코드 체계가 달라 자동 연결하지 않는다.",
                              "Gold·모델·API에는 연결하지 않는다. 결측 보간 없음."]}
    result['silver_written'] = False
    if quarantine_path is not None:
        result.update(row_accounting=accounting, quarantine_path=str(quarantine_path),
                      quarantined_rows=sum(len(records) for records in quarantined.values()),
                      quarantine_written=False)
    if not errors:
        links = {}
        # 점포 인덱스도 디스크에 두고 반경 간 중복을 점포 ID로 구분한다.
        with closing(sqlite3.connect(scratch / 'stores.sqlite')) as connection:
            connection.execute('CREATE TABLE stores (name TEXT, address TEXT, id TEXT, PRIMARY KEY(name,address,id))')
            for source, records in datasets.items():
                if source.startswith('stores/'):
                    connection.executemany('INSERT OR IGNORE INTO stores VALUES (?,?,?)',
                        ((re.sub(r'\s+', ' ', str(r['fields'].get('bizesNm') or '').strip()),
                          re.sub(r'\s+', ' ', str(r['fields'].get('rdnmAdr') or '').strip()),
                          str(r['fields']['bizesId'])) for r in records))
            for source in ['acaInsTiInfo', *LICENSES]:
                linked = DiskRows(scratch)
                pending = []
                for row in datasets[source]:
                    fields = row['fields']
                    name = fields.get('ACA_NM' if source == 'acaInsTiInfo' else 'BPLCNM')
                    address = fields.get('FA_RDNMA' if source == 'acaInsTiInfo' else 'RDNWHLADDR')
                    candidates = connection.execute('SELECT id FROM stores WHERE name=? AND address=?',
                        (re.sub(r'\s+', ' ', str(name or '').strip()), re.sub(r'\s+', ' ', str(address or '').strip()))).fetchall() if name and address else []
                    stores = [{'bizesId': item[0], 'bizesNm': name, 'rdnmAdr': address} for item in candidates]
                    pending.extend(match([row], stores, 'ACA_NM' if source == 'acaInsTiInfo' else 'BPLCNM',
                                         'FA_RDNMA' if source == 'acaInsTiInfo' else 'RDNWHLADDR'))
                    if len(pending) >= 1000:
                        linked.extend(pending)
                        pending.clear()
                linked.extend(pending)
                links[source] = linked
        result["matching"] = {k: dict(Counter(r["status"] for r in v)) for k, v in links.items()}
        result['school_foundation_status'] = dict(Counter(r['foundation_status'] for r in datasets['schoolInfo']))
        result['planned_schools_without_identity'] = sum(r['identity'] is None for r in datasets['schoolInfo'])
        result['silver_written'] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            stream.write('{"status":' + json.dumps(status) + ',"datasets":{')
            for index, (source, records) in enumerate(datasets.items()):
                if index:
                    stream.write(',')
                stream.write(json.dumps(source) + ':')
                write_rows(stream, records)
            stream.write('},"links":{')
            for index, (source, records) in enumerate(links.items()):
                if index:
                    stream.write(',')
                stream.write(json.dumps(source) + ':')
                write_rows(stream, records)
            stream.write('}}')
        if quarantine_path is not None:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            with quarantine_path.open('x', encoding='utf-8') as stream:
                stream.write('{"status":' + json.dumps(status) + ',"quarantined":{')
                for index, (source, records) in enumerate(quarantined.items()):
                    if index:
                        stream.write(',')
                    stream.write(json.dumps(source) + ':')
                    write_rows(stream, records)
                stream.write('}}')
            result['quarantine_written'] = True
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument('--quarantine', type=Path,
                        help='승인된 부분 승격 모드: 인허가 연결 필드 손상 행을 별도 파일로 보존')
    args = parser.parse_args()
    result = build(args.run, args.previous, args.output, args.report, args.quarantine)
    print(json.dumps({"status": result["status"], "errors": result["errors"]}, ensure_ascii=False))
    raise SystemExit(1 if result["errors"] else 0)
