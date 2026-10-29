"""광주 수집의 지역·시설 검증과 부분 페이지 실패를 고정한다."""
import pytest

from data.collectors import gwangju_candidates as candidates
from data.collectors import gwangju_licensing as licensing
from data.config.page_hubs import PageHub


def test_landmark_selection_rejects_other_city_gu_and_station_exit():
    def place(title, address):
        return {'title': title, 'address': {'road': address}}

    expected = place('상무역', '광주광역시 서구 상무대로 777')
    items = [place('상무역1번출구', '광주광역시 서구'),
             place('상무역', '경기도 광주시 서구'),
             place('상무역', '광주광역시 북구'), expected]
    assert candidates.select_place(items, '서구', '상무역') is expected
    with pytest.raises(ValueError):
        candidates.select_place(items[:-1], '서구', '상무역')


def test_store_partial_page_fails_instead_of_saving_success(monkeypatch):
    from data.collectors import building_vacancy as source

    pages = iter([{'body': {'items': [{'bizesId': 'one'}], 'totalCount': 2}},
                  {'body': {'items': [], 'totalCount': 2}}])
    monkeypatch.setattr(source, '_get_json', lambda *_: next(pages))
    monkeypatch.setattr(candidates.time, 'sleep', lambda _: None)
    with pytest.raises(ValueError, match='부분 수집'):
        candidates.fetch_complete_stores('test-key', PageHub('probe', '검증', 126.9, 35.1))


def test_licensing_partial_download_has_no_complete_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(licensing, 'bronze_dir', lambda _: tmp_path)
    monkeypatch.setattr(licensing, 'fetch', lambda params: {
        'response': {'body': {'totalCount': 2, 'items': {'item':
            [] if params.get('pageNo') == 2 else [{
                'MNG_NO': 'sample', 'OPN_ATMY_GRP_CD': 'observed',
                'ROAD_NM_ADDR': params.get('cond[ROAD_NM_ADDR::LIKE]', '광주광역시 동구'),
            }]}}}})
    with pytest.raises(ValueError, match='부분 수집'):
        licensing.collect_gu('동구')
    assert not (tmp_path / '동구_complete.json').exists()


def test_licensing_service_error_is_not_empty_success(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {'response': {'header': {'resultCode': '20'}}}

    monkeypatch.setenv('DATA_GO_KR_SERVICE_KEY', 'test-key')
    monkeypatch.setattr(licensing, '_LOCAL', type('Local', (), {
        'session': type('Session', (), {'get': lambda *_args, **_kwargs: Response()})()
    })())
    with pytest.raises(RuntimeError, match='권한'):
        licensing.fetch({})
