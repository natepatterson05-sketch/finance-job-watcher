# Validation and commit status

## Phase 1
- Python 3.14.4 and project virtual environment work.
- Live verification: 2026-11-16T03:58:08.470440Z, performed by the user from
  regular PowerShell because this session blocks outbound shell HTTPS.
- 21 successful Greenhouse employer boards, 3,787 postings, 111 finance-related
  titles. Largest accepted board: Stripe, 785 jobs.
- Block failed title/HTTPS URL validation; HubSpot returned HTTP 404. Neither
  is in config/sources.json, and neither wrote a raw file.
- Replaying the real raw snapshots reproduced history.csv byte for byte.
- Three local commits verified: d08c94a (plan), a0e79c6 (pipeline and data),
  222609b (tests and documentation). The user created them outside the sandbox.
- One distinct raw-data UTC date exists. At least seven distinct successful
  committed daily runs are required by the assignment.

## Phase 2
- Added tests.yml (push/PR/manual) and daily.yml (12:23 UTC/manual).
- Added explicit-publish daily Issue module; default preview makes no network call.
- Pagination, idempotent reruns, baseline exclusions, no-change reports, large
  reports, managed comment cleanup, and failure ordering covered offline.
- Latest suite: 38 passed in 0.33s on Windows/Python 3.14.4.
- Real-data local report preview completed without contacting GitHub.
- git diff --check passed; Git emitted only line-ending conversion warnings.
- Phase 2 has not been committed, pushed, or executed on GitHub. Hosted Linux
  matrix and workflow execution remain unverified. No GitHub remote is configured.
- README badge is an explicit OWNER/REPOSITORY template pending repository URL.
- Intended local commits: (1) Issue publisher and workflows; (2) tests/docs.

## Remaining
- Create Phase 2 local commits; this session cannot write to .git.
- Repository selection and approval before any push or Issue publication.
- Confirm hosted workflows after approval and activation.
- Today/Browse/Market website, six browser-calculated charts, installable PWA,
  offline caching, and submission file remain later phases.

## Website/PWA local validation
- Added Today/Browse/Market, browser metrics/charts, shortlist, manifest/icons,
  service worker, and paired data cache. All assets served with HTTP 200 locally.
- 46 pytest cases passed in 0.38s, including eight new site integrity checks.
- Metric assertion suite is written and wired into push CI; not executed locally
  because Node is absent. Edge headless startup exited 2147483651 before rendering
  due to sandbox/system initialization errors. No screenshot or browser success
  is claimed. Browser manual checks remain necessary (see README).
- Local HTTP server was used only for checks and stopped after validation.
- No push, Issue publication, Pages configuration, or external deployment.

## Approved GitHub publication preparation
- The user approved publication. Added pages.yml with default-branch push/manual
  and successful-daily workflow_run triggers, so bot data commits refresh Pages.
- Added selected-file artifact staging and an artifact integrity test.
- Latest local pytest: 47 passed in 0.33s; staging produced 14 public files.
- GitHub CLI is installed and reports configured account natepatterson05-sketch,
  but API requests fail with sandbox socket permission errors. Authentication
  cannot be verified here. No remote, repository, deployment, or live Issue has
  been created by this session. GitHub plugin was suggested, not connected.
- Publication changes still require a local commit and a working GitHub
  connection. Hosted execution, JS tests, offline/install QA, badge URL, seven
  daily successes, and the final submission file remain to verify or complete.
