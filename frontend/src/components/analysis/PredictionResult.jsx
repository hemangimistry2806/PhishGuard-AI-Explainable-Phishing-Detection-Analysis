import { AlertTriangle, CheckCircle2, FileText, ShieldQuestion } from "lucide-react";
import { motion } from "framer-motion";
import Button from "../common/Button.jsx";

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

export default function PredictionResult({ result, sample, explanation, onExplain, explaining }) {
  if (!result) return null;

  const isPhishing = result.label === "Phishing" || result.prediction === 1;

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
          {isPhishing ? <AlertTriangle size={28} /> : <CheckCircle2 size={28} />}
        </span>
        <div>
          <span>Backend prediction</span>
          <h2>{result.label}</h2>
          <p>{sample?.url}</p>
        </div>
      </div>

      <div className="probability-grid">
        <div className="probability-row">
          <span>Phishing probability</span>
          <strong>{pct(result.phishing_probability)}</strong>
          <div className="meter"><span className="meter-danger" style={{ width: pct(result.phishing_probability) }} /></div>
        </div>
        <div className="probability-row">
          <span>Legitimate probability</span>
          <strong>{pct(result.legitimate_probability)}</strong>
          <div className="meter"><span className="meter-success" style={{ width: pct(result.legitimate_probability) }} /></div>
        </div>
      </div>

      <div className="result-actions">
        <Button icon={ShieldQuestion} loading={explaining} onClick={onExplain}>
          {explaining ? "Generating explanation..." : "Generate explanation"}
        </Button>
      </div>

      {explanation ? (
        <motion.div className="explanation-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="section-title">
            <span><FileText size={17} /> Explanation</span>
            <small>{explanation.shap_features?.length || 0} SHAP features</small>
          </div>
          {explanation.llm_explanation ? <p>{explanation.llm_explanation}</p> : <p>No LLM explanation is configured for this run.</p>}
          {Array.isArray(explanation.shap_features) && explanation.shap_features.length > 0 ? (
            <div className="feature-list">
              {explanation.shap_features.slice(0, 6).map((item) => (
                <div className="feature-row" key={`${item.feature}-${item.shap_value}`}>
                  <span>{item.feature}</span>
                  <code>{Number(item.shap_value).toFixed(4)}</code>
                </div>
              ))}
            </div>
          ) : null}
        </motion.div>
      ) : null}
    </motion.section>
  );
}
