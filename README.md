# Group 6: External Recruiting

Sprint 1 so far:
- US-01 Maintain Role Catalogue (role categories, roles, seniority levels)
- US-02 Manage Suppliers and Framework Contracts, including taking over suppliers and contracts from Group 7 (Expert Supplier)
- US-03 Negotiate Contract Versions (one version per negotiation round, price limits per role and level, one ACTIVE version, comparison)

- Backend: Python, FastAPI, SQLAlchemy, SQLite (file `backend/group6.db`, created automatically)
- Frontend: React + Vite
- API: `openapi.json` and `API.md` (live at http://localhost:8000/docs while the backend runs)
- Interface draft for the next stories: `openapi-draft-us06-us07.yaml`

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
Leave this terminal open. New tables (for example the supplier tables and the version tables) are created automatically at start.

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

Open http://localhost:5173. There are two tabs: "Role catalogue" (US-01) and "Suppliers and contracts" (US-02, with the versions of US-03).
Use the "Logged in as" dropdown to switch between Sourcing Manager (can edit) and Hiring Manager (read only).

## 3. Run the tests (optional)

```
cd backend
python -m pytest
```

Expected: `130 passed` (16 for US-01, 29 for US-02, 30 for the Group 7 take-over, 49 for US-03, 6 for the audit change feed). The tests use a fake Group 7, no real connection is needed.

## Try US-02 by hand

1. Open the "Suppliers and contracts" tab as Sourcing Manager.
2. Add a supplier, for example `TechCorp`. It shows "No framework contract", so it cannot receive requests.
3. Click Open, add a contract with status Active and dates that include today. The supplier now shows "Yes".
4. Add another supplier with a contract that ended in the past. It shows EXPIRED without anyone changing it.
5. Check the audit trail at the bottom: every step is listed with user and time.
6. Switch to Hiring Manager: you can read everything, but there are no buttons to change data.

### Take over suppliers from Group 7

Group 7 gave us their API contract (`docs/group7/openapi.yaml`). Their IDs are text like `sup-01` and `fc-2027`, and we use them unchanged.
1. Group 7's API must be running. Default address `http://localhost:8080/api/v1`. For another address set the variable before starting the backend: Windows `set GROUP7_BASE_URL=http://host:port/api/v1`, Mac/Linux `export GROUP7_BASE_URL=...`. On Render, set `GROUP7_BASE_URL` in the service's environment variables.
2. In the Suppliers tab click "Take over suppliers from Group 7". You see their suppliers and framework contracts and how we would register each one.
3. Tick suppliers, click "Take over". Existing suppliers and contracts are never changed, so you can repeat it safely.
4. If Group 7 is not running you see the message "Group 7 API is not reachable" (HTTP 502). Nothing is changed.

## Try US-03 by hand

1. Sourcing Manager, Suppliers tab: open a supplier, click "Versions" on a framework contract.
2. Tick "Copy rates and travel cap of version N" and click "Create version". The new version is a copy of the previous one, as a starting point.
3. Click "Rates" on the new version, then "Edit rates". Change a rate, add a role and level, save. Duplicate role and level pairs are refused.
4. Click "Start negotiation", then "Activate". The previously active version becomes SUPERSEDED. Confirm the message.
5. Under "Compare versions" pick two versions: rates that were added, removed or changed are shown with the difference.
6. Switch to Hiring Manager: you can open the rates and compare, but there are no buttons to change anything.
7. The audit trail lists each change, for example "version 3 superseded" and "UPDATE: rates saved".

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
| A table has a new column after `git pull` | Tables are not migrated yet. Stop the backend, delete `backend/group6.db`, start again. (US-03 only adds new tables, so existing data can stay) |

## How the pieces fit

```
Browser (React)  --/api calls-->  FastAPI (Python)  --SQL-->  SQLite file
```

Where things live (a new story adds files, it does not create new folders):

```
backend/app/
  main.py                 one line per router
  models.py               database tables
  audit.py                audit trail helper (all stories)
  auth.py                 role check (development stand-in)
  contract_rules.py       contract status and "can receive requests" rule (US-02, reused by US-07)
  version_rules.py        version status moves and "can be edited" rule (US-03), no database, unit tested
  routers/catalogue.py    US-01 endpoints
  routers/suppliers.py    US-02 endpoints
  routers/group7.py       US-02 preview and take-over from Group 7
  routers/versions.py     US-03 endpoints: versions, rates, status, comparison
  group7_client.py        reads Group 7's REST API and maps their statuses to ours
  schemas_group7.py       shapes for the Group 7 endpoints
  schemas_versions.py     shapes for versions, rates and comparison
backend/tests/            one test file per story (test_group7.py: take-over with a fake Group 7;
                          test_versions.py: status rules, one ACTIVE version, blocked edits, roles)
docs/group7/              Group 7's API contract (openapi.yaml, openapi.json) and their examples
frontend/src/
  App.jsx                 header, user switch, tabs (one line per page)
  api.js                  all backend calls
  pages/Catalogue.jsx     US-01 screen
  pages/Suppliers.jsx     US-02 screen (supplier detail shows the versions of each contract)
  components/ContractVersions.jsx   US-03 panel: versions, rates, activation, comparison
```

## US-01: acceptance criteria

| Acceptance criterion | Where |
|---|---|
| Create, edit, deactivate categories and roles | `routers/catalogue.py`, `pages/Catalogue.jsx` |
| Seniority levels fixed: JUNIOR, SENIOR, EXPERT | `seed.py`, `GET /api/seniority-levels` |
| Deactivated roles cannot be used in new requests | `GET /api/roles?active=true` and `GET /api/catalogue` return active entries only |
| Audit trail (who, when, what) | table `audit_log`, `GET /api/audit-log` |
| Only Sourcing Manager can change | `auth.py` (development stand-in, not real login) |
| Catalogue available for other groups | `GET /api/catalogue`. We are the only owner of the catalogue; other groups take the role IDs from here (agreed with Group 7) |

## US-02: acceptance criteria

| Acceptance criterion | Where |
|---|---|
| Create and edit a supplier (name, supplier ID, active flag) | `routers/suppliers.py`. The supplier ID is text (`sup-01` style, letters, digits, `. _ : -`, up to 64 characters). It is created by us (a UUID) or taken over from Group 7 unchanged, and it cannot be changed later. The name can be changed. The active flag is switched with deactivate and activate |
| Framework contract with reference, valid from, valid to, status | table `framework_contract`, `/api/framework-contracts`. Optional title. The reference is Group 7's contract ID (for example `fc-2027`) |
| Linked with Group 7 (shared supplier ID) | `routers/group7.py`, `group7_client.py`, screen "Take over suppliers from Group 7" |
| Suppliers without an active framework contract cannot be selected | `contract_rules.py`, field `selectable` and filter `?selectable=true` on `GET /api/suppliers`. US-07 will use the same rule |
| Expired contracts are shown as expired automatically | Status is calculated from the dates on every read (`contract_rules.py`), no job needed |
| Every change is stored in an audit trail | `audit.py`, `GET /api/audit-log?entity=supplier&entity=framework_contract` |
| Only Sourcing Manager can change (checklist: test role permissions) | `auth.py`, tests in `tests/test_suppliers.py` |

## US-03: acceptance criteria

| Acceptance criterion | Where |
|---|---|
| A framework contract can have many contract versions (version number, date, status) | table `contract_version` (`models.py`), `GET` and `POST /api/framework-contracts/{id}/versions`, screen "Versions of ..." |
| Allowed statuses: DRAFT, IN_NEGOTIATION, ACTIVE, SUPERSEDED | `version_rules.py`, column `contract_version.status` |
| Only one version per framework contract can be ACTIVE at a time | `version_rules.py` and the partial unique index `uq_one_active_version_per_contract` (`models.py`). Test: `test_database_refuses_a_second_active_version` |
| Activating a new version sets the previous ACTIVE version to SUPERSEDED | `POST /api/contract-versions/{id}/status`, function `change_status` in `routers/versions.py`. Test: `test_activating_a_new_version_supersedes_the_previous_active_one` |
| Older versions stay readable but cannot be changed | All versions are readable. `PUT /api/contract-versions/{id}/rates` returns 409 for ACTIVE and SUPERSEDED. Tests: `test_active_and_superseded_versions_cannot_be_edited` |
| A new version can copy the rates of the previous version as a starting point | `copy_previous` in `POST /api/framework-contracts/{id}/versions`, function `copy_terms` |

Checklist of the story, and where it is done:
1. Database model for contract version: `models.py` (`ContractVersion`, `ContractRate`)
2. Create version endpoint with copy option: `routers/versions.py`, `create_version`
3. Status transitions and "only one ACTIVE" rule: `version_rules.py`, `change_status`
4. Block edits on ACTIVE and SUPERSEDED versions: `save_rates` in `routers/versions.py`
5. Version list and compare screen: `components/ContractVersions.jsx`, `GET .../versions/compare`
6. Unit tests for status transitions: `tests/test_versions.py`, the first tests (`test_transition_table` and others)
7. Test role permissions: `test_only_sourcing_manager_can_change_versions`, `test_everyone_can_read_versions_and_comparison`

## Decisions we made on our own (please confirm in the team)

US-02:
- A supplier can have several contracts over time, but two active ones must not overlap.
- Both the first and the last valid day count as valid.
- A terminated contract cannot be changed or activated again.
- The supplier ID is the one of Group 7 (`sup-01`). Suppliers we create ourselves get a UUID.
- One Group 7 framework contract (`fc-2027`) has many suppliers. We keep one contract row per supplier, with the same reference. The reference must be unique per supplier, not globally.
- Status mapping at take-over (Group 7 contract status + participation status -> ours): withdrawn -> TERMINATED; invited or rates_submitted -> DRAFT; active participation in a draft or rate_collection contract -> DRAFT; active in an active contract -> ACTIVE; active in an ended contract -> ACTIVE if the end date has passed (then shown as EXPIRED), otherwise TERMINATED. Unknown values -> DRAFT, so they never make a supplier selectable. Group 7 has confirmed this mapping.
- A Group 7 supplier with status inactive is taken over as deactivated. A supplier with the same name but another ID is skipped and reported.

US-03:
- Transitions: DRAFT may go to IN_NEGOTIATION or straight to ACTIVE. IN_NEGOTIATION may go to ACTIVE only (no way back to DRAFT). A person can never set SUPERSEDED. ACTIVE only changes to SUPERSEDED, automatically.
- A terminated framework contract gets no new versions and no version can be activated.
- Copy takes the rates and the travel cap of the latest version. Rates of deactivated roles are left out and reported in the audit trail.
- Rates are maximum daily rates in EUR, one per role and seniority level. The travel surcharge cap is optional and per version.
- `version_date` defaults to today and can be set when the version is created.
- Open question, not implemented: should a supplier only be selectable for US-07 when its framework contract has an ACTIVE version? The acceptance criteria do not say. The rule from US-02 is unchanged for now.

## Group 7 (Expert Supplier): agreed points

Group 7 confirmed these points in their reply:
- Status mapping: as above (confirmed exactly).
- Contracts: one row per supplier with the same contract reference is fine. Their offers carry both `contractId` and `supplierId`, so we match on that pair.
- Participations: always included in the list and in `GET /framework-contracts/{id}`. We read the list only (`group7_client.py`), so there is no extra detail call per contract.
- Naming: camelCase for everything we send to Group 7. When Group 7 calls our API, they use our snake_case as it is. We have not sent anything to Group 7 yet, so no outgoing payload needs changing.
- Role IDs: one owner, our catalogue. Group 7 takes the UUIDs from `GET /api/catalogue`. We send them our `openapi.json`.
- Base URL: configurable with `GROUP7_BASE_URL`, needed because the address changes when we deploy on render.com.

Still open: `/sourcing-requests` and the `RequestSent` event. Group 7 is waiting for our draft.
