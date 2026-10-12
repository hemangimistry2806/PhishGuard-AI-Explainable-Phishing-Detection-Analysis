import { Search, Sparkles, X } from "lucide-react";
import Button from "../common/Button.jsx";

export default function AnalysisForm({
  url,
  onUrlChange,
  onClearUrl,
  selectedSample,
  onAnalyze,
  loading,
  stage,
}) {
  function handleSubmit(event) {
    event.preventDefault();
    onAnalyze();
  }

  const isMatched = selectedSample && selectedSample.features?.length === 50;

  return (
    <section className="panel analysis-panel">
      <div className="section-title">
        <span>Analysis request</span>
        <small>50-feature vector mode</small>
      </div>

      <form onSubmit={handleSubmit} className="analysis-panel" noValidate>
        <label className="field-label" htmlFor="url-input">
          URL under review
        </label>
        <div className="input-row">
          <Search size={18} aria-hidden="true" />
          <input
            id="url-input"
            type="text"
            value={url}
            aria-describedby="url-input-help"
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="Type or paste a URL (e.g. http://www.teramill.com)"
            autoComplete="off"
            spellCheck="false"
          />
          {url ? (
            <button
              type="button"
              className="input-action-btn"
              onClick={onClearUrl}
              aria-label="Clear URL"
              title="Clear URL"
            >
              <X size={16} />
            </button>
          ) : null}
        </div>

        <p className="field-help" id="url-input-help">
          Type or paste any URL, or click a verified sample below. The backend evaluates the URL using
          pre-extracted 50-feature vectors from the PhiUSIIL benchmark dataset.
        </p>

        {isMatched ? (
          <div className="selected-summary">
            <span>Verified dataset match</span>
            <strong>{selectedSample.label}</strong>
            <small>{selectedSample.features.length} verified features loaded</small>
          </div>
        ) : null}

        <Button
          type="submit"
          icon={Sparkles}
          loading={loading}
          onClick={onAnalyze}
          className="primary-action"
          aria-busy={loading}
        >
          {loading ? stage : "Check URL"}
        </Button>

        <p className="field-help" role="status">
          {loading
            ? stage
            : isMatched
              ? `Ready to analyze ${selectedSample.url}`
              : url.trim()
                ? `Ready to check: ${url.trim()}`
                : "Enter a URL or select a verified sample to check."}
        </p>
      </form>
    </section>
  );
}
