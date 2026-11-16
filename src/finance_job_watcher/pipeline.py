from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

COLUMNS = "posting_id source source_id employer title location department posted_date url in_role first_run first_seen last_seen status removed_date".split()
ROLE = re.compile(r"\b(financial analyst|finance|financial planning|fp\s*&\s*a|fp\s*and\s*a|credit analyst|credit risk|treasury|accountant|accounting|controller|investment analyst|valuation analyst|financial reporting|financial modeling|financial modelling)\b", re.I)


def in_role(title):
    return bool(ROLE.search(title))


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def utc_date(value):
    if not value:
        return ''
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        # Date-only values are already calendar dates; ambiguous timestamps fail.
        if len(value) != 10:
            raise ValueError('Publication timestamp must include a timezone')
        return parsed.date().isoformat()
    return parsed.astimezone(timezone.utc).date().isoformat()


def normalize(payload, source):
    """Validate the complete Greenhouse response before treating it as success."""
    if not isinstance(payload, dict) or not isinstance(payload.get('jobs'), list):
        raise ValueError('Expected a JSON object with a jobs array')
    jobs = payload['jobs']
    total = payload.get('meta', {}).get('total', len(jobs))
    if total != len(jobs):
        raise ValueError('Incomplete board response')
    if len(jobs) > 5000:
        raise ValueError('Board exceeds 5,000; configure and document a search scope first')
    rows = []
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or job.get('id') is None:
            raise ValueError('Missing posting ID')
        sid = str(job['id'])
        if sid in seen:
            raise ValueError('Duplicate posting ID')
        seen.add(sid)
        title = job.get('title')
        url = job.get('absolute_url')
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.startswith('https://'):
            raise ValueError('Missing title or HTTPS URL')
        row = dict.fromkeys(COLUMNS, '')
        row.update(posting_id=f"{source['name']}:{sid}", source=source['name'],
                   source_id=sid, employer=source['employer'], title=title,
                   location=(job.get('location') or {}).get('name', ''),
                   department='; '.join(d['name'] for d in job.get('departments', []) if d.get('name')),
                   posted_date=utc_date(job.get('first_published')), url=url,
                   in_role=str(in_role(title)).lower())
        rows.append(row)
    return sorted(rows, key=lambda r: r['posting_id'])


def fetch(source):
    request = Request(source['url'], headers={'Accept': 'application/json', 'User-Agent': 'FinanceJobWatcher/0.1'})
    with urlopen(request, timeout=45) as response:
        if 'json' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected JSON content type')
        return json.load(response)


def save_snapshot(root, day, source, payload):
    normalize(payload, source)
    # Configuration travels with the untouched source payload for config-free replay.
    envelope = {'source': source, 'payload': payload}
    raw = json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode('utf-8')
    path = Path(root) / 'raw' / day / (source['name'] + '.json.gz')
    atomic_write(path, gzip.compress(raw, mtime=0))


def rebuild(root):
    """Use raw snapshots alone; failed/missing dates never remove a posting."""
    root = Path(root)
    history, source_first, successful_days = {}, {}, set()
    for path in sorted((root / 'raw').glob('*/*.json.gz')):
        day = path.parent.name
        if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
            raise ValueError(f'Invalid snapshot date: {day}')
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            snapshot = json.load(stream)
        source = snapshot['source']
        name = source['name']
        if path.name != name + '.json.gz':
            raise ValueError('Snapshot/source name mismatch')
        rows = normalize(snapshot['payload'], source)
        successful_days.add(day)
        source_first.setdefault(name, day)
        present = {r['posting_id'] for r in rows}
        for pid, old in history.items():
            if old['source'] == name and old['status'] == 'open' and pid not in present:
                old.update(status='removed', removed_date=day)
        for row in rows:
            old = history.get(row['posting_id'])
            row.update(first_run=old['first_run'] if old else str(day == source_first[name]).lower(),
                       first_seen=old['first_seen'] if old else day,
                       last_seen=day, status='open', removed_date='')
            history[row['posting_id']] = row
    rows = [history[pid] for pid in sorted(history)]
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=COLUMNS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(root / 'history.csv', output.getvalue().encode('utf-8'))
    return rows, sorted(successful_days)


def write_status(root, rows, days, results, now):
    day = now.date().isoformat()
    status = {'run_time': now.isoformat().replace('+00:00', 'Z'),
              'first_run_date': days[0] if days else None, 'days_with_success': len(days),
              'open': sum(r['status'] == 'open' for r in rows),
              'new_today': sum(r['first_seen'] == day and r['first_run'] == 'false' for r in rows),
              'removed_today': sum(r['removed_date'] == day for r in rows),
              'sources': results}
    atomic_write(Path(root) / 'status.json', (json.dumps(status, indent=2) + '\n').encode())
    return status


def collect(sources, root, now=None, fetcher=fetch):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    results = []
    for source in sources:
        try:
            payload = fetcher(source)
            rows = normalize(payload, source)
            save_snapshot(root, now.date().isoformat(), source, payload)
            results.append({'name': source['name'], 'ok': True, 'count': len(rows)})
        except Exception as exc:
            # Preserve an earlier successful snapshot on same-day failed reruns.
            results.append({'name': source['name'], 'ok': False, 'count': 0, 'error': str(exc)})
    rows, days = rebuild(root)
    return write_status(root, rows, days, results, now)

