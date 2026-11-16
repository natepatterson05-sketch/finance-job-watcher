# Validation and commit status

- Runtime: Python 3.14.4, project virtual environment, dependencies installed.
- Latest pytest: 27 passed in 0.22s.
- Live verification performed by the user from regular PowerShell:
  2026-11-16T03:58:08.470440Z; 21 successful Greenhouse employer boards,
  3,787 postings, 111 finance-related titles. Largest board: Stripe, 785 jobs.
- Block failed title/HTTPS URL validation; HubSpot returned HTTP 404. Neither is
  in config/sources.json. Failed sources have no raw file.
- Replayed real raw snapshots and compared history.csv bytes: identical.
- One distinct raw-data UTC date exists. This is not yet a committed successful
  course run; Git writes are blocked inside this session.
- Latest local staging attempt: cannot create .git/index.lock, permission denied.
- No commits, pushes, or publication performed.

## Intended local commits

1. Plan/scaffold: PLAN.md, .gitignore, pyproject.toml, package __init__.py.
2. Collection/history/data: pipeline.py, cli.py, config/, data/,
   docs/source-verification.json.
3. Tests/documentation: tests/, README.md, docs/validation.md.

Phase 1 functionality is validated; local commits remain. Automation, Issues,
Pages, market charts, and PWA behavior are later phases. At least seven distinct
successful committed daily runs are required by the assignment.
