import { useMemo, useState } from "react";
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

  const sampleCount = useMemo(() => SAMPLES.length, []);

  function handleUrlChange(newUrl) {
    setUrl(newUrl);
    setPrediction(null);
    setExplanation(null);

    const match = findMatchingSample(newUrl);
    setSelectedSample(match);
  }

  function handleClearUrl() {
    setUrl("");
    setSelectedSample(null);
    setPrediction(null);
    setExplanation(null);
  }

  function selectSample(sample) {
    setSelectedSample(sample);
    setUrl(sample.url);
    setPrediction(null);
    setExplanation(null);
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

    try {
      let result;

      if (matched && isValidSample(matched)) {
        // Fast path: use pre-extracted dataset features (no page fetch needed)
        result = await api.predict(matched.features);
        if (typeof result.prediction !== "number" || !result.label) {
          throw new Error("The backend returned an unexpected prediction response.");
        }
        setPrediction(result);
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
        // Surface warnings about approximation
        if (result.warnings && result.warnings.length > 0) {
          const note = result.fetch_error
            ? "⚠️ Page fetch failed — HTML features defaulted to 0. Accuracy may be reduced."
            : "ℹ️ Some features were approximated (see console for details).";
          console.info("[PhishGuard] Feature extraction warnings:", result.warnings);
          await Swal.fire({
            icon: result.fetch_error ? "warning" : "info",
            title: "Analysis Complete (with notes)",
            text: note,
            timer: 3500,
            showConfirmButton: true,
          });
          return;
        }
      }

      await Swal.fire({
        icon: "success",
        title: "Analysis Complete",
        text: "The phishing analysis was completed successfully.",
        timer: 1500,
        showConfirmButton: false,
      });
    } catch (error) {
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
      await Swal.fire({
        icon: "success",
        title: "Explanation Ready",
        text: "The SHAP explanation was generated successfully.",
        timer: 1300,
        showConfirmButton: false,
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
        eyebrow="Live backend integration"
        title="Analyze phishing risk with explainable AI"
        description="Type or paste any URL to run live feature extraction and phishing analysis. Choose a verified dataset sample for instant benchmark results."
      >
        <div className="success-chip">
          <ShieldCheck size={16} />
          <span>{sampleCount} verified samples</span>
        </div>
      </PageHeader>

      <div className="analysis-grid">
        <SampleSelector samples={SAMPLES} selectedSample={selectedSample} onSelect={selectSample} />
        <AnalysisForm
          url={url}
          onUrlChange={handleUrlChange}
          onClearUrl={handleClearUrl}
          selectedSample={selectedSample}
          onAnalyze={analyze}
          loading={loading}
          stage={stage}
        />
      </div>

      <PredictionResult
        result={prediction}
        sample={selectedSample || { url }}
        explanation={explanation}
        onExplain={explain}
        explaining={explaining}
      />
    </div>
  );
}
