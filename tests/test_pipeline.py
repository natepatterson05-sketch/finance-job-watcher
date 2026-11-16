import csv
from datetime import datetime, timezone

import pytest

from finance_job_watcher.pipeline import COLUMNS, collect, in_role, normalize, rebuild, save_snapshot

SOURCE = {'name': 'example', 'employer': 'Example', 'ats': 'greenhouse', 'url': 'https://example.invalid/jobs'}
OTHER = dict(SOURCE, name='other', employer='Other')


def payload(*ids, title='Financial Analyst'):
    return {'jobs': [{'id': i, 'title': title, 'absolute_url': f'https://example.invalid/jobs/{i}',
                      'location': {'name': 'Chicago'}, 'departments': [{'name': 'Finance'}],
                      'first_published': '2026-01-01T12:00:00Z'} for i in ids], 'meta': {'total': len(ids)}}


def day(n):
    return datetime(2026, 1, n, 12, tzinfo=timezone.utc)


def test_normalization():
    row = normalize(payload(123), SOURCE)[0]
    assert list(row) == COLUMNS
    assert row['posting_id'] == 'example:123'
    assert row['source_id'] == '123'
    assert row['location'] == 'Chicago'
    assert row['department'] == 'Finance'
    assert row['posted_date'] == '2026-01-01'
    assert row['in_role'] == 'true'


@pytest.mark.parametrize('title', ['Senior Financial Analyst', 'FP&A Manager', 'Credit Analyst',
                                    'Director, Finance', 'Treasury Analyst', 'Controller', 'Accounting Manager'])
def test_finance_titles(title):
    assert in_role(title)


@pytest.mark.parametrize('title', ['Software Engineer', 'Data Analyst', 'Sales Representative', 'Financial Services Software Engineer'])
def test_other_titles(title):
    assert not in_role(title)


def test_all_postings_retained():
    assert len(normalize(payload(1, 2, title='Engineer'), SOURCE)) == 2


def test_missing_optional_fields():
    data = {'jobs': [{'id': 1, 'title': 'Engineer', 'absolute_url': 'https://example.invalid/1'}]}
    row = normalize(data, SOURCE)[0]
    assert row['posted_date'] == row['location'] == row['department'] == ''


@pytest.mark.parametrize('data', [{}, {'jobs': None}, {'jobs': [], 'meta': {'total': 1}},
                                   {'jobs': [{'id': 1}]}, payload(1, 1)])
def test_invalid_responses_rejected(data):
    with pytest.raises(ValueError):
        normalize(data, SOURCE)


def test_first_seen_last_seen_removal_and_reopening(tmp_path):
    save_snapshot(tmp_path, '2026-01-01', SOURCE, payload(1))
    save_snapshot(tmp_path, '2026-01-03', SOURCE, payload(1, 2))
    rows, days = rebuild(tmp_path)
    assert days == ['2026-01-01', '2026-01-03']
    assert rows[0]['first_seen'] == '2026-01-01'
    assert rows[0]['last_seen'] == '2026-01-03'
    assert rows[0]['first_run'] == 'true'
    assert rows[1]['first_run'] == 'false'
    save_snapshot(tmp_path, '2026-01-04', SOURCE, payload())
    rows, _ = rebuild(tmp_path)
    assert all(r['status'] == 'removed' and r['removed_date'] == '2026-01-04' for r in rows)
    assert rows[0]['last_seen'] == '2026-01-03'
    save_snapshot(tmp_path, '2026-01-06', SOURCE, payload(1))
    rows, _ = rebuild(tmp_path)
    assert rows[0]['first_seen'] == '2026-01-01'
    assert rows[0]['last_seen'] == '2026-01-06'
    assert rows[0]['removed_date'] == ''
    assert rows[0]['status'] == 'open'
    assert rows[1]['removed_date'] == '2026-01-04'


def test_failed_source_does_not_close_and_others_continue(tmp_path):
    collect([SOURCE, OTHER], tmp_path, day(1), lambda s: payload(1))

    def fetcher(source):
        if source['name'] == 'example':
            raise OSError('offline')
        return payload()

    status = collect([SOURCE, OTHER], tmp_path, day(2), fetcher)
    assert status['sources'][0]['ok'] is False
    assert status['sources'][1]['ok'] is True
    assert not (tmp_path / 'raw/2026-01-02/example.json.gz').exists()
    rows, _ = rebuild(tmp_path)
    assert rows[0]['status'] == 'open'
    assert rows[0]['last_seen'] == '2026-01-01'
    assert rows[1]['status'] == 'removed'
    assert status['open'] == 1 and status['removed_today'] == 1


def test_same_day_reruns_are_idempotent(tmp_path):
    first = collect([SOURCE], tmp_path, day(1), lambda s: payload(1))
    original = (tmp_path / 'history.csv').read_bytes()
    second = collect([SOURCE], tmp_path, day(1), lambda s: payload(1))
    assert first == second
    assert (tmp_path / 'history.csv').read_bytes() == original
    assert second['new_today'] == 0 and second['days_with_success'] == 1
    # Failed rerun keeps earlier successful evidence.
    collect([SOURCE], tmp_path, day(1), lambda s: (_ for _ in ()).throw(OSError('offline')))
    assert (tmp_path / 'history.csv').read_bytes() == original
    # Latest successful same-day snapshot replaces the earlier one.
    collect([SOURCE], tmp_path, day(1), lambda s: payload(2))
    rows, _ = rebuild(tmp_path)
    assert [r['source_id'] for r in rows] == ['2']


def test_history_is_sorted_and_rebuilt_without_config(tmp_path):
    save_snapshot(tmp_path, '2026-01-01', OTHER, payload(9, 2))
    save_snapshot(tmp_path, '2026-01-01', SOURCE, payload(1))
    rebuild(tmp_path)
    before = (tmp_path / 'history.csv').read_bytes()
    (tmp_path / 'history.csv').unlink()
    rows, _ = rebuild(tmp_path)
    assert (tmp_path / 'history.csv').read_bytes() == before
    assert [r['posting_id'] for r in rows] == sorted(r['posting_id'] for r in rows)
    with (tmp_path / 'history.csv').open(newline='') as stream:
        assert next(csv.reader(stream)) == COLUMNS


def test_all_failures_status(tmp_path):
    status = collect([SOURCE], tmp_path, day(1), lambda s: None)
    assert status['days_with_success'] == 0
    assert status['first_run_date'] is None
    assert status['open'] == status['new_today'] == status['removed_today'] == 0
    assert not list((tmp_path / 'raw').glob('*/*.gz'))


def test_oversized_board_rejected():
    with pytest.raises(ValueError, match='5,000'):
        normalize(payload(*range(5001)), SOURCE)



def test_posted_date_converted_to_utc():
    data = payload(1)
    data['jobs'][0]['first_published'] = '2026-01-01T23:30:00-06:00'
    assert normalize(data, SOURCE)[0]['posted_date'] == '2026-01-02'


def test_new_today_excludes_each_sources_baseline(tmp_path):
    baseline = collect([SOURCE], tmp_path, day(1), lambda s: payload(1))
    assert baseline['new_today'] == 0
    later = collect([SOURCE, OTHER], tmp_path, day(2),
                    lambda s: payload(1, 2) if s['name'] == 'example' else payload(9))
    assert later['new_today'] == 1
    assert later['open'] == 3
