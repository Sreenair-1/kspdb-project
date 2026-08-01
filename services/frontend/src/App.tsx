import { Activity, Database, Server } from "lucide-react";

import "./styles.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  return (
    <main className="shell">
      <section className="panel" aria-labelledby="page-title">
        <div className="eyebrow">
          <Activity size={18} aria-hidden="true" />
          Milestone 1
        </div>
        <h1 id="page-title">KSPDB Fault Localization</h1>
        <p>
          The operator console foundation is running. Fault ingestion,
          localization, tickets, and simulation will be added in the next
          milestones.
        </p>
        <div className="status-grid" aria-label="System services">
          <div>
            <Server size={20} aria-hidden="true" />
            <span>Backend</span>
            <strong>{apiBaseUrl}</strong>
          </div>
          <div>
            <Database size={20} aria-hidden="true" />
            <span>Database</span>
            <strong>Postgres service</strong>
          </div>
        </div>
      </section>
    </main>
  );
}

export default App;
