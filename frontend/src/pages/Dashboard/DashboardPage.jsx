import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, MessageSquare, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import PageHeader from "../../components/common/PageHeader.jsx";
import { api } from "../../services/api.js";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getFeedbackStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Operations"
        title="Operations & Evaluation"
        description="Review community feedback metrics and access phishing detection workflows."
      />

      <div className="dashboard-content-stack">
        <section className="panel">
          <div className="section-title">
            <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
              <MessageSquare size={17} /> Live User Feedback Evaluation
            </span>
            <small>Backend backed</small>
          </div>

          {loading ? (
            <p className="field-help">Loading feedback evaluation metrics...</p>
          ) : stats && stats.total_feedback > 0 ? (
            <div className="feedback-stats-grid">
              <div className="stat-box">
                <MessageSquare size={20} className="text-accent" />
                <span>Total Submissions</span>
                <strong>{stats.total_feedback}</strong>
              </div>
              <div className="stat-box">
                <ThumbsUp size={20} className="text-success" />
                <span>Verified Correct</span>
                <strong>{stats.correct_predictions}</strong>
              </div>
              <div className="stat-box">
                <ThumbsDown size={20} className="text-danger" />
                <span>Reported Incorrect</span>
                <strong>{stats.incorrect_predictions}</strong>
              </div>
              <div className="stat-box">
                <CheckCircle2 size={20} className="text-accent" />
                <span>User Accuracy Rate</span>
                <strong>{((stats.accuracy_rate || 0) * 100).toFixed(1)}%</strong>
              </div>
            </div>
          ) : (
            <div className="compact-empty-state">
              <MessageSquare size={20} className="empty-state-icon" />
              <div>
                <h4>No User Feedback Recorded Yet</h4>
                <p>
                  User verdicts submitted via the Feedback page will automatically populate real accuracy statistics here.
                </p>
              </div>
            </div>
          )}
        </section>

        <section className="panel action-shortcuts-panel">
          <div className="section-title">
            <span>Quick Workflows</span>
          </div>
          <div className="shortcuts-grid">
            <Link to="/" className="shortcut-card">
              <Search size={20} className="text-accent" />
              <div>
                <strong>Analyze URL</strong>
                <p>Run live feature extraction or benchmark dataset analysis</p>
              </div>
            </Link>
            <Link to="/feedback" className="shortcut-card">
              <MessageSquare size={20} className="text-accent" />
              <div>
                <strong>Submit Feedback</strong>
                <p>Report false positives or confirm accurate model predictions</p>
              </div>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
