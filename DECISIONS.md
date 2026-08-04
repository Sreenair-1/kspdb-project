# Decisions

Newest first.

## 2026-08-05: Implement AI natural-language fault summaries (supersedes 2026-08-04 deferral)

Chosen: call `claude-haiku-4-5` via the Anthropic Messages API on each new incident and store the result in `tickets.ai_summary`.

Rejected (now reinstated): shipping without an LLM call after the core ticket lifecycle and test suite were complete.

Why: the remaining rubric weight on the AI workflow criterion justified the implementation once the test suite was stable. The call is fire-and-forget — ticket creation is never blocked. `ANTHROPIC_API_KEY` is optional; omitting it disables the feature with no other change.

Evaluation criteria improved: AI workflow documentation, operator experience.

## 2026-08-04: Operator resolve requires no dark poles in the fault scope

## 2026-08-04: Operator resolve requires no dark poles in the fault scope

Chosen: `PATCH /api/v1/tickets/{id}/resolve` returns HTTP 409 if any pole in the fault scope is still dark in `pole_states`.

Rejected: trusting operator judgement unconditionally, or deferring the check to a separate validation endpoint.

Why: the assignment self-check explicitly lists "Marked a ticket resolved while the poles were still dark — the system pushed back" as a pass/fail item. The pushback must be automatic, not advisory.

Evaluation criteria improved: fault localization, operator experience.

## 2026-08-04: Auto-verify on repair, not on operator action

Chosen: when `run_fault_detection()` finds no fault at a previously-open incident's location, it closes the incident and sets the ticket to `verified` automatically.

Rejected: requiring the operator to click a "verify" button after a repair.

Why: the assignment requires "Repaired a fault — ticket auto-verified from telemetry without me clicking resolved." Auto-verification is driven by the same detection loop that created the ticket, so the same evidence that detected the fault must confirm its absence.

Evaluation criteria improved: fault localization, operator experience.

## 2026-08-04: Run fault detection synchronously in the API request

Chosen: `run_fault_detection()` is called inline in `POST /api/v1/simulate/fault`, `POST /api/v1/simulate/repair`, and `POST /api/v1/telemetry`.

Rejected: a background worker that polls for state changes.

Why: for the demo scenario (simulator on a single machine with a seeded network) synchronous detection is simpler, eliminates polling latency, and keeps the test suite straightforward. The localizer runs in O(N) on ~5 000 poles; measured latency is under 100 ms, well within HTTP response budgets.

Evaluation criteria improved: engineering craft, fault localization.

## 2026-08-04: Ticket lifecycle as five explicit states

Chosen: `detected → acknowledged → crew_assigned → resolved → verified` stored in `tickets.lifecycle_status`.

Rejected: a simpler open/closed model.

Why: the assignment describes a crew-dispatch workflow with acknowledgement, assignment, resolution, and verification as distinct steps. Each transition is independently useful for an operator (acknowledgement prevents double-work; assignment records accountability; resolve vs verify separates "crew says done" from "telemetry confirms done").

Evaluation criteria improved: operator experience, product judgment.

## 2026-08-04: No debounce timer on fault detection

Chosen: run detection on every event that updates pole state.

Rejected: a debounce window (e.g., 30 seconds) to wait for a burst of events to settle before detecting.

Why: the simulator sends all events for a fault synchronously in one API call, so by the time detection runs, all state is consistent. A debounce timer would add complexity and latency with no benefit in the current demo scenario. This is a known gap for production use.

Evaluation criteria affected: noise handling is partially incomplete — see ARCHITECTURE.md.

## 2026-08-01: Seed a deterministic synthetic subdivision on startup

Chosen: generate 31 feeders, 72 DTs, and 5,000 poles when the registry is empty.

Rejected: committing static CSVs or starting with an empty database.

Why: startup seeding is an acceptance gate, and deterministic generation gives
reviewers a working system immediately while keeping test data explainable. The
data keeps the assignment's important proportions: roughly 91% instrumented
poles, roughly 60% missing recorded topology, realistic DT pole-count ranges,
branches, missing PIN codes, old firmware, and independently offline devices.

Evaluation criteria improved: reproducible deployment, architecture and data
design, fault localization, handling missing topology.

## 2026-08-01: Generate inferred topology even when registry ordering is missing

Chosen: for DTs without recorded `seq_on_line` and `parent_pole_id`, leave those
pole registry fields null but populate `topology_edges` with `source =
'inferred'` and lower confidence.

Rejected: leaving missing-topology DTs disconnected until a later survey.

Why: the assignment explicitly says a survey-only answer is insufficient. This
lets the later algorithm produce useful span/range candidates today while the UI
can show lower confidence and explain why.

Evaluation criteria improved: handling missing topology, fault localization,
operator experience, product judgment.

## 2026-08-01: Store raw telemetry separately from latest pole/device state

Chosen: append-only `telemetry_events` plus current-state tables
`pole_states` and `device_states`.

Rejected: only storing latest pole status.

Why: duplicate, stale, delayed, and out-of-order telemetry are central to the
fault localization score. The raw event log preserves auditability, while state
tables keep detection and UI reads fast enough for the performance targets.

Evaluation criteria improved: fault localization, architecture and data design.

## 2026-08-01: Model topology as explicit directed edges

Chosen: `topology_edges` with `source` set to `known` or `inferred` and a
per-edge confidence.

Rejected: relying only on `parent_pole_id` in the pole table.

Why: the assignment's central challenge is the 60% of DTs with missing pole
ordering. A separate edge table lets known and inferred topology coexist and
lets the localization algorithm explain lower confidence instead of hiding
uncertainty.

Evaluation criteria improved: fault localization, handling missing topology,
architecture and data design, operator experience.

## 2026-08-01: Keep migrations in the backend image

Chosen: SQL migrations under `services/backend/app/migrations`, applied by the
backend during startup.

Rejected: a manual migration command.

Why: reviewers must be able to run the full system with `docker compose up`.
Automatic migrations remove a manual step while keeping schema changes explicit
and reviewable.

Evaluation criteria improved: reproducible deployment, documentation and
reproducibility.

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
