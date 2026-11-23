# DealerOS Reconciliation

A small reconciliation app built with Django REST Framework, SQLite, React, and Vite. It imports the supplied location and ledger CSVs, compares System B with System A's adjusted totals, and returns findings for one organization at a time.

The supplied source files contain 5 locations, 120 System A records, and 121 System B entries. The importer reports reading and saving all of them.

## Requirements

- Python 3.12+ (required by the Django version in `requirements.txt`)
- Node.js 20.19+ or 22.12+
- npm

## Run from a clean clone

Run the backend commands in PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Set-Location backend
python manage.py makemigrations
python manage.py migrate
python manage.py import_data
pytest
python manage.py runserver
```

In a second terminal at the repository root, start the frontend:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://127.0.0.1:5173/`). The API is at `http://127.0.0.1:8000/`; its root redirects to the organizations endpoint. Vite proxies `/api/` requests to Django. The importer reads `backend/data/locations.csv`, `system_a.csv`, and `system_b.csv`; it can be rerun safely.

## What is included

- CSV import into indexed SQLite models, retaining each original row in `raw_data`.
- A tested, database-free comparison function and tenant-scoped API.
- A React table with organization, reason, and numeric value sort controls, live summaries, and expandable details.
- `Decimal` amount parsing, reference normalization, and explicit handling for missing values, orphans, duplicates, and balanced splits.
- Reconciliation policies, including the treatment of `REC-1042` and valid split entries, are recorded in [DECISIONS.md](./DECISIONS.md).

## Deployment

The app can be deployed as two services:
## Live Deployment
- **Frontend (Vercel):** https://frontend-alpha-lovat-27.vercel.app/
- **Backend API (Render):** https://dealeros-g0u5.onrender.com/api/orgs/

- **Render (Django):** Use the repository root as the service root. Build command: `pip install -r requirements.txt && python backend/manage.py collectstatic --noinput && python backend/manage.py migrate && python backend/manage.py import_data`. Start command: `cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`. Set `DJANGO_SECRET_KEY` to a generated secret, `DJANGO_DEBUG=false`, and `CORS_ALLOWED_ORIGINS` to the deployed Vercel origin (comma-separated if there are multiple).
- **Vercel (Vite):** Set the project root directory to `frontend`, use `npm run build` as the build command and `dist` as the output directory. Set `VITE_API_BASE_URL` to the Render service origin, with no trailing slash.

For local development, leave `CORS_ALLOWED_ORIGINS` unset (the development default allows all origins) and the frontend uses `http://127.0.0.1:8000` as its API base URL. The SQLite database is suitable for this seeded assessment demo, not durable production data storage.

## Deliberately not included

Authentication/authorization, pagination, and separate `DATE_MISMATCH` or `LOCATION_MISMATCH` reason codes are out of scope. The API requires an `org` query parameter and scopes database queries by that organization, but it does not authenticate callers. The bundled Django key is development-only; production must set `DJANGO_SECRET_KEY`.

## How I worked with the coding agent

I used the Copilot coding agent to inspect the CSV structure and implement the importer, comparison, API, UI, tests, and documentation. I checked the actual headers and anomalies, verified row counts and stored raw rows, exercised tenant/filter/sort behavior, and ran migrations, tests, and the frontend build. The agent produced most of the code; I reviewed the generated behavior against the source data and revised the parts that failed those checks.

## Follow-up answers

These are drafts based on this work session. Review them and rephrase them in your own words before submitting.

### a. One thing the agent got wrong

The agent first asserted that `REC-1015` had the blank `actor_id`. That test failed: reading the CSV showed the blank belongs to `REC-1050`, and the assertion was corrected. The failed test and direct CSV inspection caught the mistake.

### b. The part I am least confident about

The CSV has one `VOIDED` record, `REC-1019`, and B contains a matching entry. This version treats it like other records because B has no void status and its value/location match. I would confirm with the business owner whether a voided A record should always suppress a B entry.

### c. What I would improve with another day

I would add explicit date and location mismatch findings with dedicated tests. This version preserves dates, ignores date-only differences, and represents cross-location entries as `MISSING_IN_B` and `ORPHAN_IN_B`; explicit reasons could make those cases easier to review.

## API

- `GET /api/orgs/` — available organization IDs.
- `GET /api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH&sort=asc` — tenant-scoped findings; `reason` is optional and `sort` accepts `asc`, `desc`, `value`, or `-value`.
- `GET /api/disagreements/?org=ORG-B&sort=-value` — example descending query.

Blank B values are returned as missing (`MISSING_VALUE_IN_B`) with an empty display cell, never as zero. A balanced split is not a disagreement; an unbalanced multi-entry total is reported as `DUPLICATE_IN_B`.

For example, `REC-1042` is reported as `DUPLICATE_IN_B`: its two System B entries total `225674.12`, while System A's total is `112837.06`.
