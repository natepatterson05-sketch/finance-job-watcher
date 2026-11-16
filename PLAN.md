# Finance Job Watcher implementation plan

## Phase 1: collection and history
1. Establish a Python package, CLI, source registry, tests, and documentation.
2. Verify at least 15 public JSON employer boards; retain UTC verification evidence.
3. Collect whole boards, validate payloads before atomic gzip writes, isolate failures.
4. Normalize exact output columns and apply documented title rules.
5. Replay successful daily snapshots deterministically; preserve first observation across reopening.
6. Produce history and current run status; test lifecycle, failure, and rerun behavior.

## Repository
- src/finance_job_watcher/: pipeline and CLI
- config/sources.json: verified board registry
- docs/source-verification.json: live endpoint evidence
- data/raw/YYYY-MM-DD/source.json.gz: successful JSON payloads
- data/history.csv, data/status.json: derived results
- tests/: offline pipeline tests

## Later phases (not implemented in Phase 1)
- Daily GitHub Actions collection and daily GitHub Issues; tests on each push.
- GitHub Pages Today, Browse, and Market pages.
- Six browser-calculated market charts using exported history.
- PWA manifest, service worker, and offline caching.

## Semantics
Dates are UTC. A missing/failed source is not evidence of closure. Same-day
successes replace that source snapshot. History is rebuilt from snapshots alone.
First run marks postings present on the earliest successful date for their source.
Status totals cover all roles; in_role enables finance-only views later.

## Local commit sequence
1. Implementation plan and repository scaffold.
2. Verified sources and working collection/history pipeline.
3. Lifecycle tests and user documentation, with validation results.

## Assignment acceptance checklist (authoritative course specification)

### Phase 1 completion gate
- At least 15 fully verified, unauthenticated employer JSON boards; replace failures.
- Keep every returned posting; search and document any board over 5,000 jobs.
- Exact history columns; all date columns are UTC YYYY-MM-DD.
- first_run is source-specific baseline membership, not global baseline membership.
- new_today excludes first_run postings. Reopening retains original first_seen.
- Deterministic replay and same-day replacement; successful-source-only removals.
- Per-source outcomes including failures; pytest conversion and lifecycle coverage.

### Phase 2: automation and Issues
- Daily UTC GitHub Actions schedule plus manual dispatch; pytest on every push.
- Commit raw/history/status, including partial-source-failure runs.
- Date-titled daily Issue with linked new and removed postings, even with no changes.
- Same-day rerun updates the Issue; close the previous day's Issue.
- README test status badge.
- A course-successful run must finish AND commit; days_with_success still follows
  the required raw-file date count. Do not claim raw dates prove committed runs.

### Phase 3: GitHub Pages
- Shared navigation, fonts, colors; browser loads history.csv and status.json.
- Today: run time, every source status, four specified counts, new/removed links.
- Browse: finance default/all toggle, employer/location/days-open filters, title
  search, first-seen sort, apply links, persistent browser-local starred shortlist.
- Market: six sections, each with a finding heading, explanation, and chart:
  1. Daily first observations for all and finance roles, excluding first_run.
  2. Daily removals using removed_date.
  3. Current open postings per employer.
  4. Median removed_date minus first_seen for removed, non-first-run postings.
  5. Share removed in <=7 days among non-first-run postings first seen at least
     seven days before the last run. Open eligible postings remain in denominator.
  6. Top locations among current open postings.
- All market numbers computed in the browser from history, using last run as
  reference date, never the viewer's current date.

### Phase 4: installability and submission
- Web app manifest, install icons, service worker; network data when online,
  cached last-loaded data and working pages offline.
- First successful run by Blackboard first-run date, and successful committed
  runs on at least seven different days by the due date; no invented backfill.
- Final .txt or .md with exactly four lines: name, student ID, repository URL,
  live site URL. Student details and Blackboard dates remain user-supplied.
- Public repository and live Pages deployment require the user's approval;
  current authorization covers local work only.

## Phase 2 implementation status
Daily workflow, push/PR tests, and explicit-publish daily Issue synchronization
are implemented locally. Eleven offline Issue tests pass (38 tests total).
Hosted execution, a functional repository badge, and activation remain pending
repository selection and approval to push. Website and PWA remain later phases.

## Website/PWA implementation status
- Implemented Today, Browse, Market and shared responsive styles/navigation.
- Browser-only CSV parsing, all six specified metrics/charts, title filtering,
  role toggle, employer/location/duration filters, sort, persistent shortlist.
- Added manifest, install icons, service worker, and consistent data-pair cache.
- 46 local pytest cases pass. HTTP 200 verified for every page, module, worker,
  manifest, and data file. JavaScript assertion suite added to push CI.
- Browser execution remains unverified: Node absent and local Edge failed to
  initialize in the sandbox. Browser runner and manual QA documented in README.
- This phase is not yet committed or published. Intended commits: website,
  PWA/offline assets, then tests/documentation.

## Publication authorization and preparation
The user approved publishing. A GitHub Pages deployment workflow and selected-file
artifact builder are implemented; 47 local Python tests pass. Network restrictions
still block GitHub operations from this session. Repository creation/push, hosted
tests, real daily Issues, Pages deployment, and verified public URLs are pending.
