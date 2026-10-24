import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  Filter,
  KeyRound,
  MessageSquare,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import { api } from "../../services/api.js";
import Swal from "sweetalert2";

export default function FeedbackAnalyticsSlide() {
  const [stats, setStats] = useState(null);
  const [feedbackList, setFeedbackList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [disagreementsOnly, setDisagreementsOnly] = useState(false);

  // Reviewer credentials state
  const [reviewerKey, setReviewerKey] = useState("phishguard-admin-review-key-2026");
  const [reviewerId, setReviewerId] = useState("admin_auditor");
  const [isReviewerMode, setIsReviewerMode] = useState(false);

  useEffect(() => {
    refreshAll();
  }, [statusFilter, disagreementsOnly]);

  async function refreshAll() {
    setLoading(true);
    try {
      const [sRes, lRes] = await Promise.all([
        api.getFeedbackStats(),
        api.listFeedback({
          status: statusFilter || undefined,
          disagreements_only: disagreementsOnly,
          limit: 30,
        }),
      ]);
      setStats(sRes);
      setFeedbackList(lRes?.records || []);
    } catch {
      // Failed to load
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(feedbackId, newStatus) {
    if (!reviewerKey.trim()) {
      await Swal.fire({
        icon: "warning",
        title: "Reviewer Key Required",
        text: "Please enter a valid Reviewer Secret Key in the reviewer panel.",
      });
      return;
    }

    const { value: notes } = await Swal.fire({
      title: `Confirm ${newStatus.toUpperCase()} Status`,
      input: "text",
      inputLabel: "Audit Reason / Context",
      inputPlaceholder: "e.g. Ground truth confirmed via threat intelligence",
      showCancelButton: true,
    });

    if (notes === undefined) return; // user cancelled

    try {
      await api.reviewFeedback(
        feedbackId,
        {
          verification_status: newStatus,
          reviewer_id: reviewerId,
          review_notes: notes || undefined,
        },
        reviewerKey
      );

      await Swal.fire({
        icon: "success",
        title: "Status Updated",
        text: `Feedback #${feedbackId} is now marked as '${newStatus}'.`,
        timer: 2000,
      });

      refreshAll();
    } catch (err) {
      await Swal.fire({
        icon: "error",
        title: "Review Action Failed",
        text: err.message || "Unauthorized or invalid reviewer key.",
      });
    }
  }

  async function handleExportCandidateData() {
    if (!reviewerKey.trim()) {
      await Swal.fire({
        icon: "warning",
        title: "Reviewer Key Required",
        text: "Authorized reviewer key required to export candidate dataset.",
      });
      return;
    }

    try {
      const data = await api.exportCandidateDataset(reviewerKey);
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `candidate_phishguard_data_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);

      await Swal.fire({
        icon: "success",
        title: "Candidate Dataset Exported",
        text: `Successfully exported ${data.candidate_samples_count} human-verified samples for offline evaluation.`,
      });
    } catch (err) {
      await Swal.fire({
        icon: "error",
        title: "Export Failed",
        text: err.message || "Could not export candidate dataset.",
      });
    }
  }

  return (
    <div className="slide-content">
      {/* Slide Header */}
      <div className="slide-intro">
        <div className="slide-intro-badge">
          <Shield size={14} className="text-accent" />
          <span>Slide 4 of 4 • Community Feedback & Telemetry</span>
        </div>
        <h1 className="slide-title">Feedback Analytics & Review Pipeline</h1>
        <p className="slide-subtitle">
          Real telemetry aggregated from SQLite storage. Analyze user agreements, potential false
          positives/negatives, and inspect candidate training data.
        </p>
      </div>

      {/* Top 4 Metrics Row */}
      <div className="telemetry-grid">
        <div className="telemetry-stat-card">
          <div className="telemetry-icon-box">
            <MessageSquare size={20} className="text-accent" />
          </div>
          <span className="telemetry-label">Total Submissions</span>
          <strong className="telemetry-val">{stats?.total_feedback || 0}</strong>
          <small className="telemetry-sub">Persisted in SQLite</small>
        </div>

        <div className="telemetry-stat-card">
          <div className="telemetry-icon-box">
            <ThumbsUp size={20} className="text-success" />
          </div>
          <span className="telemetry-label">Agreement Rate</span>
          <strong className="telemetry-val">
            {stats && stats.total_feedback > 0 ? `${((stats.agreement_rate || 0) * 100).toFixed(1)}%` : "0.0%"}
          </strong>
          <small className="telemetry-sub">{stats?.correct_predictions || 0} user-agreed predictions</small>
        </div>

        <div className="telemetry-stat-card">
          <div className="telemetry-icon-box">
            <AlertCircle size={20} className="text-warning" />
          </div>
          <span className="telemetry-label">Potential False Positives</span>
          <strong className="telemetry-val">{stats?.potential_false_positives || 0}</strong>
          <small className="telemetry-sub">Model: Phish / User: Legit</small>
        </div>

        <div className="telemetry-stat-card">
          <div className="telemetry-icon-box">
            <ShieldAlert size={20} className="text-danger" />
          </div>
          <span className="telemetry-label">Potential False Negatives</span>
          <strong className="telemetry-val">{stats?.potential_false_negatives || 0}</strong>
          <small className="telemetry-sub">Model: Legit / User: Phish</small>
        </div>
      </div>

      {/* Verification Status Breakdown & Top Domains */}
      <div className="feedback-subgrid">
        <div className="panel verification-breakdown-card">
          <div className="section-title">
            <Clock size={16} className="text-accent" />
            <span>Human Review Lifecycle Status</span>
          </div>
          <div className="status-counts-row">
            <div className="status-box box-pending">
              <span>Pending Audit</span>
              <strong>{stats?.pending_count || 0}</strong>
            </div>
            <div className="status-box box-verified">
              <span>Verified Ground-Truth</span>
              <strong>{stats?.verified_count || 0}</strong>
            </div>
            <div className="status-box box-rejected">
              <span>Rejected / Invalid</span>
              <strong>{stats?.rejected_count || 0}</strong>
            </div>
          </div>
        </div>

        <div className="panel reviewer-panel">
          <div className="section-title">
            <KeyRound size={16} className="text-accent" />
            <span>Reviewer Authorization Controls</span>
            <button
              type="button"
              className="toggle-reviewer-mode-btn"
              onClick={() => setIsReviewerMode(!isReviewerMode)}
            >
              {isReviewerMode ? "Close Panel" : "Auditor Access"}
            </button>
          </div>

          {isReviewerMode ? (
            <div className="reviewer-controls-form">
              <div className="form-group">
                <label>Reviewer Secret Key</label>
                <input
                  type="password"
                  className="form-input"
                  value={reviewerKey}
                  onChange={(e) => setReviewerKey(e.target.value)}
                  placeholder="Enter X-Reviewer-Key..."
                />
              </div>
              <div className="form-group">
                <label>Reviewer ID</label>
                <input
                  type="text"
                  className="form-input"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="e.g. lead_analyst_1"
                />
              </div>
              <button
                type="button"
                className="secondary-btn export-candidate-btn"
                onClick={handleExportCandidateData}
              >
                <Download size={14} />
                <span>Export Verified Candidate Dataset</span>
              </button>
            </div>
          ) : (
            <p className="reviewer-hint-text">
              Authorized security auditors can verify submissions to prepare candidate training sets.
              Click "Auditor Access" to enter credentials.
            </p>
          )}
        </div>
      </div>

      {/* Filterable Submissions Table */}
      <div className="panel feedback-table-panel">
        <div className="feedback-table-header">
          <div>
            <div className="section-title">
              <MessageSquare size={17} className="text-accent" />
              <span>Persisted Feedback Submissions</span>
              <small className="badge-pill badge-neutral">{feedbackList.length} shown</small>
            </div>
            <p className="section-desc">
              All user-submitted verdicts retained across application restarts.
            </p>
          </div>

          <div className="table-filter-controls">
            <select
              className="filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="verified">Verified</option>
              <option value="rejected">Rejected</option>
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={disagreementsOnly}
                onChange={(e) => setDisagreementsOnly(e.target.checked)}
              />
              <span>Disagreements Only</span>
            </label>
            <button
              type="button"
              className="refresh-icon-btn"
              onClick={refreshAll}
              title="Refresh database records"
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} />
            </button>
          </div>
        </div>

        {feedbackList.length > 0 ? (
          <div className="table-responsive-container">
            <table className="feedback-data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Sanitized URL</th>
                  <th>Model Prediction</th>
                  <th>User Verdict</th>
                  <th>Agreement</th>
                  <th>Status</th>
                  <th>Notes</th>
                  {isReviewerMode && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {feedbackList.map((rec) => {
                  const isAgreed = rec.is_agreement;
                  return (
                    <tr key={rec.feedback_id}>
                      <td><code>#{rec.feedback_id}</code></td>
                      <td className="table-url-cell" title={rec.url}>
                        <span>{rec.url}</span>
                      </td>
                      <td>
                        <span className={`badge-pill ${rec.model_prediction === "Phishing" ? "badge-danger" : "badge-success"}`}>
                          {rec.model_prediction}
                        </span>
                      </td>
                      <td>
                        <span className={`badge-pill ${rec.user_verdict === "Phishing" ? "badge-danger" : "badge-success"}`}>
                          {rec.user_verdict}
                        </span>
                      </td>
                      <td>
                        {isAgreed ? (
                          <span className="text-success inline-flex-center gap-1">
                            <CheckCircle2 size={14} /> Agreed
                          </span>
                        ) : (
                          <span className="text-warning inline-flex-center gap-1">
                            <AlertCircle size={14} /> Disagreed
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`badge-pill status-pill-${rec.verification_status}`}>
                          {rec.verification_status}
                        </span>
                      </td>
                      <td className="table-comment-cell">
                        {rec.comment || <span className="text-muted">—</span>}
                      </td>
                      {isReviewerMode && (
                        <td className="table-action-cell">
                          <button
                            type="button"
                            className="btn-mini btn-mini-verify"
                            onClick={() => handleReview(rec.feedback_id, "verified")}
                            title="Mark as Verified ground truth"
                          >
                            Verify
                          </button>
                          <button
                            type="button"
                            className="btn-mini btn-mini-reject"
                            onClick={() => handleReview(rec.feedback_id, "rejected")}
                            title="Mark as Rejected"
                          >
                            Reject
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-feedback-state">
            <MessageSquare size={28} className="text-muted" />
            <p>No feedback records match the current filter criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
}
