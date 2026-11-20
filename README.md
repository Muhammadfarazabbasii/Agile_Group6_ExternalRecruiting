# Group 6: External Recruiting

Sprint 1, US-01: Maintain Role Catalogue (role categories, roles, seniority levels).

- Backend: Python, FastAPI, SQLAlchemy, SQLite (file `backend/group6.db`, created automatically)
- Frontend: React + Vite
- API: `openapi.json` and `API.md` (live at http://localhost:8000/docs while the backend runs)

## What you need first

- Python 3.12 or newer (tested on 3.13, packages also have Windows builds for 3.15)
- Node.js LTS (nodejs.org)

Check in a terminal: `python --version` and `node --version`.

## 1. Start the backend (terminal 1)

```
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Use `python -m uvicorn` (not just `uvicorn`). On Windows the plain `uvicorn` command is often not found.

When you see `Uvicorn running on http://127.0.0.1:8000`, open http://localhost:8000/docs.
Leave this terminal open.

Optional: use a virtual environment so packages stay inside the project
(`python -m venv .venv`, then `.venv\Scripts\activate.bat` on Windows or `source .venv/bin/activate` on Mac/Linux, then the pip command again).
It is not required.

## 2. Start the frontend (terminal 2)

Open a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Use the "Logged in as" dropdown to switch between
Sourcing Manager (can edit) and Hiring Manager (read only).

## 3. Run the tests (optional)

```
cd backend
python -m pytest
```

Expected: `16 passed`.

## Trying the API in the browser (Swagger page)

Open http://localhost:8000/docs. For endpoints that change data, click "Try it out" and type
`SOURCING_MANAGER` into the `x-user-role` field. The default is `HIRING_MANAGER` (read only), which gives 403.

## Common problems

| Problem | Fix |
|---|---|
| `'uvicorn' is not recognized` | Use `python -m uvicorn app.main:app --reload` |
| `Failed building wheel for pyyaml` | Use the current `requirements.txt` (plain `uvicorn`, without `[standard]`) |
| `Microsoft Visual C++ 14.0 or greater is required` | A package has no ready-made build for your Python version. Install Python 3.12 and repeat |
| Frontend shows "Cannot reach the backend" | Terminal 1 is not running, or not on port 8000 |
| Port 8000 already in use | Close the other program, or start with `--port 8001` and change the port in `frontend/vite.config.js` |
| Want a clean database | Stop the backend and delete `backend/group6.db` |

## How the pieces fit

```
Browser (React)  --/api calls-->  FastAPI (Python)  --SQL-->  SQLite file
```

| Acceptance criterion | Where |
|---|---|
| Create, edit, deactivate categories and roles | `backend/app/routers/catalogue.py`, screen in `frontend/src/App.jsx` |
| Seniority levels fixed: JUNIOR, SENIOR, EXPERT | `backend/app/seed.py`, `GET /api/seniority-levels` |
| Deactivated roles cannot be used in new requests | `GET /api/roles?active=true` and `GET /api/catalogue` return active entries only |
| Audit trail (who, when, what) | table `audit_log`, `GET /api/audit-log` |
| Only Sourcing Manager can change | `backend/app/auth.py` (development stand-in, not real login) |
| Catalogue available for other groups | `GET /api/catalogue` |

## Known limits (next steps)

- Login is a stand-in (headers). Replace with real authentication later.
- SQLite is for development. For the cloud, set `DATABASE_URL` to PostgreSQL.
- No Dockerfile or CI pipeline yet (Sprint 2).

## Rules from the course

- Never commit secrets or `.env` files.
- Log every AI use in `AI_USAGE.md` and be able to explain every line you hand in.
