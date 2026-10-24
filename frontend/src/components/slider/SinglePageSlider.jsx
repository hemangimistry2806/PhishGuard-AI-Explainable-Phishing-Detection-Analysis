import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Cpu,
  MessageSquare,
  Search,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Swal from "sweetalert2";

import { api } from "../../services/api.js";
import { SAMPLES } from "../../data/samples/index.js";

import UrlAnalysisSlide from "./UrlAnalysisSlide.jsx";
import PredictionExplainabilitySlide from "./PredictionExplainabilitySlide.jsx";
import ModelEvaluationSlide from "./ModelEvaluationSlide.jsx";
import FeedbackAnalyticsSlide from "./FeedbackAnalyticsSlide.jsx";

const SLIDES = [
  { id: 0, title: "URL Analysis", short: "Analysis", icon: Search },
  { id: 1, title: "Prediction & Explainability", short: "Prediction", icon: ShieldAlert },
  { id: 2, title: "Model Evaluation & Reliability", short: "Evaluation", icon: BarChart3 },
  { id: 3, title: "Feedback & Analytics", short: "Feedback", icon: MessageSquare },
];

export default function SinglePageSlider({ initialSlide = 0 }) {
  const [activeSlide, setActiveSlide] = useState(initialSlide);
  const [slideDirection, setSlideDirection] = useState(1); // 1 = right, -1 = left

  // Shared state maintained across all slide transitions
  const [url, setUrl] = useState("");
  const [selectedSample, setSelectedSample] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [stage, setStage] = useState("");
  const [inlineStatus, setInlineStatus] = useState(null);
  const [backendHealth, setBackendHealth] = useState({ online: false, checking: true });

  // Check backend health on mount
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  async function checkHealth() {
    try {
      const res = await api.checkHealth();
      setBackendHealth({ online: res?.status === "ok", checking: false });
    } catch {
      setBackendHealth({ online: false, checking: false });
    }
  }

  // Keyboard navigation (ArrowLeft, ArrowRight, keys 1-4)
  useEffect(() => {
    function handleKeyDown(e) {
      // Do not intercept keystrokes if typing inside inputs
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

      if (e.key === "ArrowLeft") {
        goToSlide(Math.max(0, activeSlide - 1));
      } else if (e.key === "ArrowRight") {
        goToSlide(Math.min(SLIDES.length - 1, activeSlide + 1));
      } else if (["1", "2", "3", "4"].includes(e.key)) {
        const target = parseInt(e.key, 10) - 1;
        goToSlide(target);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeSlide]);

  function goToSlide(target) {
    if (target === activeSlide) return;
    setSlideDirection(target > activeSlide ? 1 : -1);
    setActiveSlide(target);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleUrlChange(newUrl) {
    setUrl(newUrl);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);

    // Auto-detect matching benchmark sample
    const trimmed = newUrl.trim().toLowerCase();
    const match = SAMPLES.find(
      (s) => s.url.toLowerCase() === trimmed || s.url.replace(/^https?:\/\//, "").toLowerCase() === trimmed.replace(/^https?:\/\//, "")
    );
    setSelectedSample(match || null);
  }

  function handleClearUrl() {
    setUrl("");
    setSelectedSample(null);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);
  }

  function handleSelectSample(sample) {
    setSelectedSample(sample);
    setUrl(sample.url);
    setPrediction(null);
    setExplanation(null);
    setInlineStatus({
      type: "info",
      message: `Selected benchmark sample: ${sample.label} (${sample.url})`,
    });
  }

  async function handleAnalyze() {
    const trimmed = url.trim();
    if (!trimmed) {
      await Swal.fire({
        icon: "warning",
        title: "URL Required",
        text: "Please enter or paste a URL to analyze.",
      });
      return;
    }

    // Format validation
    const hasProtocolOrDomain = /^(https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+/i.test(trimmed);
    if (!hasProtocolOrDomain) {
      await Swal.fire({
        icon: "warning",
        title: "Invalid URL Format",
        text: "Please enter a valid URL (e.g. https://example.com or http://sub.domain.co.uk).",
      });
      return;
    }

    setLoading(true);
    setStage("Extracting URL features...");
    setPrediction(null);
    setExplanation(null);
    setInlineStatus(null);

    try {
      let result;

      if (selectedSample && Array.isArray(selectedSample.features) && selectedSample.features.length === 50) {
        // Fast path: benchmark dataset features
        result = await api.predict(selectedSample.features);
        setPrediction(result);
        setInlineStatus({
          type: "success",
          message: `Benchmark evaluation completed: Classified as ${result.label}.`,
        });
      } else {
        // Live extraction path: backend PSL + SSRF safe page fetch
        setStage("Fetching HTML & analyzing security features...");
        result = await api.analyzeUrl(trimmed, true);
        setPrediction(result);
        if (result.shap_features && result.shap_features.length > 0) {
          setExplanation(result);
        }

        if (result.warnings && result.warnings.length > 0) {
          setInlineStatus({
            type: "warning",
            message: result.fetch_error
              ? "Live analysis completed with fetch notes. HTML features defaulted to safe values."
              : "Live analysis completed with transparent feature disclosures.",
          });
        } else {
          setInlineStatus({
            type: "success",
            message: `Live analysis completed: Classified as ${result.label}.`,
          });
        }
      }

      // Smoothly transition to Slide 2 to present the prediction!
      goToSlide(1);
    } catch (error) {
      setInlineStatus({
        type: "error",
        message: error.message || "Analysis failed.",
      });
      await Swal.fire({
        icon: "error",
        title: "Analysis Failed",
        text: error.message,
      });
    } finally {
      setLoading(false);
      setStage("");
    }
  }

  async function handleExplain() {
    if (!prediction) return;
    setExplaining(true);
    try {
      if (selectedSample && selectedSample.features) {
        const result = await api.explain(selectedSample.url, selectedSample.features);
        setExplanation(result);
      }
    } catch (err) {
      await Swal.fire({
        icon: "error",
        title: "Explanation Failed",
        text: err.message || "Could not generate SHAP explanation.",
      });
    } finally {
      setExplaining(false);
    }
  }

  return (
    <div className="slider-app-container">
      {/* Top Application Header */}
      <header className="slider-header-bar">
        <div className="header-brand-wrap">
          <div className="brand-badge-icon">
            <ShieldCheck size={22} className="text-accent" />
          </div>
          <div>
            <div className="brand-title">PhishGuard-AI</div>
            <div className="brand-subtitle">Explainable URL Detection</div>
          </div>
        </div>

        {/* Backend Health Pill */}
        <div className="backend-health-pill" title="Live FastAPI Backend Service">
          <span
            className={`status-pulse-dot ${
              backendHealth.checking ? "pulse-checking" : backendHealth.online ? "pulse-online" : "pulse-offline"
            }`}
          />
          <span className="health-text">
            {backendHealth.checking ? "Checking..." : backendHealth.online ? "Backend Online" : "Backend Offline"}
          </span>
        </div>

        {/* Slide Navigation Controls */}
        <div className="slider-nav-arrows">
          <button
            type="button"
            className="slider-arrow-btn"
            onClick={() => goToSlide(activeSlide - 1)}
            disabled={activeSlide === 0}
            aria-label="Previous Slide"
          >
            <ChevronLeft size={18} />
            <span>Prev</span>
          </button>
          <div className="slider-step-indicator">
            {activeSlide + 1} / {SLIDES.length}
          </div>
          <button
            type="button"
            className="slider-arrow-btn"
            onClick={() => goToSlide(activeSlide + 1)}
            disabled={activeSlide === SLIDES.length - 1}
            aria-label="Next Slide"
          >
            <span>Next</span>
            <ChevronRight size={18} />
          </button>
        </div>
      </header>

      {/* Horizontal Slide Indicator Tabs */}
      <nav className="slider-tabs-nav" aria-label="Slider Sections">
        <div className="slider-tabs-container">
          {SLIDES.map((slide, idx) => {
            const Icon = slide.icon;
            const isActive = activeSlide === idx;
            return (
              <button
                key={slide.id}
                type="button"
                className={`slider-tab-btn ${isActive ? "active-tab" : ""}`}
                onClick={() => goToSlide(idx)}
                aria-current={isActive ? "step" : undefined}
              >
                <span className="tab-step-num">{idx + 1}</span>
                <Icon size={16} className="tab-icon" />
                <span className="tab-label-full">{slide.title}</span>
                <span className="tab-label-short">{slide.short}</span>
              </button>
            );
          })}
        </div>
        <div className="slider-progress-track">
          <div
            className="slider-progress-fill"
            style={{ width: `${((activeSlide + 1) / SLIDES.length) * 100}%` }}
          />
        </div>
      </nav>

      {/* Main Viewport with Horizontal Animated Slide Switch */}
      <main className="slider-viewport-main">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeSlide}
            initial={{ opacity: 0, x: slideDirection * 60 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: slideDirection * -60 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
            className="slide-wrapper"
          >
            {activeSlide === 0 && (
              <UrlAnalysisSlide
                url={url}
                onUrlChange={handleUrlChange}
                onClearUrl={handleClearUrl}
                selectedSample={selectedSample}
                onSelectSample={handleSelectSample}
                onAnalyze={handleAnalyze}
                loading={loading}
                stage={stage}
                inlineStatus={inlineStatus}
                hasPrediction={!!prediction}
                onGoToPrediction={() => goToSlide(1)}
              />
            )}

            {activeSlide === 1 && (
              <PredictionExplainabilitySlide
                result={prediction}
                sample={selectedSample || { url }}
                explanation={explanation}
                onExplain={handleExplain}
                explaining={explaining}
                onBackToAnalysis={() => goToSlide(0)}
                onFeedbackSubmitted={() => {}}
              />
            )}

            {activeSlide === 2 && <ModelEvaluationSlide />}

            {activeSlide === 3 && <FeedbackAnalyticsSlide />}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer bar with keyboard tip */}
      <footer className="slider-footer-bar">
        <div className="footer-keys-hint">
          <span className="key-kbd">←</span>
          <span className="key-kbd">→</span>
          <span>Use arrow keys to navigate slides</span>
          <span className="key-kbd">1</span>
          <span className="key-kbd">2</span>
          <span className="key-kbd">3</span>
          <span className="key-kbd">4</span>
          <span>Jump to section</span>
        </div>
        <div className="footer-meta">
          <span>PhishGuard-AI • Production XGBoost + SHAP Explainability Engine</span>
        </div>
      </footer>
    </div>
  );
}
