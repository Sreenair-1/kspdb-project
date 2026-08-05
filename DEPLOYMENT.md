# Deployment

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Docker | 24.x | Includes Docker Compose V2 (`docker compose`) |
| Git | any | To clone the repo |

No other tools are required for local or Docker-based deployment. Python and Node are only needed if you want to run the backend or frontend outside Docker.

---

## Local deployment (Docker Compose)

### 1. Clone and configure

```bash
git clone <repo-url>
cd <repo>
cp .env.example .env
```

The default `.env` values work out of the box. Edit only if you need different ports or a custom Postgres password.

### 2. Start the stack

```bash
docker compose up --build
```

This pulls `postgres:16-alpine`, builds the `backend` and `frontend` images, runs database migrations, and seeds the synthetic network. First build takes 2–4 minutes depending on your connection speed; subsequent starts are fast.

### 3. Verify

| Check | Expected |
|---|---|
| http://localhost:5173 | Operator console loads; stats strip shows feeders/DTs/poles |
| http://localhost:8000/health | `{"status":"ok","service":"backend","environment":"development"}` |
| http://localhost:8000/ready | `{"status":"ok","database":true}` |
| http://localhost:8000/docs | FastAPI interactive API docs |

### 4. Run a fault injection test

Open http://localhost:5173, select fault type **DT**, pick any transformer from the dropdown, and click **Inject Fault**. A ticket should appear in the Active Tickets table within a second.

---

## Environment variables

All variables have safe defaults. Set them in `.env` or pass them directly to `docker compose`.

| Variable | Default | Required | Description |
|---|---|---|---|
| `APP_ENV` | `development` | No | Passed to the backend as `SETTINGS.app_env` |
| `POSTGRES_DB` | `kspdb` | No | Database name |
| `POSTGRES_USER` | `kspdb` | No | Database user |
| `POSTGRES_PASSWORD` | `kspdb` | No | Database password |
| `DATABASE_URL` | `postgresql://kspdb:kspdb@db:5432/kspdb` | No | Full DSN used by the backend; must match the Postgres variables above |
| `RUN_MIGRATIONS_ON_STARTUP` | `true` | No | Set to `false` if you manage migrations externally. **Known gap:** `docker-compose.yml` does not currently forward this variable to the `backend` service, so it always runs at its default (`true`) under `docker compose up`; it only takes effect when running the backend outside Docker with a local `.env` file. |
| `SEED_REGISTRY_ON_STARTUP` | `true` | No | Set to `false` to start with an empty database. Same known gap as `RUN_MIGRATIONS_ON_STARTUP` — not forwarded by `docker-compose.yml`, so it always seeds under Docker Compose. |
| `BACKEND_PORT` | `8000` | No | Host port for the backend |
| `FRONTEND_PORT` | `5173` | No | Host port for the frontend |
| `VITE_API_BASE_URL` | `http://localhost:8000` | No | Backend URL the browser uses; change to the public backend URL for cloud deployments |
| `ANTHROPIC_API_KEY` | _(empty)_ | No | Anthropic API key for AI fault summaries. Leave blank to disable — the system works fully without it |

To actually disable migrations or seeding under Docker Compose, add the corresponding line to the `backend` service's `environment:` block in `docker-compose.yml` — the setting exists in `app/config.py` and is honoured by `lifespan.py`, it just is not wired through Compose today.

---

## Reset to a clean state

```bash
docker compose down -v
docker compose up --build
```

`-v` removes the `postgres-data` volume, deleting all data. The next start re-seeds from scratch.

---

## Cloud deployment (Render)

The repo includes a `render.yaml` Render Blueprint that provisions all three services — PostgreSQL, backend, and frontend — from a single file.

### Prerequisites

- A [Render](https://render.com) account (free tier works)
- The repository pushed to a public GitHub repo

### Step 1 — Deploy with the Blueprint

1. Go to **Render Dashboard → New → Blueprint**.
2. Connect your GitHub repository.
3. Render detects `render.yaml` and previews three services: `kspdb-db`, `kspdb-backend`, `kspdb-frontend`.
4. Click **Apply**. Render provisions the database and deploys the backend automatically.

### Step 2 — Set the frontend API URL

The frontend bundles `VITE_API_BASE_URL` at build time, so it must be set before the first (or any subsequent) frontend build.

1. In Render Dashboard, open the `kspdb-backend` service.
2. Copy its public URL (e.g. `https://kspdb-backend-n3p2.onrender.com`).
3. Open `kspdb-frontend` → **Environment**.
4. Add `VITE_API_BASE_URL` = the backend URL copied above (no trailing slash).
5. Click **Save Changes**, then **Manual Deploy → Deploy latest commit**.

### Step 3 — Verify

| Check | Expected |
|---|---|
| `https://<backend>.onrender.com/health` | `{"status":"ok","service":"backend","environment":"production"}` |
| `https://<backend>.onrender.com/ready` | `{"status":"ok","database":true}` |
| `https://<frontend>.onrender.com` | Operator console loads with feeders/DTs/poles |

### Cold-start note

Free-tier Render web services sleep after 15 minutes of inactivity. The first request after sleep takes 20–40 seconds. The frontend static site does not sleep.

### Environment variables set by the Blueprint

| Variable | Set by | Value |
|---|---|---|
| `DATABASE_URL` | Blueprint (from DB) | Render internal connection string |
| `APP_ENV` | Blueprint | `production` |
| `VITE_API_BASE_URL` | **You (manual step 2)** | `https://<backend>.onrender.com` |
| `ANTHROPIC_API_KEY` | **You (optional)** | Your Anthropic API key — enables AI fault summaries on tickets |

---

## Troubleshooting

### Backend exits immediately with "Connection refused" or "could not connect to server"

**Symptom** — The backend container starts, tries to connect to Postgres, and exits.

**Cause** — The `db` service is not yet ready when the backend starts, even with `depends_on: condition: service_healthy`. This can happen if the Postgres init takes longer than the healthcheck timeout on slow machines.

**Fix** — Re-run `docker compose up`. The backend has a 10-second retry interval (set in `lifespan.py`). On a second attempt Postgres is already initialized and the connection succeeds. Alternatively, increase the `db` healthcheck `retries` in `docker-compose.yml`.

---

### Port conflict on 5432, 8000, or 5173

**Symptom** — `docker compose up` fails with "port is already allocated".

**Cause** — Another process (a local Postgres, another backend, etc.) is using that port.

**Fix** — Set `BACKEND_PORT`, `FRONTEND_PORT`, or expose Postgres on a different host port:

```bash
BACKEND_PORT=8001 FRONTEND_PORT=5174 docker compose up --build
```

Then open http://localhost:5174 and update `VITE_API_BASE_URL=http://localhost:8001`.

---

### ARM vs x86 image issues

**Symptom** — Backend or frontend image fails to build on Apple Silicon (M1/M2/M3) with an architecture error.

**Cause** — A native binary dependency built for x86.

**Fix** — Set the platform explicitly:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build
```

Or add `platform: linux/amd64` to the relevant service in `docker-compose.yml`.

---

### CORS errors in the browser console

**Symptom** — The frontend loads but API calls fail with "CORS policy" errors.

**Cause** — `VITE_API_BASE_URL` in the frontend container does not match the actual backend origin.

**Fix** — Set `VITE_API_BASE_URL` to the exact origin (scheme + host + port) the browser uses to reach the backend. For local Docker this is `http://localhost:8000`. For a cloud deployment it is the public backend URL.

The backend's CORS middleware (`app/main.py`) currently allows all origins (`allow_origins=["*"]`). If you restrict this, add the frontend origin explicitly.

---

### Migrations fail with "relation already exists"

**Symptom** — Backend logs show a migration error on startup.

**Cause** — The migration file was already partially applied, or a previous run left the schema in an inconsistent state.

**Fix** — Reset the database volume and restart:

```bash
docker compose down -v && docker compose up --build
```

---

### Memory limit on free hosting tiers

**Symptom** — The backend or Postgres is OOM-killed on a free cloud tier.

**Cause** — Free tiers typically limit containers to 256–512 MB RAM. The backend seeding process inserts ~5 000 poles in a single transaction.

**Fix** — Reduce the synthetic network size by setting environment variables (if exposed) or by editing `app/synthetic/generator.py` constants before deploying. The seed runs once; after that, memory usage is low.

---

### Frontend shows "Network error — is the backend running?"

**Symptom** — The operator console loads but shows a network error when injecting a fault.

**Cause** — `VITE_API_BASE_URL` is baked into the frontend bundle at build time. If the backend moved or the variable was not set before building, the browser tries the wrong URL.

**Fix** — Rebuild the frontend image after setting `VITE_API_BASE_URL` correctly:

```bash
docker compose build frontend
docker compose up
```
