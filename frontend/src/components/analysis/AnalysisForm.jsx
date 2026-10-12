import { Clipboard, Globe, Search, ShieldCheck, Sparkles, X } from "lucide-react";
import Button from "../common/Button.jsx";

export default function AnalysisForm({
  url,
  onUrlChange,
  onClearUrl,
  selectedSample,
  onAnalyze,
  loading,
  stage,
  inlineStatus,
}) {
  function handleSubmit(event) {
    event.preventDefault();
    onAnalyze();
  }

  async function handlePaste() {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) onUrlChange(text.trim());
      }
    } catch {
      // Browser permissions or clipboard access denied; silent fallback
    }
  }

  const isMatched = selectedSample && selectedSample.features?.length === 50;

  return (
    <section className="panel analysis-panel-primary">
      <div className="section-title">
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Search size={18} className="panel-title-icon" />
          <span>Phishing Risk Analyzer</span>
        </div>
        <span className={`analysis-mode-badge ${isMatched ? "benchmark" : "live"}`}>
          {isMatched ? (
            <>
              <ShieldCheck size={13} /> Benchmark Mode (Fast)
            </>
          ) : (
            <>
              <Globe size={13} /> Live Feature Extraction
            </>
          )}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="analysis-form" noValidate>
        <div className="input-group">
          <label className="field-label" htmlFor="url-input">
            Enter URL to analyze
          </label>
          <div className="input-row main-url-input">
            <Globe size={18} className="input-leading-icon" aria-hidden="true" />
            <input
              id="url-input"
              type="text"
              value={url}
              aria-describedby="url-input-help"
              onChange={(event) => onUrlChange(event.target.value)}
              placeholder="e.g. https://www.paypal.com or http://suspicious-site.tk"
              autoComplete="off"
              spellCheck="false"
              autoFocus
            />
            <div className="input-actions-group">
              {url ? (
                <button
                  type="button"
                  className="input-action-btn"
                  onClick={onClearUrl}
                  aria-label="Clear URL"
                  title="Clear input"
                >
                  <X size={16} />
                </button>
              ) : (
                <button
                  type="button"
                  className="input-action-btn"
                  onClick={handlePaste}
                  aria-label="Paste from clipboard"
                  title="Paste URL"
                >
                  <Clipboard size={15} />
                </button>
              )}
            </div>
          </div>
        </div>

        {isMatched ? (
          <div className="selected-summary-compact">
            <div className="match-pill">
              <ShieldCheck size={14} />
              <span>Verified Benchmark Sample: <strong>{selectedSample.label}</strong></span>
            </div>
            <small>50 verified features loaded directly from PhiUSIIL dataset</small>
          </div>
        ) : url.trim() ? (
          <div className="live-extraction-notice">
            <small>
              External URL detected. The backend will fetch the page and extract 50 structural and content features.
            </small>
          </div>
        ) : null}

        <div className="form-submit-row">
          <Button
            type="submit"
            icon={Sparkles}
            loading={loading}
            onClick={onAnalyze}
            className="primary-action analyze-btn"
            aria-busy={loading}
            disabled={!url.trim() || loading}
          >
            {loading ? stage : "Analyze URL"}
          </Button>

          {inlineStatus ? (
            <div className={`inline-status-msg ${inlineStatus.type}`} role="status">
              <span>{inlineStatus.message}</span>
            </div>
          ) : null}
        </div>
      </form>
    </section>
  );
}
