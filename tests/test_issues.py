import copy
import csv
import json

import pytest

from finance_job_watcher import issues


def row(pid='one', **changes):
    result = dict(posting_id=pid, title='Financial Analyst', employer='Example',
                  location='Chicago', url='https://example.com/jobs/1',
                  first_seen='2026-11-16', first_run='false', removed_date='')
    result.update(changes)
    return result


def status():
    return dict(run_time='2026-11-16T12:23:00Z', open=2,
                sources=[dict(name='example', ok=True, count=2),
                         dict(name='failed', ok=False, count=0)])


class FakeGitHub:
    def __init__(self, existing=None):
        self.issues = copy.deepcopy(existing or [])
        self.comments = {}
        self.calls = []
        self.fail_comments = False

    def list(self, path):
        if path.startswith('/issues?'):
            return copy.deepcopy(self.issues)
        number = int(path.split('/')[2])
        return copy.deepcopy(self.comments.get(number, []))

    def request(self, method, path, data=None):
        self.calls.append((method, path, data))
        if path == '/issues' and method == 'POST':
            item = dict(number=max([i['number'] for i in self.issues] + [0]) + 1,
                        state='open', **data)
            self.issues.append(item)
            return copy.deepcopy(item)
        if path.startswith('/issues/comments/'):
            cid = int(path.split('/')[-1])
            for comments in self.comments.values():
                for item in comments:
                    if item['id'] == cid:
                        if method == 'DELETE':
                            comments.remove(item)
                        else:
                            item.update(data)
                        return copy.deepcopy(item)
            raise AssertionError('Unknown comment')
        number = int(path.split('/')[2])
        if path.endswith('/comments'):
            if self.fail_comments:
                raise OSError('GitHub unavailable')
            comments = self.comments.setdefault(number, [])
            item = dict(id=sum(len(c) for c in self.comments.values()) + 100, **data)
            comments.append(item)
            return copy.deepcopy(item)
        item = next(i for i in self.issues if i['number'] == number)
        item.update(data)
        return copy.deepcopy(item)


def test_report_filters_baseline_and_uses_run_date():
    rows = [row('new'), row('baseline', title='Baseline', first_run='true'),
            row('old', title='Old', first_seen='2026-11-15'),
            row('removed', title='Removed', first_seen='2026-11-14', removed_date='2026-11-16')]
    day, body, chunks = issues.render_report(rows, status())
    assert day == '2026-11-16'
    assert '## New postings (1)' in body
    assert '## Removed postings (1)' in body
    assert '[Financial Analyst](https://example.com/jobs/1)' in body
    assert '[Removed]' in body
    assert 'Baseline' not in body and '[Old]' not in body
    assert 'failed: FAILED' in body
    assert chunks == []


def test_empty_day_still_creates_report():
    client = FakeGitHub()
    issues.sync_issue(client, [], status())
    assert len(client.issues) == 1
    assert client.issues[0]['title'] == '2026-11-16'
    assert 'New postings (0)' in client.issues[0]['body']
    assert 'Removed postings (0)' in client.issues[0]['body']


def test_rerun_updates_and_closes_only_managed_older_issues():
    client = FakeGitHub([
        dict(number=1, title='2026-11-15', body=issues.MARKER, state='open'),
        dict(number=2, title='2026-11-15', body='User issue', state='open'),
        dict(number=3, title='2026-11-17', body=issues.MARKER, state='open'),
    ])
    first = issues.sync_issue(client, [row()], status())
    second = issues.sync_issue(client, [], status())
    assert first == second
    assert len(client.issues) == 4
    assert client.issues[0]['state'] == 'closed'
    assert client.issues[1]['state'] == client.issues[2]['state'] == 'open'
    assert 'New postings (0)' in client.issues[3]['body']


def test_closed_current_issue_reopens():
    client = FakeGitHub([dict(number=1, title='2026-11-16', body=issues.MARKER, state='closed')])
    assert issues.sync_issue(client, [], status()) == 1
    assert client.issues[0]['state'] == 'open'


def test_large_report_keeps_all_links_and_rerun_removes_stale_comments(monkeypatch):
    monkeypatch.setattr(issues, 'BODY_LIMIT', 500)
    rows = [row(str(i), title=f'Posting {i}', url=f'https://example.com/{i}') for i in range(40)]
    client = FakeGitHub()
    number = issues.sync_issue(client, rows, status())
    comments = client.comments[number]
    assert len(comments) > 1
    assert all(len(c['body']) <= 500 for c in comments)
    for i in range(40):
        assert f'[Posting {i}]' in ''.join(c['body'] for c in comments)
    count = len(comments)
    issues.sync_issue(client, rows, status())
    assert len(client.comments[number]) == count
    client.comments[number].append(dict(id=9999, body='User comment'))
    issues.sync_issue(client, [], status())
    assert client.comments[number] == [dict(id=9999, body='User comment')]


def test_failed_report_does_not_close_previous_day(monkeypatch):
    monkeypatch.setattr(issues, 'BODY_LIMIT', 500)
    client = FakeGitHub([dict(number=1, title='2026-11-15', body=issues.MARKER, state='open')])
    client.fail_comments = True
    with pytest.raises(OSError):
        issues.sync_issue(client, [row(str(i)) for i in range(30)], status())
    assert client.issues[0]['state'] == 'open'


def test_github_client_paginates():
    client = issues.GitHubClient('owner/repository', 'test-only-token')
    calls = []

    def request(method, path, data=None):
        calls.append(path)
        return list(range(100)) if path.endswith('page=1') else [100]

    client.request = request
    assert len(client.list('/issues?state=all')) == 101
    assert calls == ['/issues?state=all&per_page=100&page=1', '/issues?state=all&per_page=100&page=2']


def test_markdown_is_escaped():
    _, body, _ = issues.render_report([row(title='[Analyst] @team', url='https://example.com/a(b)')], status())
    assert r'\[Analyst\]' in body
    assert '@team' not in body
    assert 'https://example.com/a%28b%29' in body


def test_run_date_is_utc():
    data = status()
    data['run_time'] = '2026-11-15T23:30:00-06:00'
    assert issues.report_day(data) == '2026-11-16'


def test_duplicate_daily_issues_fail_before_writing():
    client = FakeGitHub([dict(number=i, title='2026-11-16', body=issues.MARKER, state='open') for i in [1, 2]])
    with pytest.raises(ValueError, match='Multiple managed'):
        issues.sync_issue(client, [], status())
    assert client.calls == []


def test_preview_never_calls_github(monkeypatch, capsys, tmp_path):
    (tmp_path / 'status.json').write_text(json.dumps(status()), encoding='utf-8')
    sample = row()
    with (tmp_path / 'history.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(sample))
        writer.writeheader()
        writer.writerow(sample)
    monkeypatch.setattr('sys.argv', ['issues', '--data-dir', str(tmp_path)])
    monkeypatch.setattr(issues.GitHubClient, '__init__', lambda *a: pytest.fail('Preview used GitHub'))
    assert issues.main() == 0
    assert issues.MARKER in capsys.readouterr().out
