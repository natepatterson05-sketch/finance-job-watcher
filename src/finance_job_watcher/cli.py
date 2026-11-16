import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from .pipeline import atomic_write, collect, rebuild, write_status


def main():
    parser = argparse.ArgumentParser(description='Collect public JSON job boards or replay raw history')
    parser.add_argument('command', choices=['collect', 'rebuild', 'verify'])
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--sources', type=Path, default=Path('config/sources.json'))
    parser.add_argument('--candidates', type=Path, default=Path('config/candidates.json'))
    parser.add_argument('--verification', type=Path, default=Path('docs/source-verification.json'))
    args = parser.parse_args()
    if args.command in ('collect', 'verify'):
        path = args.candidates if args.command == 'verify' else args.sources
        sources = json.loads(path.read_text(encoding='utf-8-sig'))
        names = [s['name'] for s in sources]
        if len(names) != len(set(names)) or any(not n or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in n) for n in names):
            parser.error('Source names must be unique safe lowercase filenames')
        if any(s.get('ats') != 'greenhouse' for s in sources):
            parser.error('Only Greenhouse is implemented in Phase 1')
        if not sources:
            parser.error('No verified sources; run verify first with working outbound HTTPS')
        status = collect(sources, args.data_dir)
        if args.command == 'verify':
            successful = {s['name'] for s in status['sources'] if s['ok']}
            verified = [s for s in sources if s['name'] in successful]
            evidence = {'run_time': status['run_time'], 'status': 'complete' if len(verified) >= 15 else 'incomplete',
                        'sources': [dict(s, **next(r for r in status['sources'] if r['name'] == s['name'])) for s in sources]}
            atomic_write(args.verification, (json.dumps(evidence, indent=2) + '\n').encode())
            atomic_write(args.sources, (json.dumps(verified, indent=2) + '\n').encode())
            print(json.dumps(evidence, indent=2))
            return 0 if len(verified) >= 15 else 1
    else:
        rows, days = rebuild(args.data_dir)
        now = datetime.now(timezone.utc)
        results = []
        for path in sorted((args.data_dir / 'raw' / now.date().isoformat()).glob('*.json.gz')):
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                snapshot = json.load(stream)
            results.append({'name': snapshot['source']['name'], 'ok': True, 'count': len(snapshot['payload']['jobs'])})
        status = write_status(args.data_dir, rows, days, results, now)
    print(json.dumps(status, indent=2))
    return 0 if args.command == 'rebuild' or any(s['ok'] for s in status['sources']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
