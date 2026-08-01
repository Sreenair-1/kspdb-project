# KSPDB Fault Localization

Working system for the Karnataka State Power Distribution Board take-home
assignment.

## Current Status

Milestone 1 is complete: the repository has a Dockerized backend, frontend, and
database foundation. Fault ingestion, simulation, localization, ticket workflow,
and operator workflows will be implemented in later milestones.

## One-Command Start

```bash
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health

## Services

| Service | Purpose |
| --- | --- |
| `frontend` | Operator console shell, built with React and Vite. |
| `backend` | FastAPI service that will host ingest, topology, localization, and ticket APIs. |
| `db` | Postgres database for registry data, telemetry, topology, incidents, and tickets. |

## Review-Score Priorities

The architecture is intentionally arranged around the rubric:

1. Deterministic, testable fault localization will live in backend domain
   modules rather than the UI.
2. Topology and telemetry state will be represented explicitly in Postgres so
   missing topology, duplicate messages, and delayed messages can be explained.
3. The operator console starts as a thin client over backend APIs so later UX can
   focus on incident clarity instead of duplicated business logic.
4. Docker Compose is the default local runtime because it is a pass/fail
   acceptance gate.

