import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Zap,
  Radio,
  RefreshCw,
  Users,
  XCircle,
} from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RegistrySummary {
  feeders: number;
  transformers: number;
  poles: number;
  instrumented_poles: number;
  known_edges: number;
  inferred_edges: number;
}

interface Ticket {
  id: string;
  incident_id: string;
  lifecycle_status: string;
  assigned_crew: string | null;
  ai_summary: string | null;
  created_at: string;
  updated_at: string;
  incident_type: string;
  status: string;
  feeder_id: string | null;
  dt_id: string | null;
  upstream_pole_id: string | null;
  downstream_pole_id: string | null;
  latitude: number | null;
  longitude: number | null;
  pincode: string | null;
  affected_poles: number;
  confidence: number;
  opened_at: string;
}

interface Transformer {
  id: string;
  feeder_id: string;
  capacity_kva: number;
  households_served: number;
}

interface SimResult {
  affected_poles: number;
  injected_events: number;
  new_incidents: number;
  closed_incidents: number;
}

type FaultType = "dt" | "feeder" | "span";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ago`;
}

function confClass(c: number) {
  if (c >= 0.9) return "conf-high";
  if (c >= 0.75) return "conf-med";
  return "conf-low";
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function App() {
  const [summary, setSummary] = useState<RegistrySummary | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [transformers, setTransformers] = useState<Transformer[]>([]);

  const [faultType, setFaultType] = useState<FaultType>("dt");
  const [selectedDt, setSelectedDt] = useState("");
  const [selectedFeeder, setSelectedFeeder] = useState("");
  const [upstreamPole, setUpstreamPole] = useState("");
  const [downstreamPole, setDownstreamPole] = useState("");

  const [simMsg, setSimMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [crewInput, setCrewInput] = useState("Lineman Team A");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ----------- data loading -----------

  const loadTickets = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/v1/tickets`);
      if (res.ok) setTickets((await res.json()).items);
    } catch {
      // silently retry
    }
  }, []);

  useEffect(() => {
    fetch(`${API}/api/v1/registry/summary`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(() => {});

    fetch(`${API}/api/v1/registry/transformers`)
      .then((r) => r.json())
      .then((d: { items: Transformer[] }) => {
        setTransformers(d.items);
        if (d.items.length > 0) {
          setSelectedDt(d.items[0].id);
          const feeders = [...new Set(d.items.map((t) => t.feeder_id))].sort();
          if (feeders.length > 0) setSelectedFeeder(feeders[0]);
        }
      })
      .catch(() => {});

    const initialLoadTimeout = setTimeout(() => {
      void loadTickets();
    }, 0);

    pollRef.current = setInterval(() => {
      void loadTickets();
    }, 5000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      clearTimeout(initialLoadTimeout);
    };
  }, [loadTickets]);

  const feeders = useMemo(
    () => [...new Set(transformers.map((t) => t.feeder_id))].sort(),
    [transformers],
  );

  // ----------- simulator -----------

  async function injectFault() {
    setSimMsg(null);
    setLoading(true);
    try {
      const body: Record<string, string> = { fault_type: faultType };
      if (faultType === "dt") body.dt_id = selectedDt;
      else if (faultType === "feeder") body.feeder_id = selectedFeeder;
      else {
        body.upstream_pole_id = upstreamPole;
        body.downstream_pole_id = downstreamPole;
      }

      const res = await fetch(`${API}/api/v1/simulate/fault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        const d = data as SimResult;
        setSimMsg({
          text: `${d.affected_poles} poles dark — ${d.new_incidents} new ticket(s) created`,
          ok: true,
        });
        await loadTickets();
      } else {
        setSimMsg({ text: data.detail ?? "Injection failed", ok: false });
      }
    } catch {
      setSimMsg({ text: "Network error — is the backend running?", ok: false });
    } finally {
      setLoading(false);
    }
  }

  async function repairFault() {
    setSimMsg(null);
    setLoading(true);
    try {
      const body: Record<string, string> = {};
      if (faultType === "dt") body.dt_id = selectedDt;
      else if (faultType === "feeder") body.feeder_id = selectedFeeder;
      else body.downstream_pole_id = downstreamPole;

      const res = await fetch(`${API}/api/v1/simulate/repair`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        const d = data as SimResult;
        setSimMsg({
          text: `${d.affected_poles} poles restored — ${d.closed_incidents} ticket(s) auto-verified`,
          ok: true,
        });
        await loadTickets();
      } else {
        setSimMsg({ text: data.detail ?? "Repair failed", ok: false });
      }
    } catch {
      setSimMsg({ text: "Network error", ok: false });
    } finally {
      setLoading(false);
    }
  }

  // ----------- ticket actions -----------

  async function acknowledge(id: string) {
    await fetch(`${API}/api/v1/tickets/${id}/acknowledge`, { method: "PATCH" });
    await loadTickets();
  }

  function startAssign(id: string) {
    setAssigningId(id);
    setCrewInput("Lineman Team A");
  }

  async function confirmAssign(id: string) {
    await fetch(`${API}/api/v1/tickets/${id}/assign`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ crew: crewInput }),
    });
    setAssigningId(null);
    await loadTickets();
  }

  async function resolve(id: string) {
    const res = await fetch(`${API}/api/v1/tickets/${id}/resolve`, { method: "PATCH" });
    if (!res.ok) {
      const data = await res.json();
      setActionMsg(data.detail ?? "Cannot resolve");
      setTimeout(() => setActionMsg(null), 5000);
    }
    await loadTickets();
  }

  // ----------- derived state -----------

  const active = tickets.filter((t) =>
    ["detected", "acknowledged", "crew_assigned"].includes(t.lifecycle_status),
  );
  const closed = tickets.filter((t) =>
    ["resolved", "verified", "closed"].includes(t.lifecycle_status),
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <Zap size={18} />
          <span>KSPDB Fault Localization</span>
          <span className="topbar-sub">Subdivision 07 Operator Console</span>
        </div>
        <div className="topbar-actions">
          <span className="live-badge">
            <span className="live-dot" />
            LIVE
          </span>
          <button className="icon-btn" onClick={loadTickets} title="Refresh now">
            <RefreshCw size={14} />
          </button>
        </div>
      </header>

      {/* ── Stats strip ── */}
      {summary && (
        <div className="stats-strip">
          <StatChip label="Feeders" value={summary.feeders} />
          <StatChip label="DTs" value={summary.transformers} />
          <StatChip label="Poles" value={summary.poles.toLocaleString()} />
          <StatChip
            label="Instrumented"
            value={`${Math.round((summary.instrumented_poles / summary.poles) * 100)}%`}
          />
          <StatChip
            label="Known topology"
            value={`${Math.round(
              (summary.known_edges / (summary.known_edges + summary.inferred_edges)) * 100,
            )}%`}
          />
          <StatChip
            label="Active faults"
            value={active.length}
            highlight={active.length > 0}
          />
        </div>
      )}

      {/* ── Content ── */}
      <main className="content">
        {/* Left sidebar */}
        <aside className="sidebar">
          {/* Simulator panel */}
          <div className="panel">
            <div className="panel-head">
              <Radio size={14} />
              Fault Simulator
            </div>

            <label className="field-label">Fault type</label>
            <div className="seg">
              {(["dt", "feeder", "span"] as FaultType[]).map((t) => (
                <button
                  key={t}
                  className={`seg-btn${faultType === t ? " active" : ""}`}
                  onClick={() => setFaultType(t)}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>

            {faultType === "dt" && (
              <>
                <label className="field-label">Distribution Transformer</label>
                <select
                  className="field-select"
                  value={selectedDt}
                  onChange={(e) => setSelectedDt(e.target.value)}
                >
                  {transformers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.id} — {t.feeder_id}
                    </option>
                  ))}
                </select>
              </>
            )}

            {faultType === "feeder" && (
              <>
                <label className="field-label">Feeder</label>
                <select
                  className="field-select"
                  value={selectedFeeder}
                  onChange={(e) => setSelectedFeeder(e.target.value)}
                >
                  {feeders.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </>
            )}

            {faultType === "span" && (
              <>
                <label className="field-label">Upstream pole ID</label>
                <input
                  className="field-input"
                  placeholder="e.g. P-000001"
                  value={upstreamPole}
                  onChange={(e) => setUpstreamPole(e.target.value)}
                />
                <label className="field-label">Downstream pole ID</label>
                <input
                  className="field-input"
                  placeholder="e.g. P-000002"
                  value={downstreamPole}
                  onChange={(e) => setDownstreamPole(e.target.value)}
                />
              </>
            )}

            <div className="sim-actions">
              <button className="btn btn-fault" onClick={injectFault} disabled={loading}>
                <AlertTriangle size={13} />
                Inject Fault
              </button>
              <button className="btn btn-repair" onClick={repairFault} disabled={loading}>
                <CheckCircle size={13} />
                Repair
              </button>
            </div>

            {simMsg && (
              <p className={`sim-msg ${simMsg.ok ? "ok" : "err"}`}>{simMsg.text}</p>
            )}
          </div>

          {/* Closed tickets mini-list */}
          {closed.length > 0 && (
            <div className="panel closed-list">
              <div className="panel-head">
                <CheckCircle size={14} />
                Resolved ({closed.length})
              </div>
              {closed.slice(0, 8).map((t) => (
                <div key={t.id} className="closed-row">
                  <TypeChip type={t.incident_type} />
                  <span className="closed-scope">{t.dt_id ?? t.feeder_id ?? "—"}</span>
                  <StatusChip status={t.lifecycle_status} />
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Main panel */}
        <section className="main-panel">
          {actionMsg && (
            <div className="action-msg">
              <XCircle size={14} />
              {actionMsg}
            </div>
          )}

          {active.length === 0 ? (
            <div className="empty-state">
              <CheckCircle size={44} className="empty-icon" />
              <p>No active faults — all clear</p>
              <p className="empty-sub">
                Use the Fault Simulator on the left to inject a test fault
              </p>
            </div>
          ) : (
            <>
              <div className="section-head">
                <span>Active Tickets</span>
                <span className="count-badge">{active.length}</span>
              </div>

              <div className="table-wrap">
                <table className="ticket-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>DT / Feeder</th>
                      <th>Span boundary</th>
                      <th>Poles</th>
                      <th>Conf.</th>
                      <th>Status</th>
                      <th>Opened</th>
                      <th className="ai-col">AI Situation</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {active.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <TypeChip type={t.incident_type} />
                        </td>
                        <td className="mono">
                          {t.dt_id ?? t.feeder_id ?? "—"}
                          {t.pincode && (
                            <span className="pincode">{t.pincode}</span>
                          )}
                          {t.latitude != null && t.longitude != null && (
                            <a
                              href={`https://www.openstreetmap.org/?mlat=${t.latitude}&mlon=${t.longitude}&zoom=17`}
                              target="_blank"
                              rel="noreferrer"
                              className="geo-link"
                            >
                              {t.latitude.toFixed(4)}, {t.longitude.toFixed(4)}
                            </a>
                          )}
                        </td>
                        <td className="mono small">
                          {t.upstream_pole_id && t.downstream_pole_id
                            ? `${t.upstream_pole_id} → ${t.downstream_pole_id}`
                            : "—"}
                        </td>
                        <td className="num">{t.affected_poles}</td>
                        <td>
                          <span className={`conf ${confClass(t.confidence)}`}>
                            {Math.round(t.confidence * 100)}%
                          </span>
                        </td>
                        <td>
                          <StatusChip status={t.lifecycle_status} />
                          {t.assigned_crew && (
                            <span className="crew-tag">{t.assigned_crew}</span>
                          )}
                        </td>
                        <td className="time">{timeAgo(t.opened_at)}</td>
                        <td className="ai-col">
                          {t.ai_summary ? (
                            <span
                              className="ai-note"
                              title={t.ai_summary}
                            >
                              {t.ai_summary.length > 80
                                ? t.ai_summary.slice(0, 80) + "…"
                                : t.ai_summary}
                            </span>
                          ) : (
                            <span className="ai-note-empty">—</span>
                          )}
                        </td>
                        <td>
                          <div className="action-group">
                            {t.lifecycle_status === "detected" && (
                              <button
                                className="act-btn"
                                onClick={() => acknowledge(t.id)}
                              >
                                Ack
                              </button>
                            )}
                            {["detected", "acknowledged"].includes(
                              t.lifecycle_status,
                            ) &&
                              (assigningId === t.id ? (
                                <span className="assign-inline">
                                  <input
                                    className="assign-input"
                                    value={crewInput}
                                    onChange={(e) => setCrewInput(e.target.value)}
                                    autoFocus
                                    onKeyDown={(e) =>
                                      e.key === "Enter" && confirmAssign(t.id)
                                    }
                                  />
                                  <button
                                    className="act-btn ok"
                                    onClick={() => confirmAssign(t.id)}
                                  >
                                    ✓
                                  </button>
                                  <button
                                    className="act-btn"
                                    onClick={() => setAssigningId(null)}
                                  >
                                    ✕
                                  </button>
                                </span>
                              ) : (
                                <button
                                  className="act-btn"
                                  onClick={() => startAssign(t.id)}
                                >
                                  <Users size={11} /> Assign
                                </button>
                              ))}
                            {t.lifecycle_status !== "detected" && (
                              <button
                                className="act-btn resolve"
                                onClick={() => resolve(t.id)}
                              >
                                Resolve
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatChip({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className={`stat-chip${highlight ? " stat-highlight" : ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

function TypeChip({ type }: { type: string }) {
  return <span className={`type-chip type-${type}`}>{type}</span>;
}

function StatusChip({ status }: { status: string }) {
  const display = status.replace(/_/g, " ");
  const cls = status.replace(/_/g, "-");
  return <span className={`status-chip status-${cls}`}>{display}</span>;
}
