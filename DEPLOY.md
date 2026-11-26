# Deploy with Render and Neon (free, about 30 minutes)

The code and settings in this repository are already prepared. You only need to create the accounts and connect them.

```
Browser --> Render static site (React) --/api/*--> Render web service (FastAPI) --> Neon Postgres
```

## Step 1: Push the repository to GitHub

```
git add .
git commit -m "Prepare Render and Neon deployment, new interface styles

AI-Assisted: Claude Sonnet 5.5, deployment setup and CSS, reviewed by the team"
git push
```

## Step 2: Create the Neon database

1. Go to neon.com and sign up (GitHub login works).
2. Create a project named `group6`, region **AWS Europe (Frankfurt)**.
3. Click **Connect** and copy the connection string. It looks like
   `postgresql://user:password@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`
4. It contains the password. Never commit it, never paste it into chat or AI tools.

## Step 3: Deploy on Render

1. Go to render.com, sign up and connect your GitHub account.
2. **New**, then **Blueprint**, choose this repository and the branch you push to (Render deploys that branch), click **Connect**.
3. Render reads `render.yaml` and asks for two values:
   - `DATABASE_URL`: paste the Neon string from step 2.
   - `GROUP7_BASE_URL`: Group 7's cloud address ending in `/api/v1`, or leave empty for now.
4. Click **Apply**. Keep both services on the **Free** plan. The first build takes a few minutes.

## Step 4: Check the backend address

1. Open the service `group6-backend` and copy its URL (for example `https://group6-backend.onrender.com`).
2. If it differs from the one in `render.yaml` (`destination` of the `/api/*` rewrite), change it there and push again. Render redeploys the frontend. (Alternative: change it in the frontend service under Redirects/Rewrites.)

## Step 5: Test

1. `<backend URL>/health` shows `{"status":"ok"}`.
2. `<backend URL>/health/db` shows `database reachable` (checks Neon).
3. `<backend URL>/docs` shows the Swagger page.
4. Open the frontend URL, add a role category and a supplier, reload: the data must still be there.
5. In Neon, open **Tables** and see the same data.

## Step 6: Tell the other groups

Send them the **backend** URL, for example `<backend URL>/api/catalogue`. Update the base URL in `API.md`.
When Group 7 is online, set `GROUP7_BASE_URL` in Render (service, **Environment**). Render restarts the service.

## Keep the backend awake for a demo (optional)

The free backend sleeps after 15 minutes. Open `<backend URL>/health` one minute before a demo, or let a free monitor (uptimerobot.com, cron-job.org) call `<backend URL>/health` every 10 minutes.
Always use `/health`, never `/health/db`: a call that touches the database keeps Neon awake and uses up its free compute hours.

## Things to remember

- Every `git push` to the deployed branch redeploys automatically.
- Tables are not migrated. For a new column, empty the Neon database (Neon SQL Editor: `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) and restart the backend. Tables are created again at start.
- Security: the role header (`X-User-Role`) is a development stand-in. Anyone who knows the URL can change data. Use only test data and say so in the report.
- The first request after a pause is slow (Render about a minute, Neon about a second).
- Free plans can change. Check the current Render and Neon terms before you rely on them.

## If something goes wrong

| Problem | Fix |
|---|---|
| Build fails on `psycopg` | `PYTHON_VERSION` must be `3.13.5` (see `render.yaml`). psycopg is skipped on Python 3.15 locally on purpose |
| `could not connect` or SSL error | The Neon string must end with `?sslmode=require`. Copy it again without spaces |
| Frontend shows "Cannot reach the backend" | Backend is asleep (wait a minute) or the rewrite destination in step 4 is wrong |
| `/api/...` returns the web page instead of JSON | The `/api/*` rewrite is missing or comes after `/*` |
| Group 7 take-over returns 502 | `GROUP7_BASE_URL` is empty or Group 7 is not online |
| Data is gone after a restart | `DATABASE_URL` is not set, so the backend uses a local SQLite file. Set it in Render |
