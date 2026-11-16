# Finance Job Watcher

A Financial Data Analytics course project tracking public employer job boards,
with a title-based finance flag and reproducible daily history.

## Current state

Phase 1 collection and history are validated: 21 public Greenhouse boards
returned 3,787 postings on 2026-11-16 UTC, including 111 finance-related titles.
All 27 offline pytest cases pass, and replaying the real snapshots produces a
byte-identical history.csv. No accepted board exceeds 5,000 jobs.
Block failed posting validation and HubSpot returned 404; both are excluded from
the active 21-employer registry. See docs/source-verification.json for per-board
endpoints, counts, outcomes, and verification time.

Python 3.14.4 works through the project virtual environment. The user performed
live verification from PowerShell because this session blocks outbound shell
HTTPS. Git writes remain blocked in this session, so the incremental local
commits still need to be created. Nothing has been pushed or published.

## Run (Python 3.11+)

From the repository root in a network-enabled environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m finance_job_watcher.cli verify
python -m finance_job_watcher.cli collect
python -m finance_job_watcher.cli rebuild
python -m pytest
```

`verify` tries every candidate, archives successful responses, writes status,
records per-source counts/errors and UTC verification time, and installs only
successful sources into `config/sources.json`. It exits unsuccessfully if fewer
than 15 pass; replace failed candidates and repeat. Verify before daily use.
`collect` fetches all configured boards independently. A partially successful run
exits zero; an entirely failed run exits nonzero. Inspect per-source status.
`rebuild` needs only `data/raw`, never network or the source registry. Options:
`--data-dir`, `--sources`, `--candidates`, `--verification`.

## Files and sources

- `PLAN.md`: implementation sequence, repository structure, later phases.
- `src/finance_job_watcher/`: standard-library-only runtime and CLI.
- `config/candidates.json`: unverified employer candidates.
- `config/sources.json`: only boards that pass the verification command.
- `docs/source-verification.json`: evidence and limits, never invented counts.
- `data/raw/YYYY-MM-DD/source.json.gz`: successful UTC daily snapshots. Each gzip
  contains `{source: <configuration>, payload: <original JSON response>}` so
  future config changes cannot alter employer identity during replay. JSON is
  reserialized; payload values are preserved. Atomic writes prevent partial files.
- `data/history.csv`: deterministic replay, sorted by `posting_id`.
- `data/status.json`: current run time, earliest successful snapshot date, number
  of distinct UTC days with at least one success, all-role open/new/removed counts,
  and per-source `name`, `ok`, `count` (plus error on failures).
- `tests/test_pipeline.py`: synthetic **test-only** records; never production data.

Phase 1 implements Greenhouse's public, unauthenticated Job Board JSON API:
`https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`.
[Official API documentation](https://docs.greenhouse.io/job-board.html).
The full jobs array is fetched, including non-finance roles. `meta.total`, when
provided, must match the returned array. No HTML, login, or application endpoints
are used. Other ATS adapters can be added later; diversity of ATS types is not
needed to collect 15 employers. Boards above 5,000 postings are rejected rather
than silently truncated; none is accepted with an undocumented search filter.
If a future board needs a search scope, implement a supported JSON search endpoint,
document its term and scope, and test completeness before enabling it.

## Columns and lifecycle

The exact CSV columns, in order:

```text
posting_id,source,source_id,employer,title,location,department,posted_date,url,in_role,first_run,first_seen,last_seen,status,removed_date
```

`posting_id` is `source:source_id`; IDs are strings. Location uses the board's
location name; departments are joined with `; `. `posted_date` uses
`first_published` converted to a UTC YYYY-MM-DD date when present and is otherwise empty. An ATS update timestamp
is not substituted for the publication date. Missing optional values stay empty.
Boolean fields use `true`/`false`. Status is `open` or `removed`.

`first_seen` is the first successful UTC snapshot containing the ID. `last_seen`
is the latest successful snapshot containing it. An absent ID is removed only
on a successful snapshot for its own source, including a valid empty jobs list.
A missing or failed source never closes jobs. Reopening clears `removed_date`
and preserves `first_seen` and `first_run`. `first_run` marks jobs first observed
on their source's earliest successful day; it distinguishes baseline inventory
from subsequent arrivals. This CSV stores latest lifecycle state, while raw
snapshots preserve all episodes for later market calculations.

Same-day successful reruns replace that source's snapshot; replay counts each
UTC day once. Failed reruns write no snapshot and preserve earlier same-day
successes. Intraday appearances/removals are intentionally not retained. A job
seen only in an overwritten intraday snapshot is not part of final daily history.
`new_today` counts first observations excluding first-run postings and reopenings; `removed_today` counts
currently removed jobs whose latest removal was today. Counts cover all roles.
Rebuild status reports only today's archived successes; it cannot reconstruct
failed fetch attempts because failures have no raw files. Collection status
reports the latest attempt even when a previous same-day success remains archived.

## Finance classification

Case-insensitive, word-boundary title matching for any of: `financial analyst`,
`finance`, `financial planning`, `FP&A` (optional spaces), `FP and A`,
`credit analyst`, `credit risk`, `treasury`, `accountant`, `accounting`,
`controller`, `investment analyst`, `valuation analyst`, `financial reporting`,
`financial modeling`, or `financial modelling`.

The rule intentionally includes related accounting and treasury roles. It uses
no description, department, or location data and is a transparent heuristic:
finance software titles may match `finance`; titles such as `Data Analyst` do
not qualify without a finance phrase. Review precision/recall in later phases.

## Remaining phases

Daily GitHub Actions and GitHub Issues; tests on each push; GitHub Pages Today,
Browse, and Market pages; six browser-calculated market charts; PWA manifest,
service worker, and offline caching. No deployment or push has been performed.



