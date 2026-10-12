import { useMemo, useState, useRef } from "react";
import Swal from "sweetalert2";
import { ShieldCheck } from "lucide-react";
import PageHeader from "../../components/common/PageHeader.jsx";
import AnalysisForm from "../../components/analysis/AnalysisForm.jsx";
import PredictionResult from "../../components/analysis/PredictionResult.jsx";
import SampleSelector from "../../components/analysis/SampleSelector.jsx";
import { SAMPLES } from "../../data/samples/index.js";
import { api } from "../../services/api.js";

function isValidSample(sample) {
  return sample && Array.isArray(sample.features) && sample.features.length === 50;
}

function normalizeUrl(raw) {
  if (!raw) return "";
  return raw.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/+$/, "");
}

function findMatchingSample(rawUrl) {
  if (!rawUrl || !rawUrl.trim()) return null;
  const cleaned = rawUrl.trim();
  const normalized = normalizeUrl(cleaned);

  // Exact match
  const exact = SAMPLES.find(
    (s) => s.url.toLowerCase() === cleaned.toLowerCase()
  );
  if (exact) return exact;

  // Normalized match (ignoring scheme http/https and trailing slash)
  const normMatch = SAMPLES.find(
    (s) => normalizeUrl(s.url) === normalized
  );
  return normMatch || null;
}

export default function HomePage() {
  const [selectedSample, setSelectedSample] = useState(null);
  const [url, setUrl] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [stage, setStage] = useState("Analyzing URL...");
  const [inlineStatus, setInlineStatus] = useState(null);

  const resultRef = useRef(null);
  const sampleCount = useMemo(() => SAMPLES.length, []);

  function handleUrlChange(newUrl) {
    setUrl(newUrl);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);

    const match = findMatchingSample(newUrl);
    setSelectedSample(match);
  }

  function handleClearUrl() {
    setUrl("");
    setSelectedSample(null);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);
  }

  function selectSample(sample) {
    setSelectedSample(sample);
    setUrl(sample.url);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus({
      type: "info",
      message: `Selected benchmark sample: ${sample.label} (${sample.url})`,
    });
  }

  async function analyze() {
    const trimmed = url.trim();
    if (!trimmed) {
      await Swal.fire({
        icon: "warning",
        title: "URL Required",
        text: "Please enter or paste a URL to analyze.",
      });
      return;
    }

    // Basic URL format validation
    const hasProtocolOrDomain = /^(https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+/i.test(trimmed);
    if (!hasProtocolOrDomain) {
      await Swal.fire({
        icon: "warning",
        title: "Invalid URL Format",
        text: "Please enter a valid URL (e.g., http://www.teramill.com or https://example.com).",
      });
      return;
    }

    const matched = selectedSample || findMatchingSample(trimmed);

    setLoading(true);
    setStage("Analyzing URL...");
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);

    try {
      let result;

      if (matched && isValidSample(matched)) {
        // Fast path: use pre-extracted dataset features (no page fetch needed)
        result = await api.predict(matched.features);
        if (typeof result.prediction !== "number" || !result.label) {
          throw new Error("The backend returned an unexpected prediction response.");
        }
        setPrediction(result);
        setInlineStatus({
          type: "success",
          message: `Benchmark evaluation completed: Classified as ${result.label} using verified 50 features.`,
        });
      } else {
        // Live path: backend fetches the page and extracts features
        setStage("Fetching page and extracting features...");
        result = await api.analyzeUrl(trimmed, true);
        if (typeof result.prediction !== "number" || !result.label) {
          throw new Error("The backend returned an unexpected analysis response.");
        }
        // Store the full /analyze/ response (includes shap_features, warnings, etc.)
        setPrediction(result);
        // If SHAP was included in the response, store explanation immediately
        if (result.shap_features && result.shap_features.length > 0) {
          setExplanation(result);
        }

        if (result.warnings && result.warnings.length > 0) {
          setInlineStatus({
            type: "warning",
            message: result.fetch_error
              ? "Live analysis completed with fetch notes. HTML features defaulted to 0."
              : "Live analysis completed. Note: URLSimilarityIndex is approximated on external URLs.",
          });
        } else {
          setInlineStatus({
            type: "success",
            message: `Live analysis completed: Classified as ${result.label}.`,
          });
        }
      }
    } catch (error) {
      setInlineStatus({
        type: "error",
        message: error.message || "Analysis failed.",
      });
      await Swal.fire({ icon: "error", title: "Analysis Failed", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  async function explain() {
    const matched = selectedSample || findMatchingSample(url);

    // If we already have explanation from /analyze/ response, skip re-fetch
    if (explanation && explanation.shap_features) return;

    if (!prediction || !matched || !isValidSample(matched)) return;
    setExplaining(true);
    setStage("Generating explanation...");
    try {
      const result = await api.explain(matched.url, matched.features);
      setExplanation(result);
      setInlineStatus({
        type: "success",
        message: "SHAP feature importance calculated successfully.",
      });
    } catch (error) {
      await Swal.fire({ icon: "error", title: "Explanation Failed", text: error.message });
    } finally {
      setExplaining(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Explainable AI Security"
        title="Analyze Phishing Risk"
        description="Analyze any URL using live feature extraction and SHAP explainability, or benchmark against verified dataset samples."
      >
        <div className="success-chip">
          <ShieldCheck size={16} />
          <span>{sampleCount} benchmark samples</span>
        </div>
      </PageHeader>

      <div className="analyze-main-stack">
        <AnalysisForm
          url={url}
          onUrlChange={handleUrlChange}
          onClearUrl={handleClearUrl}
          selectedSample={selectedSample}
          onAnalyze={analyze}
          loading={loading}
          stage={stage}
          inlineStatus={inlineStatus}
        />

        <div ref={resultRef}>
          <PredictionResult
            result={prediction}
            sample={selectedSample || { url }}
            explanation={explanation}
            onExplain={explain}
            explaining={explaining}
          />
        </div>

        <SampleSelector
          samples={SAMPLES}
          selectedSample={selectedSample}
          onSelect={selectSample}
        />
      </div>
    </div>
  );
}
