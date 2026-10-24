import { useState } from "react";
import {
  ArrowRight,
  ClipboardPaste,
  Cpu,
  Globe,
  Info,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { SAMPLES } from "../../data/samples/index.js";

export default function UrlAnalysisSlide({
  url,
  onUrlChange,
  onClearUrl,
  selectedSample,
  onSelectSample,
  onAnalyze,
  loading,
  stage,
  inlineStatus,
  hasPrediction,
  onGoToPrediction,
}) {
  const [filterType, setFilterType] = useState("all"); // "all" | "Legitimate" | "Phishing"
  const [sampleSearch, setSampleSearch] = useState("");
  const [showSamples, setShowSamples] = useState(true);

  async function handlePaste() {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        onUrlChange(text.trim());
      }
    } catch {
      // Clipboard access denied or unavailable
    }
  }

  const filteredSamples = SAMPLES.filter((s) => {
    if (filterType !== "all" && s.label !== filterType) return false;
    if (sampleSearch) {
      return s.url.toLowerCase().includes(sampleSearch.toLowerCase());
    }
    return true;
  });

  return (
    <div className="slide-content">
      {/* Hero / Introduction */}
      <div className="slide-intro">
        <div className="slide-intro-badge">
          <Shield size={14} className="text-accent" />
          <span>Slide 1 of 4 • Primary URL Scanner</span>
        </div>
        <h1 className="slide-title">Real-Time Explainable Phishing Detection</h1>
        <p className="slide-subtitle">
          Submit any raw URL for Public Suffix List parsing, live heuristic feature extraction,
          and transparent XGBoost machine learning classification.
        </p>
      </div>

      {/* Main Analysis Panel */}
      <div className="panel analyzer-card">
        <div className="analyzer-header">
          <div className="analyzer-header-title">
            <Globe size={18} className="text-accent" />
            <span>Target URL Verification</span>
          </div>
          {selectedSample ? (
            <span className={`badge-pill ${selectedSample.label === "Phishing" ? "badge-danger" : "badge-success"}`}>
              {selectedSample.label === "Phishing" ? <ShieldAlert size={12} /> : <ShieldCheck size={12} />}
              Dataset Sample: {selectedSample.label}
            </span>
          ) : (
            <span className="badge-pill badge-neutral">
              <Sparkles size={12} /> Live Scanner Mode
            </span>
          )}
        </div>

        {/* Input Bar */}
        <div className="url-input-container">
          <input
            type="text"
            className="url-input-field"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && onAnalyze()}
            placeholder="Enter or paste URL (e.g. https://paypal.com.account-verify.net/login)"
            aria-label="URL to inspect"
            disabled={loading}
          />
          <div className="url-input-actions">
            {url && (
              <button
                type="button"
                className="action-icon-btn"
                onClick={onClearUrl}
                title="Clear input"
                disabled={loading}
              >
                <RotateCcw size={15} />
              </button>
            )}
            <button
              type="button"
              className="action-icon-btn"
              onClick={handlePaste}
              title="Paste from clipboard"
              disabled={loading}
            >
              <ClipboardPaste size={15} />
            </button>
            <button
              type="button"
              className="primary-btn analyze-trigger-btn"
              onClick={onAnalyze}
              disabled={loading || !url.trim()}
            >
              {loading ? (
                <>
                  <span className="btn-spinner" />
                  <span>{stage || "Analyzing..."}</span>
                </>
              ) : (
                <>
                  <Search size={16} />
                  <span>Analyze URL</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Inline Status Message */}
        {inlineStatus && (
          <div className={`status-banner status-${inlineStatus.type}`}>
            <Info size={16} />
            <span>{inlineStatus.message}</span>
          </div>
        )}

        {/* Ready Result Shortcut */}
        {hasPrediction && !loading && (
          <div className="ready-prediction-callout">
            <div className="ready-text">
              <ShieldCheck size={18} className="text-success" />
              <span>Prediction generated. View SHAP attribution and confidence breakdown on Slide 2.</span>
            </div>
            <button
              type="button"
              className="secondary-btn go-result-btn"
              onClick={onGoToPrediction}
            >
              <span>View Prediction</span>
              <ArrowRight size={15} />
            </button>
          </div>
        )}
      </div>

      {/* Benchmark Dataset Fixtures */}
      <div className="panel samples-panel">
        <div className="samples-panel-header">
          <div>
            <div className="section-title">
              <Cpu size={16} className="text-accent" />
              <span>PhiUSIIL Benchmark Samples (Pre-extracted 50 Features)</span>
            </div>
            <p className="section-desc">
              Test verified legitimate and phishing URLs directly against the production model.
            </p>
          </div>
          <button
            type="button"
            className="toggle-samples-btn"
            onClick={() => setShowSamples(!showSamples)}
          >
            {showSamples ? "Hide Samples" : "Show Samples"}
          </button>
        </div>

        {showSamples && (
          <div className="samples-filter-stack">
            <div className="samples-controls-row">
              <div className="sample-tabs">
                <button
                  type="button"
                  className={`sample-tab-btn ${filterType === "all" ? "active" : ""}`}
                  onClick={() => setFilterType("all")}
                >
                  All ({SAMPLES.length})
                </button>
                <button
                  type="button"
                  className={`sample-tab-btn tab-legit ${filterType === "Legitimate" ? "active" : ""}`}
                  onClick={() => setFilterType("Legitimate")}
                >
                  Legitimate ({SAMPLES.filter((s) => s.label === "Legitimate").length})
                </button>
                <button
                  type="button"
                  className={`sample-tab-btn tab-phish ${filterType === "Phishing" ? "active" : ""}`}
                  onClick={() => setFilterType("Phishing")}
                >
                  Phishing ({SAMPLES.filter((s) => s.label === "Phishing").length})
                </button>
              </div>
              <input
                type="text"
                className="sample-search-input"
                value={sampleSearch}
                onChange={(e) => setSampleSearch(e.target.value)}
                placeholder="Filter sample URLs..."
              />
            </div>

            <div className="sample-chips-grid">
              {filteredSamples.map((sample, idx) => {
                const isSelected = selectedSample?.url === sample.url;
                const isPhish = sample.label === "Phishing";
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`sample-chip ${isPhish ? "chip-phish" : "chip-legit"} ${isSelected ? "selected" : ""}`}
                    onClick={() => onSelectSample(sample)}
                  >
                    <span className="chip-badge">{sample.label}</span>
                    <span className="chip-url" title={sample.url}>{sample.url}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
