import { BackendStatus } from "../components/BackendStatus";

export function HomePage() {
  return (
    <main className="page-shell">
      <section className="foundation-card" aria-labelledby="page-title">
        <p className="phase-label">MVP Foundation</p>
        <h1 id="page-title">EchoMind</h1>
        <p className="tagline">Turn conversations into understanding.</p>

        <div className="status-panel">
          <p className="status-label">后端状态</p>
          <div role="status" aria-live="polite">
            <BackendStatus />
          </div>
        </div>
      </section>
    </main>
  );
}
