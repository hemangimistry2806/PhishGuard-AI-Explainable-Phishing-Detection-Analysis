import { useEffect, useState } from "react";
import Swal from "sweetalert2";
import { MessageSquare, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import Button from "../../components/common/Button.jsx";
import EmptyState from "../../components/common/EmptyState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import { api } from "../../services/api.js";

export default function FeedbackPage() {
  const [form, setForm] = useState({ url: "", model_prediction: "Phishing", user_verdict: "Phishing", comment: "" });
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.getFeedbackStats().then(setStats).catch(() => setStats(null));
  }, []);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.url.trim()) {
      await Swal.fire({ icon: "warning", title: "URL Required", text: "Enter the URL associated with the feedback." });
      return;
    }
    if (form.comment.length > 1000) {
      await Swal.fire({ icon: "warning", title: "Comment Too Long", text: "Feedback comments must be 1000 characters or fewer." });
      return;
    }

    setLoading(true);
    try {
      const response = await api.submitFeedback(form.url.trim(), form.model_prediction, form.user_verdict, form.comment.trim());
      await Swal.fire({ icon: "success", title: "Feedback Recorded", text: response.message || "Thank you for your feedback." });
      setForm({ url: "", model_prediction: "Phishing", user_verdict: "Phishing", comment: "" });
      api.getFeedbackStats().then(setStats).catch(() => setStats(null));
    } catch (error) {
      await Swal.fire({ icon: "error", title: "Feedback Failed", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Feedback"
        title="Submit prediction feedback"
        description="The backend includes a real feedback endpoint, so this form sends feedback to the finalized API contract."
      />
      <div className="feedback-grid">
        <form className="panel form-panel" onSubmit={submit}>
          <label className="field-label" htmlFor="feedback-url">Analyzed URL</label>
          <input id="feedback-url" value={form.url} onChange={(event) => update("url", event.target.value)} placeholder="https://example.com" />

          <div className="two-column">
            <label className="field-label">
              Model prediction
              <select value={form.model_prediction} onChange={(event) => update("model_prediction", event.target.value)}>
                <option>Phishing</option>
                <option>Legitimate</option>
              </select>
            </label>
            <label className="field-label">
              Your verdict
              <select value={form.user_verdict} onChange={(event) => update("user_verdict", event.target.value)}>
                <option>Phishing</option>
                <option>Legitimate</option>
              </select>
            </label>
          </div>

          <label className="field-label" htmlFor="feedback-comment">Comment</label>
          <textarea
            id="feedback-comment"
            rows="6"
            value={form.comment}
            onChange={(event) => update("comment", event.target.value)}
            placeholder="Optional context for this prediction"
          />
          <small className="field-help">{form.comment.length}/1000 characters</small>
          <Button icon={Send} loading={loading} className="primary-action" type="submit">
            Submit feedback
          </Button>
        </form>
        <section className="panel">
          <div className="section-title">
            <span><MessageSquare size={17} /> Feedback status</span>
            <small>Backend backed</small>
          </div>
          {stats ? (
            <div className="feedback-stats">
              <div><MessageSquare size={20} /><span>Total</span><strong>{stats.total_feedback}</strong></div>
              <div><ThumbsUp size={20} /><span>Correct</span><strong>{stats.correct_predictions}</strong></div>
              <div><ThumbsDown size={20} /><span>Incorrect</span><strong>{stats.incorrect_predictions}</strong></div>
            </div>
          ) : (
            <EmptyState icon={MessageSquare} title="Feedback stats unavailable" text="The form can still submit when the backend is reachable." />
          )}
        </section>
      </div>
    </div>
  );
}
