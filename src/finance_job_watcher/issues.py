"""Render daily reports; publishing is an explicit, separate operation."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

MARKER = '<!-- finance-job-watcher:daily:v1 -->'
COMMENT_MARKER = '<!-- finance-job-watcher:postings:v1 -->'
BODY_LIMIT = 50000  # Below GitHub's body limit, with room for metadata.


def escape(value):
    return re.sub(r'([\\`*_{}\[\]<>|])', r'\\\1', str(value)).replace('\n', ' ').replace('\r', ' ').replace('@', '&#64;')


def report_day(status):
    value = datetime.fromisoformat(status['run_time'].replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('run_time must include a timezone')
    return value.astimezone(timezone.utc).date().isoformat()


def render_report(rows, status):
    day = report_day(status)
    new = sorted((r for r in rows if r['first_seen'] == day and r['first_run'] == 'false'), key=lambda r: r['posting_id'])
    removed = sorted((r for r in rows if r['removed_date'] == day), key=lambda r: r['posting_id'])
    header = [MARKER, f'# Finance Job Watcher — {day}', '', f"Run time: {status['run_time']}",
              f"Open: {status['open']} | New: {len(new)} | Removed: {len(removed)}",
              '', '## Sources', '']
    for source in status['sources']:
        outcome = f"OK — {source['count']} postings" if source['ok'] else 'FAILED'
        header.append(f"- {escape(source['name'])}: {outcome}")
    header += ['', 'All postings are included; baseline postings are excluded from new arrivals.', '']
    lines = []
    for heading, postings in [('New postings', new), ('Removed postings', removed)]:
        lines += [f'## {heading} ({len(postings)})', '']
        if not postings:
            lines.append('None.')
        for row in postings:
            url = row['url']
            if not url.startswith('https://'):
                raise ValueError('Report posting URL must use HTTPS')
            url = quote(url, safe=':/?&=%#')
            lines.append(f"- [{escape(row['title'])}]({url}) — {escape(row['employer'])} — {escape(row['location'])}")
        lines.append('')
    body = '\n'.join(header + lines)
    if len(body) <= BODY_LIMIT:
        return day, body, []
    # Keep every link on busy days, using managed comments instead of truncation.
    chunks, chunk = [], COMMENT_MARKER + '\n'
    for line in lines:
        if len(line) + len(COMMENT_MARKER) + 2 > BODY_LIMIT:
            raise ValueError('A report entry exceeds GitHub comment size')
        if len(chunk) + len(line) + 1 > BODY_LIMIT:
            chunks.append(chunk)
            chunk = COMMENT_MARKER + '\n'
        chunk += line + '\n'
    chunks.append(chunk)
    return day, '\n'.join(header) + '\nPosting links are listed in the managed comments below.\n', chunks


class GitHubClient:
    def __init__(self, repository, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Repository must be OWNER/REPOSITORY')
        self.base = f'https://api.github.com/repos/{repository}'
        self.token = token

    def request(self, method, path, data=None):
        request = Request(self.base + path, method=method,
                          data=None if data is None else json.dumps(data).encode(),
                          headers={'Authorization': f'Bearer {self.token}',
                                   'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2022-11-28',
                                   'Content-Type': 'application/json',
                                   'User-Agent': 'FinanceJobWatcher/0.1'})
        with urlopen(request, timeout=45) as response:
            body = response.read()
            return json.loads(body) if body else None

    def list(self, path):
        items, page = [], 1
        separator = '&' if '?' in path else '?'
        while True:
            batch = self.request('GET', f'{path}{separator}per_page=100&page={page}')
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1


def sync_issue(client, rows, status):
    day, body, chunks = render_report(rows, status)
    issues = [i for i in client.list('/issues?state=all')
              if 'pull_request' not in i and (i.get('body') or '').startswith(MARKER)]
    current = [i for i in issues if i['title'] == day]
    if len(current) > 1:
        raise ValueError('Multiple managed issues for this date; resolve duplicates first')
    if current:
        issue = client.request('PATCH', f"/issues/{current[0]['number']}",
                               {'title': day, 'body': body, 'state': 'open'})
    else:
        issue = client.request('POST', '/issues', {'title': day, 'body': body})
    number = issue['number']
    comments = [c for c in client.list(f'/issues/{number}/comments')
                if (c.get('body') or '').startswith(COMMENT_MARKER)]
    for index, chunk in enumerate(chunks):
        if index < len(comments):
            client.request('PATCH', f"/issues/comments/{comments[index]['id']}", {'body': chunk})
        else:
            client.request('POST', f'/issues/{number}/comments', {'body': chunk})
    for comment in comments[len(chunks):]:
        client.request('DELETE', f"/issues/comments/{comment['id']}")
    # Close older reports only after today's complete report has been written.
    for old in issues:
        if old['state'] == 'open' and re.fullmatch(r'\d{4}-\d{2}-\d{2}', old['title']) and old['title'] < day:
            client.request('PATCH', f"/issues/{old['number']}", {'state': 'closed'})
    return number


def main():
    parser = argparse.ArgumentParser(description='Preview the daily Issue; --publish explicitly writes to GitHub')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    status = json.loads((args.data_dir / 'status.json').read_text(encoding='utf-8'))
    with (args.data_dir / 'history.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not args.publish:
        day, body, chunks = render_report(rows, status)
        print(body)
        for chunk in chunks:
            print('\n' + chunk)
        return 0
    token = os.environ.get('GH_TOKEN')
    repository = os.environ.get('GITHUB_REPOSITORY')
    if not token or not repository:
        parser.error('--publish requires GH_TOKEN and GITHUB_REPOSITORY')
    number = sync_issue(GitHubClient(repository, token), rows, status)
    print(f'Daily report synchronized: issue #{number}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
