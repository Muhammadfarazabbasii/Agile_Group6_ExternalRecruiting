# Deploying Group 6 to the cloud (Sprint 2)

Plan: **Azure** for the real deployment (student credit), **Render** as an optional quick first test and fallback.
The platform choice is a team decision. Button names in the portals change from time to time, so follow the meaning, not the exact words.

## What the code needs (already done in this project)

| Setting | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | backend | Database address. Empty = SQLite file (local). For the cloud use the PostgreSQL address. `postgres://` and `postgresql://` both work |
| `ALLOWED_ORIGINS` | backend | Address(es) of the frontend, separated by commas, no `/` at the end. Without it the browser blocks the calls |
| `GROUP7_BASE_URL` | backend | Address of Group 7's API, for example `https://their-host/api/v1` |
| `PORT` | backend | Set by the platform. The Docker image uses it |
| `VITE_API_BASE_URL` | frontend, **at build time** | Address of our backend, for example `https://g6-api.azurewebsites.net`. Empty = same address (local dev proxy) |

Files: `backend/Dockerfile`, `backend/requirements-cloud.txt` (adds the PostgreSQL driver, only for the cloud), `.github/workflows/ci.yml` (tests and build on every push).
Checked by the assistant: 179 tests pass, the app starts and works against a real PostgreSQL 16 (UTF8 database), CORS allows only the configured origin, the frontend build contains the backend address. **Not checked:** the Docker build (no Docker daemon was available) and the Azure and Render pages themselves.

## Before you start

1. Put the project in one GitHub repository (never commit `.env`, `*.db` or passwords). Check that the CI workflow is green.
2. Decide who owns the Azure subscription. That person gives the other three access (Access control (IAM), role Contributor).
3. Write passwords only into the platform's settings or GitHub Secrets, never into code or chat.

## A. Azure (main path)

1. **Resource group.** In the Azure portal create a resource group, for example `g6-external-recruiting`, in one region close to you (for example Germany West Central). Put everything into it. Deleting it later removes everything.
2. **Budget alert.** Cost Management, create a budget with an alert, so the student credit cannot run out unnoticed.
3. **PostgreSQL.** Create "Azure Database for PostgreSQL flexible server", choose the free-offer size (Burstable B1ms) if the portal shows it. Set an admin user and a strong password. Under networking allow access from Azure services. Create a database `group6`.
   Your address looks like: `postgresql://ADMIN:PASSWORD@SERVER.postgres.database.azure.com:5432/group6?sslmode=require`
4. **Backend (App Service).** Create a Web App: runtime Python 3.12, Linux. A free plan can be used for tests. Check its daily limit before a demo, or use a small paid plan from the student credit.
   - Settings, Environment variables: `DATABASE_URL`, `ALLOWED_ORIGINS` (fill in after step 6), `GROUP7_BASE_URL`.
   - Settings, Configuration, Startup command:
     `pip install -r requirements-cloud.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - If the app does not answer, set the app setting `WEBSITES_PORT` to `8000`.
5. **Deploy the backend.** In the Web App download the "publish profile" and save its content as GitHub secret `AZURE_WEBAPP_PUBLISH_PROFILE`. Also create the repository variable `AZURE_WEBAPP_NAME`. Then run the workflow "Deploy backend to Azure" (Actions tab, Run workflow). It uploads the `backend` folder.
   Check `https://YOUR-APP.azurewebsites.net/health` (answer `{"status":"ok"}`) and `/docs`.
6. **Frontend (Static Web Apps).** Create a Static Web App, connect your GitHub repository, app location `frontend`, output location `dist`. Azure adds a workflow file to the repository. In that file, in the build step, add the environment variable `VITE_API_BASE_URL` with the address of your backend from step 5. Push, wait for the green run, open the address Azure shows.
7. **Allow the frontend.** Go back to the Web App and set `ALLOWED_ORIGINS` to the address of the Static Web App, then restart the Web App.
8. **Test.** Open the frontend, create a category and a role, add a supplier, add a version and rates. Open `/docs` of the backend.
9. **Give Group 7 the backend address** and ask them for theirs. Put theirs into `GROUP7_BASE_URL`. Then run the first real take-over: Suppliers tab, "Take over suppliers from Group 7".

## B. Render (optional quick test)

Render's free plan is good for a first try, not for a long demo: a free web service sleeps after 15 minutes without traffic and wakes in about a minute, and a free PostgreSQL database expires after 30 days.

1. Render dashboard, New, **PostgreSQL** (free). Copy the "Internal Database URL" for the backend.
2. New, **Web Service**, connect the GitHub repository. Language Docker, root directory `backend`. Environment variables: `DATABASE_URL`, `ALLOWED_ORIGINS`, `GROUP7_BASE_URL`.
3. New, **Static Site**, same repository. Root directory `frontend`, build command `npm ci && npm run build`, publish directory `dist`, environment variable `VITE_API_BASE_URL` = address of the web service.
4. Set `ALLOWED_ORIGINS` of the web service to the address of the static site. Check `/health` and the frontend.

## Known limits (tell the team)

- **There is no real login yet.** The role is sent in the header `X-User-Role`, and anyone who knows the address can send `SOURCING_MANAGER`. Use test data only until the authentication concept (also asked by Group 7) is done.
- Tables are created at start and there are no migrations. After a model change on a database that already has tables, the affected tables must be dropped by hand.
- The Azure free web plan has a daily time limit, and the free Render database expires. Plan the demo date.
- SQLite must not be used in the cloud, because its file is lost when the app restarts.

## For the report (cloud chapter)

Platform and why, the parts (frontend, backend, database), the settings above, the pipeline (CI on every push, deploy), the public addresses, screenshots of the running app and of the cloud portal.
