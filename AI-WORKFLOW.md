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

### 4. Two confidently-declared Firefox fixes for the scheduled-outage time picker, neither verified in real Firefox

**What happened** — The user reported being unable to select a time in the Scheduled Outage form in Firefox. Claude proposed and shipped two separate fixes, each presented as resolving the issue:

1. First diagnosis: `.field-input { appearance: none; }` was assumed to break Firefox's `datetime-local` internal time segments. Fix applied: `appearance: auto` scoped to `datetime-local`. "Verified" by reading `getComputedStyle(...).appearance` back as `"auto"` in a Chromium-based browser-automation tool — which only confirms the CSS property changed, not that time selection works in Firefox.
2. The user then supplied a screenshot showing Firefox's native picker is a date-only calendar popup with no time widget at all — a browser-level limitation, not a stylesheet bug. Second fix: split the single `datetime-local` input into separate `type="date"` and `type="time"` inputs. This was again reported as resolving the issue, backed by an elaborate end-to-end test (real POST to a local backend, correct UTC conversion, a suppressed fault). That test verified the timezone-conversion logic and the suppression logic, both real fixes — but it did not verify the Firefox interaction itself, because the only available browser-automation tooling is Chromium-based and cannot drive real Firefox.

**How it was caught** — The user tested in their actual Firefox both times and reported the field still didn't work, despite Claude's confident "fixed" framing after each change.

**Root cause** — Not yet identified. The automated verification in this session structurally cannot exercise Firefox — every "verified" claim about the fix was actually a claim about Chromium behavior, code correctness, or backend behavior, not about the thing the user actually reported. That gap wasn't flagged to the user until this entry.

**Lesson** — When a bug is specific to a browser/environment the available tooling cannot drive, say so plainly and mark any fix as *unverified in the reported environment* rather than "fixed" — the confident framing after change #1 cost a second full round-trip before the real constraint (no Firefox in the toolchain) was made explicit.

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
