import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Button from "../common/Button.jsx";

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

export default function PredictionResult({
  result,
  sample,
  explanation,
  onExplain,
  explaining,
}) {
  const [shapCollapsed, setShapCollapsed] = useState(false);
  const [showAllFeatures, setShowAllFeatures] = useState(false);

  if (!result) return null;

  const isPhishing = result.label
    ? result.label.toLowerCase() === "phishing"
    : result.prediction === 0;

  const confidence = isPhishing
    ? result.phishing_probability
    : result.legitimate_probability;

  const shapFeatures = explanation?.shap_features || [];
  const displayedFeatures = showAllFeatures
    ? shapFeatures
    : shapFeatures.slice(0, 5);

  return (
    <motion.section
      className="panel result-panel"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      aria-live="polite"
    >
      <div className={`verdict-card ${isPhishing ? "danger" : "success"}`}>
        <span className="verdict-icon" aria-hidden="true">
          {isPhishing ? <ShieldAlert size={28} /> : <ShieldCheck size={28} />}
        </span>
        <div className="verdict-details">
          <div className="verdict-meta">
            <span className="verdict-badge">
              {isPhishing ? "High Risk Detected" : "Low Risk / Legitimate"}
            </span>
            <span className="verdict-confidence">
              {pct(confidence)} confidence
            </span>
          </div>
          <h2>{result.label}</h2>
          <code className="verdict-url">{sample?.url}</code>
        </div>
      </div>

      <div className="probability-grid">
        <div className="probability-row">
          <div className="probability-header">
            <span>Phishing risk</span>
            <strong>{pct(result.phishing_probability)}</strong>
          </div>
          <div className="meter">
            <span
              className="meter-danger"
              style={{ width: pct(result.phishing_probability) }}
            />
          </div>
        </div>
        <div className="probability-row">
          <div className="probability-header">
            <span>Legitimate probability</span>
            <strong>{pct(result.legitimate_probability)}</strong>
          </div>
          <div className="meter">
            <span
              className="meter-success"
              style={{ width: pct(result.legitimate_probability) }}
            />
          </div>
        </div>
      </div>

      {result.warnings && result.warnings.length > 0 ? (
        <div className="warning-notice-card" role="alert">
          <div className="warning-notice-header">
            <AlertTriangle size={18} />
            <strong>Live Analysis Warnings & Disclosures</strong>
          </div>
          <ul className="warning-notice-list">
            {result.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
          <p className="warning-notice-disclaimer">
            Notice: URLSimilarityIndex is approximated. Offline dataset benchmark accuracy does not guarantee real-world accuracy on unseen URLs, and live predictions may produce false positives.
          </p>
        </div>
      ) : null}

      {!explanation ? (
        <div className="result-actions">
          <Button
            icon={ShieldQuestion}
            loading={explaining}
            onClick={onExplain}
            className="secondary-action"
          >
            {explaining ? "Computing SHAP values..." : "Generate AI Explanation"}
          </Button>
        </div>
      ) : null}

      {explanation ? (
        <motion.div
          className="explanation-card"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="explanation-header">
            <div className="section-title" style={{ margin: 0 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                <FileText size={17} /> SHAP Feature Explanation
              </span>
              <small>{shapFeatures.length} features analyzed</small>
            </div>
            <button
              type="button"
              className="collapse-toggle-btn"
              onClick={() => setShapCollapsed((prev) => !prev)}
              aria-expanded={!shapCollapsed}
              aria-label={shapCollapsed ? "Expand SHAP explanation" : "Collapse SHAP explanation"}
            >
              <span>{shapCollapsed ? "Show details" : "Collapse"}</span>
              {shapCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>
          </div>

          <AnimatePresence initial={false}>
            {!shapCollapsed ? (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="explanation-body"
              >
                {explanation.llm_explanation ? (
                  <div className="llm-explanation-box">
                    <div className="llm-explanation-header">
                      <Sparkles size={14} />
                      <span>AI Model Reasoning</span>
                    </div>
                    <p>{explanation.llm_explanation}</p>
                  </div>
                ) : (
                  <p className="field-help">No LLM narrative explanation configured for this run.</p>
                )}

                {shapFeatures.length > 0 ? (
                  <div className="feature-section">
                    <span className="field-help">
                      Top feature contributions (SHAP importance value):
                    </span>
                    <div className="feature-list">
                      {displayedFeatures.map((item) => {
                        const val = Number(item.shap_value);
                        const isPositive = val > 0;
                        return (
                          <div
                            className="feature-row"
                            key={`${item.feature}-${item.shap_value}`}
                          >
                            <span className="feature-name">{item.feature}</span>
                            <div className="feature-val-group">
                              <span
                                className={`feature-pill ${
                                  isPositive ? "push-legit" : "push-phish"
                                }`}
                              >
                                {isPositive ? "+Legitimate" : "-Phishing"}
                              </span>
                              <code>{val.toFixed(4)}</code>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {shapFeatures.length > 5 ? (
                      <button
                        type="button"
                        className="show-more-features-btn"
                        onClick={() => setShowAllFeatures((prev) => !prev)}
                      >
                        {showAllFeatures
                          ? "Show top 5 features only"
                          : `Show all ${shapFeatures.length} features`}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
      ) : null}
    </motion.section>
  );
}
