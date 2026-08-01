# Decisions

Newest first.

## 2026-08-01: Use Docker Compose as the primary runtime

Chosen: a three-service Compose stack with `frontend`, `backend`, and `db`.

Rejected: a single local script that starts language-specific dev servers.

Why: `docker compose up` from a clean clone is a pass/fail acceptance gate.
Putting Postgres in the default stack also prevents a later gap between local
development and reviewer execution.

Evaluation criteria improved: reproducible deployment, documentation and
reproducibility, architecture and data design.

## 2026-08-01: Use FastAPI for the backend

Chosen: FastAPI with small modules under `services/backend/app`.

Rejected: a frontend-only app with in-browser simulation and localization.

Why: fault localization, telemetry ingestion, deduplication, ticket verification,
and performance measurement belong in a deterministic backend where they can be
unit-tested and explained. Keeping this logic out of the UI directly supports
the highest-weight localization criterion.

Evaluation criteria improved: fault localization, architecture and data design,
engineering craft.

## 2026-08-01: Use React/Vite for the operator console

Chosen: React with Vite for a focused operator UI.

Rejected: a generic admin template at project start.

Why: the assignment rewards product judgment and operator experience. Starting
with a small custom UI keeps the information hierarchy under our control, which
will matter when showing confidence, ambiguity, and ticket state.

Evaluation criteria improved: operator experience, product judgment.

## 2026-08-01: Keep AI out of core localization

Chosen: reserve AI for a later explanatory/operator-support feature if it earns
its keep.

Rejected: using an LLM to identify the fault span.

Why: the rubric explicitly warns that localization should be deterministic,
instant, free, and explainable. A graph algorithm is the right tool for the
live/dark boundary problem.

Evaluation criteria improved: fault localization, product judgment, AI workflow
documentation.

