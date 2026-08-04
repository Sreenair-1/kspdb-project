# KSPDB Fault Localization

Real-time fault localization system for the Karnataka State Power Distribution Board.

Detects power outages on an LT distribution network, localizes them to feeder-, DT-, or span-level faults, and creates operator tickets that follow a five-step crew-dispatch lifecycle.

---

## One-command start

```bash
git clone <repo> && cd <repo>
docker compose up --build
```

No manual migration or seed step. The backend runs migrations and seeds a synthetic subdivision on first start.

| URL | Purpose |
|---|---|
| http://localhost:5173 | Operator console |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/health | Liveness check |

---

## Public URL

<!-- Replace the line below with the live Render URL after deploying -->
**Live app:** https://kspdb-frontend-13op.onrender.com/

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step cloud hosting instructions.

> **Cold-start note** — the free-tier backend sleeps after 15 minutes of inactivity. Allow up to 40 seconds on first load.

## Demo video

Recording pending.

---

## What the system does

1. **Synthetic network** seeds on startup: 31 feeders, 72 DTs, 5 000 poles, ≈91 % instrumented, ≈60 % of DTs with inferred topology.
2. **Telemetry ingestion** — pole devices send `heartbeat`, `power_lost`, `power_restored`, or `boot` events; the backend deduplicates and applies each one.
3. **Fault detection** — after any state change the `FaultLocalizer` walks each DT's radial tree and finds live/dark boundaries.
4. **Incidents and tickets** — each new fault boundary becomes an incident and a ticket; each closed boundary auto-verifies the ticket.
5. **Operator workflow** — the console lets operators acknowledge, assign a crew, and mark a ticket resolved. The system pushes back (HTTP 409) if dark poles remain.
6. **Scheduled-outage suppression** — faults that fall within a pre-declared maintenance window do not generate tickets.

---

## Services

| Service | Port | Image |
|---|---|---|
| `db` | 5432 | postgres:16-alpine |
| `backend` | 8000 | FastAPI (Python 3.12) |
| `frontend` | 5173 | React + Vite (Node 20) |

---

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness — no DB dependency |
| GET | `/ready` | DB readiness check |
| GET | `/api/v1/registry/summary` | Network topology counts |
| GET | `/api/v1/registry/transformers` | DT list (used by simulator UI) |
| GET | `/api/v1/incidents` | Active/recent incident list |
| GET | `/api/v1/tickets` | All tickets with incident detail |
| PATCH | `/api/v1/tickets/{id}/acknowledge` | Operator acknowledges a ticket |
| PATCH | `/api/v1/tickets/{id}/assign` | Assign crew `{"crew": "..."}` |
| PATCH | `/api/v1/tickets/{id}/resolve` | Mark resolved; 409 if poles still dark |
| POST | `/api/v1/telemetry` | Ingest a real device event |
| POST | `/api/v1/simulate/fault` | Inject a synthetic fault |
| POST | `/api/v1/simulate/repair` | Repair a synthetic fault |

Full schemas are available at `/docs` when the backend is running.

---

## Documents

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Data flow, schema, localization algorithm, API surface, UI decisions |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Prerequisites, commands, environment variables, troubleshooting |
| [DECISIONS.md](DECISIONS.md) | Decision log with rationale, assumptions, and known gaps |
| [AI-WORKFLOW.md](AI-WORKFLOW.md) | AI tools used, delegated vs manual work, failure cases |

---

## Tests

```bash
cd services/backend
pip install -r requirements-dev.txt
pytest
```

28 tests cover the synthetic generator, localization algorithm, telemetry ingestion, fault simulator, and ticket lifecycle.
