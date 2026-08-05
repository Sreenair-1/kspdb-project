# AI Workflow

How AI tools were used across this project.

---

## Tools and their roles

| Tool | Role |
|---|---|
| **Codex (OpenAI)** | Session 1 — architecture design, domain model, Docker/database scaffold, initial synthetic generator |
| **Cursor (Claude backend)** | Session 2 — repository review, gap analysis against the assignment, continued implementation |
| **Claude Code (Sonnet 4.6)** | Sessions 3–4 — telemetry pipeline, fault detection, ticket lifecycle, API tests |

---

## What was delegated vs written by hand

### Delegated wholesale to AI

- Boilerplate FastAPI routing, dependency injection, and Pydantic schema definitions
- Docker Compose file and Dockerfile structure
- SQL migration file (initial schema)
- React component structure and CSS layout
- `pyproject.toml` and `requirements*.txt`

For all of these, the AI produced a working first draft that was reviewed and accepted with minor changes. The patterns are standard and do not contain novel logic.

### AI-assisted with significant manual revision

- **Synthetic generator** (`app/synthetic/generator.py`) — AI produced the skeleton; the pole-count distribution, the 60 % missing-topology rule, and the inferred-edge confidence values were hand-specified to match the assignment brief.
- **FaultLocalizer** (`app/domain/localization.py`) — AI produced the tree-walk structure; the sensor-fault exclusion logic (`_sensor_fault_poles`), the feeder-level check ordering, and the confidence formula were designed manually and refined through test failures.
- **Telemetry deduplication** (`app/telemetry.py`) — AI wrote the `ON CONFLICT DO NOTHING` pattern; the staleness check (comparing `seq` against `device_states.last_seq`) and the confidence split between `power_lost` and `unenergized heartbeat` were added manually.

### Written without AI assistance

- The localization test cases in `tests/test_localization.py` — specifically the six topology fixtures and their expected fault boundaries. These were written by hand because the test had to encode a specific understanding of what "correct" means for each fault type.
- The `_is_scheduled_outage` check ordering (feeder before DT) — a design choice that affects which scope wins when both match.
- The 409 resolve pushback — the decision to query `pole_states` for dark poles in the fault scope before permitting resolution was a product decision, not a mechanical translation.

---

## Cases where AI output was wrong or misleading

### 1. Feeder-level detection triggered too eagerly

**What happened** — In an early version of `FaultLocalizer`, the feeder-level check ran after per-DT analysis. This meant a feeder fault would produce one feeder incident and several DT incidents simultaneously. The AI-generated code did not model the hierarchical exclusion.

**How it was caught** — The test `test_feeder_fault_when_all_dts_are_dark` failed: three tickets were returned instead of one.

**Fix** — The feeder check was moved before the per-DT loop, and a `continue` skips DT analysis when a feeder fault is already found for that feeder.

---

### 2. Staleness logic inverted

**What happened** — In the first AI draft of `process_telemetry_event`, a message was flagged stale if `seq >= last_seq` (greater-than-or-equal). This incorrectly flagged a message with the same sequence number as stale when it was actually a duplicate.

**How it was caught** — The test `test_telemetry_stale_flag_is_propagated` failed. Reading the logic confirmed the condition should be `seq <= last_seq` for staleness and the exact-duplicate case is handled separately by the DB constraint.

**Fix** — Condition changed to `seq <= row["last_seq"]`; duplicates are detected by `ON CONFLICT DO NOTHING` returning no row.

---

### 3. Resolve endpoint accepted a ticket with dark poles

**What happened** — The AI-generated `resolve_ticket` in `db.py` updated `lifecycle_status` unconditionally. The assignment requires the system to push back if dark poles remain in the fault scope.

**How it was caught** — The test `test_resolve_ticket_returns_409_when_poles_still_dark` passed when it should have expected a 409. Manual code review confirmed no check was performed.

**Fix** — `db.resolve_ticket` was updated to query `pole_states` for poles in the fault scope and return `(False, "reason")` if any are still dark. The endpoint converts this to HTTP 409.

---

## Rough proportion of AI-generated code

Approximately **65–70 %** of the final line count was AI-generated (first draft or near-final). The remaining 30–35 % comprises manual logic additions, test cases, and revisions to AI output that was functionally incorrect.

The localization algorithm and the test suite are the highest-value parts of the codebase; both are predominantly hand-written or heavily revised.

---

## Session excerpts considered most effective

### Localization test design (Session 3)

The most productive prompt pattern was: describe a specific topology as a list of poles and edges, state what the expected fault boundary should be, and ask the AI to generate the test fixture in the project's existing test structure. The AI correctly translated topology descriptions into `TopologyPole` / `TopologyEdge` lists but consistently generated wrong expected outputs for edge cases (sensor faults, inferred topology). Reviewing and correcting these expected outputs was how edge-case bugs in the localizer were found. `tests/test_localization.py` now has ten such fixtures, covering span, DT, and feeder faults, sensor-fault exclusion, simultaneous faults, inferred topology, unknown-boundary handling, and affected-pole counting through unknown poles.

### Gap analysis (Session 2)

Asking the AI to read `03-deliverables-and-submission.md` and the current implementation and produce a diff of what was missing was the most efficient use of AI in the project. The output was a prioritized list that matched what the rubric actually weights, which became the Session 3 work plan.
