# AI usage log (Group 6, External Recruiting)

Course rules (WS 2026/27): every AI use is disclosed, we can explain every line we hand in, no personal data or credentials in prompts, AI output is reviewed and tested.
AI must not decide team matters (priorities, estimates, acceptance) and must not write our report reflection.

Tool for entries 1 to 22: Claude Sonnet 5.5 (model id `claude-sonnet-5-5`), used through the Claude app. The header said this for every entry, but **entries 23 to 27 were made with Claude Haiku 5.5** (model id `claude-haiku-5-5`), also through the Claude app. The team must check which model was used for entries 1 to 22 and correct those rows after review. Entries 1 to 22 have not been changed.

How to read the columns:
- **Result** is filled in by the team after review: Adopted, Adopted with changes, or Rejected. "Pending review" means nobody has decided yet.
- **Verification** says what was actually checked, and by whom. "Checked by the assistant" means the AI ran the check itself. It does not replace the team's own review.

## Log

| # | Date | Purpose | Prompt summary | Result | Verification |
|---|---|---|---|---|---|
| 1 | 10.11.2026 | Draft first user stories (US-01 to US-10) and messages to other groups | Asked for at least 4 stories and a message to each group, in the style of Group 3's message and the Group 7 stories. Gave the course slides | Pending review | Compared with the slides by the assistant. Team review needed |
| 2 | 10.11.2026 | Rework the stories to 12 stories and new messages based on our role and rate model | Gave the model diagram (supplier, contract versions, roles, seniority, maximum daily rate, travel cap) | Pending review | Team review against the model |
| 3 | 10.11.2026 | Explain the seniority level and the model diagram | Asked what the seniority level is and what the picture means | Explanation only, no file used | None needed |
| 4 | 10.11.2026 | Diagram of the model and ERD (8 tables) | Asked for a diagram and the database tables for the model | Pending review | Checked by the assistant that the diagram renders. Team must compare with the model |
| 5 | 10.11.2026 | Technology suggestions (Python/FastAPI, React, PostgreSQL, Docker) and a comparison of custom code, Camunda, Flowable and Pega | Asked which backend, frontend and platform to use. The assistant searched vendor pages for licence facts | Pending team decision. The AI only suggested | Licence facts come from the vendor pages (Camunda, Flowable, Pega). Judgements about difficulty are the AI's opinion and unchecked |
| 6 | 10.11.2026 | Explain what an API is, a beginner roadmap, ways to link groups without Azure | Asked step by step explanations and cloud alternatives | Explanation only | Team to confirm the cloud choice with the professor and the other groups |
| 7 | 10.11.2026 | Acceptance criteria and checklists for all 12 stories (file `Group6_User_Stories_Board.md`) | Gave the Group 7 story format as a template | Pending review | Team review. Estimates and priorities are left to the team |
| 8 | 10.11.2026 | Starter code for US-01: FastAPI backend, React frontend, 16 pytest tests, README | Asked for a Python and React implementation of US-01 | Pending review | Checked by the assistant: 16 tests pass on Python 3.13, frontend builds, API called through the frontend proxy. Not checked in a real browser. Team must read and explain every file |
| 9 | 10.11.2026 | Debug `pip install` errors on Windows with Python 3.15 (pyyaml build error, `uvicorn` not found) | Pasted the error screenshots | Adopted (changed requirements.txt, use `python -m uvicorn`) | Assistant checked with `pip download` that the other packages have Windows builds for Python 3.15. The team ran the fix on their own machine |
| 10 | 20.11.2026 | Update README and requirements.txt, write API.md, regenerate openapi.json | Asked for an updated README for the Python 3.15 setup and the API description | Pending review | 16 tests pass again (checked by the assistant). OpenAPI file generated from the code |
| 11 | 20.11.2026 | Draft OpenAPI interface for US-06 and US-07 and events (file `openapi-draft-us06-us07.yaml`) | Asked for an API draft for Groups 1, 3 and 7 | Pending review. Not implemented, to be agreed with the groups | Validated with `openapi-spec-validator` (OpenAPI 3.1) by the assistant. Content not yet checked with other groups |
| 12 | 20.11.2026 | Advice on Git folders and branches, and a suggested split of stories over 3 sprints | Asked how to structure folders and branches, and how many stories per sprint | Advice only. Sprint plan is a suggestion. The team decides priorities and estimates | Sprint dates taken from the slides by the assistant |
| 13 | 20.11.2026 | Sprint plan page and a table for the Kanban board (artifact) | Asked for the plan as an artifact and as a table | Pending review | Not opened or visually checked by the assistant. Team review. Owners chosen by the team |
| 14 | 20.11.2026 | Draft the reply to Group 5 (HR analytics data questions) | Pasted Group 5's six questions | Pending review | Assistant kept the answers to what exists (only the role catalogue API is implemented). Team must confirm before sending |
| 15 | 20.11.2026 | Draft the reply to Group 3 (capacity gaps and planned experts) | Pasted Group 3's message | Pending review | Consistent with `openapi-draft-us06-us07.yaml`, except two proposals not yet in the yaml: `allocationFte` and `POST /api/requests/{id}/cancel`. Team must confirm before sending |
| 16 | 20.11.2026 | Backend for US-02: tables for supplier and framework contract, contract rules, endpoints, audit helper, 27 tests | Asked for the program for the US-02 story, with acceptance criteria and checklist given. The backend files were already in the project when this step started (dated 20.11.2026 03:11, produced by the assistant in this session) | Pending review | Reviewed and run by the assistant: all 43 tests pass (16 US-01, 27 US-02). Team must read and explain every file |
| 17 | 20.11.2026 | Frontend for US-02: tabs, split of the catalogue page, new Suppliers page (list, detail, contracts, audit trail) | Same request as entry 16 | Pending review | Build passes. Assistant ran a Chromium test with 13 checks (add supplier, contract, EXPIRED status, duplicate error, audit trail, read-only view, phone width) and looked at a screenshot. The test found two bugs, now fixed in both pages: error messages vanished after a reload, and a loading race gave a 403. Team must test by hand too |
| 18 | 20.11.2026 | Update README, API.md and openapi.json for US-02 | Asked for the updated AI usage log, API file and README with the program | Pending review | openapi.json regenerated from the code (26 operations). Statements in README and API.md checked against the code and tests by the assistant (for example both first and last valid day count) |
| 19 | 23.11.2026 | Align US-02 with the API contract of Group 7 (`openapi.yaml`, `examples.md`): text IDs (`sup-01`), contract reference unique per supplier, contract title, 4 changed tests | Attached Group 7's two files and asked to build US-02 according to them | Pending review | 45 tests pass (assistant ran them). Team must confirm the decisions in README (reference per supplier, ID format) with Group 7 |
| 20 | 23.11.2026 | Take-over from Group 7: client (`group7_client.py`), status mapping, endpoints `/api/group7/suppliers` and `/api/group7/import-suppliers`, 29 tests with a fake Group 7 incl. a contract test against their schema (`docs/group7/openapi.json`) | Same request | Pending review | 74 tests pass. Not tested against the real Group 7 server, only a fake one. The status mapping (withdrawn, invited, ended) is our assumption and must be confirmed with Group 7 |
| 21 | 23.11.2026 | Frontend: panel "Take over suppliers from Group 7", contract title field, ID hint | Same request | Pending review | Build passes. Assistant ran a Chromium test against a small fake Group 7 server (preview, take over 2 suppliers, result list, audit trail, contract title) and looked at the screenshot. No JavaScript errors. Team must test by hand with Group 7's real server |
| 22 | 23.11.2026 | Update README, API.md, regenerate `openapi.json` (28 operations), remove `format: uuid` from supplier IDs in `openapi-draft-us06-us07.yaml` | Asked for OpenAPI JSON, AI usage, API and README files | Pending review | Both OpenAPI files validated with `openapi-spec-validator`. Statements checked against code and tests by the assistant |
| 23 | 26.11.2026 | Amend the Group 6 take-over from Group 7: status mapping, one contract row per supplier, participations from the list, camelCase for outgoing data, configurable base URL | Pasted Group 7's answers to our questions and asked to amend the project accordingly | Pending review | Removed the extra detail call per contract. 30 Group 7 tests pass (run by the assistant). Group 7 confirmed the status mapping in their reply. Team must check the decisions in README against Group 7's real server |
| 24 | 26.11.2026 | Backend for US-03: contract version and rate tables, create version with copy option, status rules, one ACTIVE version per contract, blocked edits, comparison endpoint | Asked for the backend of US-03 with the seven steps and acceptance criteria from the story | Pending review | Status rules are pure functions in `version_rules.py`. Live API flow checked by the assistant: copy, supersede, 409 on an edit to a superseded version, 403 for Hiring Manager, comparison rows and travel cap. Team must read and explain every file and decide the open points listed in README |
| 25 | 26.11.2026 | Tests for US-03: transitions, one ACTIVE version (also refused by the database), blocked edits, copy, comparison, role permissions, audit trail | Same request as entry 24 | Pending review | 124 tests pass in total (run by the assistant). The tests were written by the assistant, so the team must check that they test the story and not only the code |
| 26 | 26.11.2026 | Frontend for US-03: version panel, rate editor, start negotiation and activate with confirmation, copy option, compare table | Same request as entry 24 | Pending review | Build passes. Headless Chrome check with 11 checks (create version, edit rates, duplicate role and level refused, activate, supersede, compare, read-only for Hiring Manager). Screenshots saved, not yet reviewed by the team. Some check-script selectors were wrong and were fixed; the app behaviour was confirmed from the server log and the database. Team must test by hand |
| 27 | 26.11.2026 | Regenerate `openapi.json` (34 operations), update API.md and README for US-03 and the Group 7 agreements | Asked for the updated OpenAPI JSON, API file, README and AI usage log | Pending review | `openapi.json` validated with `openapi-spec-validator` (OpenAPI 3.1, 27 paths). Statements in README and API.md checked against code and tests by the assistant |
| 28 | 26.11.2026 | Answer to Group 5 (People Analytics): change feed on the audit log (`after_id`), API docs for polling, regenerated `openapi.json` | Pasted Group 5's preferences (webhooks, snapshot, KPIs, team IDs, date filters) and asked what the project needs to change and what to send back | Pending review | 6 new tests; 130 tests pass in total (run by the assistant). `openapi.json` validated with `openapi-spec-validator`. Scope (feed only, no webhooks, no team IDs, no `updatedSince`) is a team decision that the assistant proposed, not decided. Team must check the answer before sending |

## AI-assisted files in the repository

Mark these in commits with the trailer `AI-Assisted: <model>, <purpose>`, as the course asks. Use the model that was actually used for that change: Claude Sonnet 5.5 for entries 1 to 22, Claude Haiku 5.5 for entries 23 to 27.

| Files | Purpose |
|---|---|
| `backend/` (app, tests, requirements.txt) | US-01, US-02 incl. Group 7 take-over, and US-03 versions (entries 8, 9, 16, 19, 20, 23, 24, 25) |
| `frontend/` (App.jsx, api.js, pages/, components/, styles.css) | US-01, US-02 and US-03 screens (entries 8, 17, 21, 26) |
| `README.md`, `API.md`, `openapi.json` | Run instructions, API description, US-03 and Group 7 notes (entries 8, 10, 18, 22, 27) |
| `openapi-draft-us06-us07.yaml` | Interface draft (entries 11, 22) |
| `docs/group7/` | Files from Group 7 (not ours, only `openapi.json` is a conversion of their yaml, entry 20) |
| `Group6_User_Stories_Board.md` | Stories, acceptance criteria, checklists (entries 1, 2, 7) |

Example commit message:

```
US-01: add role categories endpoint

AI-Assisted: Claude Sonnet 5.5, generated first version, reviewed and changed by hand
```

## Rules for the team

- Add a new row for every further AI use: date, purpose, short prompt summary, then result and verification.
- Fill the "Result" column honestly after review. Do not leave "Pending review" at submission.
- Do not paste personal data, passwords or confidential material into AI tools.
- The report chapter "AI usage and reflection" is written by the team, not by AI.
- Every member must be able to explain the code and text they hand in.
