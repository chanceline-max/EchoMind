import { Link } from "react-router-dom";

import { BackendStatus } from "../components/BackendStatus";

export function HomePage() {
  return (
    <main className="page-shell home-page">
      <section className="foundation-card" aria-labelledby="page-title">
        <p className="phase-label">MVP Import Workflow</p>
        <h1 id="page-title">EchoMind</h1>
        <p className="tagline">Turn conversations into understanding.</p>
        <div className="home-actions">
          <Link className="primary-link" to="/import">导入聊天记录</Link>
          <Link className="secondary-link" to="/conversations">查看会话</Link>
        </div>
        <div className="status-panel">
          <p className="status-label">后端状态</p>
          <div role="status" aria-live="polite"><BackendStatus /></div>
        </div>
      </section>
    </main>
  );
}
