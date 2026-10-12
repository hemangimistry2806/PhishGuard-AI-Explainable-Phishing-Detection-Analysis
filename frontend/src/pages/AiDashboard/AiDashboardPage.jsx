import { useEffect, useState } from "react";
import { Activity, BrainCircuit, CheckCircle2, Cpu, Database, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import PageHeader from "../../components/common/PageHeader.jsx";
import { api } from "../../services/api.js";

export default function AiDashboardPage() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refreshData();
  }, []);

  function refreshData() {
    setLoading(true);
    Promise.allSettled([api.checkHealth(), api.getFeedbackStats()]).then(
      ([healthRes, statsRes]) => {
        setHealth(healthRes.status === "fulfilled" ? healthRes.value : null);
        setStats(statsRes.status === "fulfilled" ? statsRes.value : null);
        setLoading(false);
      }
    );
  }

  const isOnline = health && health.status === "ok";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="AI System Telemetry"
        title="AI Dashboard"
        description="Real operational status and evaluation metrics verified against live PhishGuard-AI backend endpoints."
      >
        <button
          type="button"
          className="refresh-btn"
          onClick={refreshData}
          disabled={loading}
          title="Refresh telemetry"
          aria-label="Refresh telemetry data"
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
          <span>{loading ? "Checking..." : "Refresh Status"}</span>
        </button>
      </PageHeader>

      <div className="real-metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon-wrap">
              {isOnline ? <CheckCircle2 size={18} className="text-success" /> : <XCircle size={18} className="text-danger" />}
            </span>
            <span className="metric-title">Backend API Health</span>
          </div>
          <strong className="metric-value">{isOnline ? "Online" : "Unreachable"}</strong>
          <small className="metric-sub">{health?.service || "Connection failed"}</small>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon-wrap">
              <Cpu size={18} className="text-accent" />
            </span>
            <span className="metric-title">Active ML Model</span>
          </div>
          <strong className="metric-value">XGBoost</strong>
          <small className="metric-sub">50 PhiUSIIL features</small>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon-wrap">
              <BrainCircuit size={18} className="text-accent" />
            </span>
            <span className="metric-title">Explainability Engine</span>
          </div>
          <strong className="metric-value">TreeExplainer</strong>
          <small className="metric-sub">SHAP log-odds attribution</small>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon-wrap">
              <Database size={18} className="text-accent" />
            </span>
            <span className="metric-title">User Feedback Count</span>
          </div>
          <strong className="metric-value">
            {stats !== null ? stats.total_feedback : "—"}
          </strong>
          <small className="metric-sub">
            {stats !== null
              ? `${stats.correct_predictions} marked correct (${((stats.accuracy_rate || 0) * 100).toFixed(1)}%)`
              : "Feedback endpoint unreachable"}
          </small>
        </div>
      </div>

      <div className="compact-empty-state">
        <Activity size={20} className="empty-state-icon" />
        <div>
          <h4>Request-Level Telemetry Not Implemented</h4>
          <p>
            The backend does not store historical prediction volumes or request latency streams. Only live health checks and feedback evaluation totals are recorded.
          </p>
        </div>
      </div>
    </div>
  );
}
