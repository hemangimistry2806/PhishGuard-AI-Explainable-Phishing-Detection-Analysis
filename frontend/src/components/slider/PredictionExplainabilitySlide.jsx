import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  FileText,
  Fingerprint,
  Globe,
  HelpCircle,
  Info,
  Lock,
  MessageSquare,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  Terminal,
} from "lucide-react";
import { api } from "../../services/api.js";
import Swal from "sweetalert2";

// 50 Feature names to human-friendly titles
const FEATURE_FRIENDLY_NAMES = {
  URLLength: "URL Character Length",
  DomainLength: "Domain Character Length",
  IsDomainIP: "Direct IP Address Host",
  URLSimilarityIndex: "Brand / Benchmark Similarity",
  CharContinuationRate: "Character Continuation Rate",
  TLDLegitimateProb: "TLD Historical Legitimacy Score",
  URLCharProb: "URL Character Probability",
  TLDLength: "TLD Length",
  NoOfSubDomain: "Subdomain Nesting Count",
  HasObfuscation: "Obfuscation Flags",
  NoOfObfuscatedChar: "Obfuscated Characters Count",
  ObfuscationRatio: "Obfuscation Ratio",
  NoOfLettersInURL: "Letter Count in URL",
  LetterRatioInURL: "Letter-to-Length Ratio",
  NoOfDegitsInURL: "Digit Count in URL",
  DegitRatioInURL: "Digit-to-Length Ratio",
  NoOfEqualsInURL: "Query Equals Signs (=)",
  NoOfQMarkInURL: "Query Question Marks (?)",
  NoOfAmpersandInURL: "Query Ampersands (&)",
  NoOfOtherSpecialCharsInURL: "Other Special Characters",
  SpacialCharRatioInURL: "Special Character Ratio",
  IsHTTPS: "HTTPS Protocol Used",
  LineOfCode: "Webpage HTML Lines of Code",
  LargestLineLength: "HTML Largest Line Length",
  HasTitle: "Webpage Has Title Tag",
  DomainTitleMatchScore: "Domain & Title Match Score",
  URLTitleMatchScore: "URL & Title Match Score",
  HasFavicon: "Webpage Has Favicon Icon",
  Robots: "Robots.txt Presence",
  IsResponsive: "Responsive Viewport Tag",
  NoOfURLRedirect: "HTTP Redirect Count",
  NoOfSelfRedirect: "Self Redirect Count",
  HasDescription: "Meta Description Present",
  NoOfPopup: "Popup Windows Detected",
  NoOfiFrame: "iFrame Elements Count",
  HasExternalFormSubmit: "Form Submits to External Domain",
  HasSocialNet: "Social Media Links Present",
  HasSubmitButton: "Submit Button Present",
  HasHiddenFields: "Hidden Input Fields",
  HasPasswordField: "Password Input Field",
  Bank: "Financial / Banking Keywords",
  Pay: "Payment Keywords",
  Crypto: "Cryptocurrency Keywords",
  HasCopyrightInfo: "Copyright Notice in HTML",
  NoOfImage: "Image Count",
  NoOfCSS: "CSS Stylesheet Count",
  NoOfJS: "JavaScript File Count",
  NoOfSelfRef: "Self References Count",
  NoOfEmptyRef: "Empty References Count",
  NoOfExternalRef: "External References Count",
};

// 50 Feature names in canonical training schema order
const FEATURE_NAMES_ORDER = [
  "URLLength", "DomainLength", "IsDomainIP",
  "URLSimilarityIndex", "CharContinuationRate", "TLDLegitimateProb",
  "URLCharProb", "TLDLength", "NoOfSubDomain", "HasObfuscation",
  "NoOfObfuscatedChar", "ObfuscationRatio", "NoOfLettersInURL",
  "LetterRatioInURL", "NoOfDegitsInURL", "DegitRatioInURL",
  "NoOfEqualsInURL", "NoOfQMarkInURL", "NoOfAmpersandInURL",
  "NoOfOtherSpecialCharsInURL", "SpacialCharRatioInURL", "IsHTTPS",
  "LineOfCode", "LargestLineLength", "HasTitle",
  "DomainTitleMatchScore", "URLTitleMatchScore", "HasFavicon",
  "Robots", "IsResponsive", "NoOfURLRedirect", "NoOfSelfRedirect",
  "HasDescription", "NoOfPopup", "NoOfiFrame", "HasExternalFormSubmit",
  "HasSocialNet", "HasSubmitButton", "HasHiddenFields",
  "HasPasswordField", "Bank", "Pay", "Crypto", "HasCopyrightInfo",
  "NoOfImage", "NoOfCSS", "NoOfJS", "NoOfSelfRef",
  "NoOfEmptyRef", "NoOfExternalRef",
];

// Evidence-based risk level assessment
function getRiskAssessment(isPhishing, confidence) {
  const conf = Number(confidence || 0);
  if (isPhishing) {
    if (conf >= 0.90) {
      return {
        level: "Critical Risk",
        badgeClass: "risk-phish",
        description: "High-confidence phishing indicators detected across domain structure and URL tokens.",
      };
    }
    if (conf >= 0.70) {
      return {
        level: "High Risk",
        badgeClass: "risk-phish",
        description: "Substantial phishing patterns detected. Proceed with extreme caution.",
      };
    }
    return {
      level: "Moderate Risk",
      badgeClass: "risk-phish",
      description: "Borderline indicators detected. Address warrants independent verification.",
    };
  } else {
    if (conf >= 0.90) {
      return {
        level: "Low Risk",
        badgeClass: "risk-legit",
        description: "No anomalous phishing patterns found matching known malicious indicators.",
      };
    }
    return {
      level: "Moderate / Cautious Risk",
      badgeClass: "risk-legit",
      description: "Classified as legitimate with lower confidence margin. Exercise standard caution.",
    };
  }
}

// Generate evidence-grounded plain-language explanation
function generateSimpleExplanation(result, sample, explanation) {
  const isPhishing = result.label
    ? result.label.toLowerCase() === "phishing"
    : result.prediction === 0;

  const warnings = result.warnings || [];
  const domain = result.registered_domain || "";
  const shapFeatures = explanation?.shap_features || result.shap_features || [];
  const rawLlm = explanation?.llm_explanation || result.llm_explanation;
  const isLlmValid =
    rawLlm &&
    !rawLlm.startsWith("[LLM explanation unavailable") &&
    !rawLlm.includes("Neither OPENROUTER_API_KEY");

  // 1. What did the system find?
  const what = isPhishing
    ? "Result: This URL looks suspicious. The system detected patterns and structural markers commonly associated with phishing or deceptive websites that attempt to trick users into sharing passwords, credentials, or personal information."
    : "Result: No strong phishing indicators were detected. The system did not identify enough suspicious patterns to classify this URL as phishing.";

  // 2. Why did it give this result?
  const whyPoints = [];

  // Brand spoofing check from live extraction warnings
  const brandWarning = warnings.find((w) =>
    w.toLowerCase().includes("brand spoofing")
  );
  if (brandWarning) {
    whyPoints.push(
      "A recognized brand name was detected in the web address, but the official registered domain does not match that brand."
    );
  }

  // Domain structure evidence
  if (domain) {
    if (isPhishing) {
      whyPoints.push(
        `The destination registered domain "${domain}" differs from standard official services or exhibits deceptive subdomain layering.`
      );
    } else {
      whyPoints.push(
        `The registered domain "${domain}" adheres to standard public suffix conventions with no deceptive brand prefixing.`
      );
    }
  }

  // Feature evidence from SHAP
  if (shapFeatures.length > 0) {
    const topFeature = shapFeatures[0];
    const topFriendly =
      FEATURE_FRIENDLY_NAMES[topFeature.feature] || topFeature.feature;
    if (isPhishing && topFeature.shap_value < 0) {
      whyPoints.push(
        `The primary statistical signal raising suspicion was "${topFriendly}", which strongly diverged from typical legitimate website profiles.`
      );
    } else if (!isPhishing && topFeature.shap_value > 0) {
      whyPoints.push(
        `The strongest statistical confirming signal was "${topFriendly}", which aligned well with verified legitimate websites.`
      );
    }
  }

  // Live extraction warnings or approximations
  if (warnings.length > 0) {
    whyPoints.push(
      "Live extraction note: Some page features were safely approximated (e.g. crawler protection or lexical heuristics), which the model accounts for during evaluation."
    );
  }

  if (whyPoints.length === 0) {
    whyPoints.push(
      isPhishing
        ? "Multiple lexical and syntactic features across the URL match statistical profiles of known phishing pages in the benchmark."
        : "The URL length, character distribution, and domain structure align with standard legitimate websites."
    );
  }

  // 3. What should the user do next?
  const next = isPhishing
    ? "Avoid entering sensitive information, passwords, payment cards, or personal details on this destination. If you need to access this account or service, open a new browser tab and navigate directly using an independently bookmarked or verified official address. Do not browse suspicious websites to investigate them."
    : "Proceed cautiously. Check the website address carefully in your browser's address bar before typing passwords or private information, and verify that the destination domain matches the official organization.";

  return { what, why: whyPoints, next, llmNarrative: isLlmValid ? rawLlm : null };
}

export default function PredictionExplainabilitySlide({
  result,
  sample,
  explanation,
  onExplain,
  explaining,
  onBackToAnalysis,
  onFeedbackSubmitted,
}) {
  // Collapsible sections — SHAP and Advanced are COLLAPSED BY DEFAULT
  const [shapCollapsed, setShapCollapsed] = useState(true);
  const [advancedCollapsed, setAdvancedCollapsed] = useState(true);
  const [showAllShapFeatures, setShowAllShapFeatures] = useState(false);

  // Feedback form state
  const [feedbackVerdict, setFeedbackVerdict] = useState("Legitimate");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackSubmittedRecord, setFeedbackSubmittedRecord] = useState(null);

  // If no prediction is available yet, display clean empty state
  if (!result) {
    return (
      <div className="slide-content">
        <div className="panel empty-prediction-panel">
          <div className="empty-icon-box">
            <ShieldQuestion size={42} className="text-muted" />
          </div>
          <h2>No URL Analysis Results Yet</h2>
          <p>
            Please submit a URL or choose a benchmark sample on Slide 1 to generate machine learning
            predictions and plain-language explanations.
          </p>
          <button
            type="button"
            className="primary-btn"
            onClick={onBackToAnalysis}
          >
            <ArrowLeft size={16} />
            <span>Go to Slide 1 (URL Analysis)</span>
          </button>
        </div>
      </div>
    );
  }

  // Model class verification: 0 = Phishing, 1 = Legitimate
  const isPhishing = result.label
    ? result.label.toLowerCase() === "phishing"
    : result.prediction === 0;

  // Confidence is the probability of the predicted class
  const confidence = isPhishing
    ? result.phishing_probability
    : result.legitimate_probability;

  // Display label as specified: "Phishing" or "Likely Legitimate"
  const displayLabel = isPhishing ? "Phishing" : "Likely Legitimate";

  const risk = getRiskAssessment(isPhishing, confidence);
  const plainExplanation = generateSimpleExplanation(result, sample, explanation);

  const shapFeatures = explanation?.shap_features || result.shap_features || [];
  const displayedShap = showAllShapFeatures ? shapFeatures : shapFeatures.slice(0, 5);

  async function handleSubmitFeedback(e) {
    e.preventDefault();
    setSubmittingFeedback(true);
    try {
      const payload = {
        url: sample?.url || result.url,
        model_prediction: isPhishing ? "Phishing" : "Legitimate",
        user_verdict: feedbackVerdict,
        comment: feedbackComment.trim() || undefined,
        analysis_id: result.analysis_id || undefined,
        phishing_probability: result.phishing_probability,
        legitimate_probability: result.legitimate_probability,
        extracted_features: result.extracted_features || undefined,
      };

      const res = await api.submitFeedback(payload);
      setFeedbackSubmittedRecord(res);
      await Swal.fire({
        icon: "success",
        title: "Feedback Recorded",
        text: `Feedback #${res.feedback_id} recorded in SQLite database (Status: ${res.verification_status}).`,
        timer: 3000,
      });
      if (onFeedbackSubmitted) onFeedbackSubmitted();
    } catch (err) {
      await Swal.fire({
        icon: "error",
        title: "Feedback Failed",
        text: err.message || "Could not save feedback to database.",
      });
    } finally {
      setSubmittingFeedback(false);
    }
  }

  return (
    <div className="slide-content">
      {/* Slide Header */}
      <div className="slide-intro">
        <div className="slide-intro-badge">
          <Shield size={14} className="text-accent" />
          <span>Slide 2 of 4 • Prediction & Explainability</span>
        </div>
        <h1 className="slide-title">Prediction & Plain-Language Explanation</h1>
        <p className="slide-subtitle">
          Immediate, understandable classification results grounded in actual feature evidence,
          with optional technical attribution and auditor feedback.
        </p>
      </div>

      {/* 1. Prediction Result Card */}
      <div className={`verdict-panel ${isPhishing ? "verdict-danger" : "verdict-success"}`}>
        <div className="verdict-main-row">
          <div className="verdict-icon-container">
            {isPhishing ? <ShieldAlert size={36} /> : <ShieldCheck size={36} />}
          </div>
          <div className="verdict-info-col" style={{ flex: 1 }}>
            <div className="verdict-badges-row">
              <span className={`verdict-risk-badge ${risk.badgeClass}`}>
                {risk.level.toUpperCase()}
              </span>
              <span className="verdict-confidence-badge" title="Model's actual predicted-class probability">
                {(Number(confidence || 0) * 100).toFixed(1)}% Model Confidence
              </span>
              {result.registered_domain && (
                <span className="verdict-confidence-badge" title="Registered Domain via Public Suffix List">
                  <Globe size={12} /> {result.registered_domain}
                </span>
              )}
              {result.analysis_id && (
                <span className="verdict-id-badge" title="Unique Traceable Analysis ID">
                  <Fingerprint size={12} /> {result.analysis_id}
                </span>
              )}
            </div>

            <h2 className="verdict-title">Prediction: {displayLabel}</h2>

            <div className="verdict-url-box">
              <Globe size={14} />
              <code>{sample?.url || result.url}</code>
            </div>
          </div>
        </div>

        {/* Dual Class Probability Breakdown */}
        <div className="probability-breakdown">
          <div className="prob-meter-block">
            <div className="prob-meta">
              <span>Phishing Probability (Class 0)</span>
              <strong>{(Number(result.phishing_probability || 0) * 100).toFixed(1)}%</strong>
            </div>
            <div className="meter-track">
              <div
                className="meter-fill fill-danger"
                style={{ width: `${(Number(result.phishing_probability || 0) * 100).toFixed(1)}%` }}
              />
            </div>
          </div>

          <div className="prob-meter-block">
            <div className="prob-meta">
              <span>Legitimate Probability (Class 1)</span>
              <strong>{(Number(result.legitimate_probability || 0) * 100).toFixed(1)}%</strong>
            </div>
            <div className="meter-track">
              <div
                className="meter-fill fill-success"
                style={{ width: `${(Number(result.legitimate_probability || 0) * 100).toFixed(1)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Important Security Warning (Prominently displayed) */}
        <div className="safety-warning-banner">
          <AlertTriangle size={18} className="text-warning" style={{ flexShrink: 0, marginTop: 2 }} />
          <p className="safety-warning-text">
            <strong>Important Security Notice:</strong> A URL classified as legitimate is not
            guaranteed to be safe. Automated machine learning models evaluate known statistical
            indicators and cannot detect novel, zero-day, or targeted spear-phishing attacks. Always
            verify domain authenticity before entering confidential information.
          </p>
        </div>
      </div>

      {/* Disclosures & Warnings (if any) */}
      {result.warnings && result.warnings.length > 0 && (
        <div className="panel warning-panel" role="alert">
          <div className="warning-panel-header">
            <AlertTriangle size={18} className="text-warning" />
            <strong>Live Extraction Disclosures & Verification Warnings</strong>
          </div>
          <ul className="warning-panel-list">
            {result.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 2. Plain-Language Explanation — ALWAYS VISIBLE BY DEFAULT */}
      <div className="plain-language-panel">
        <div className="plain-language-header">
          <Sparkles size={20} className="text-accent" />
          <h3 className="plain-language-title">Simple-Language Explanation</h3>
          <span className="plain-language-badge">Always Visible</span>
        </div>

        <div className="qa-grid">
          {/* Question 1: What did the system find? */}
          <div className="qa-card">
            <div className="qa-card-header">
              <HelpCircle size={16} className="text-accent" />
              <span>1. What did the system find?</span>
            </div>
            <p className="qa-card-body">{plainExplanation.what}</p>
          </div>

          {/* Question 2: Why did it give this result? */}
          <div className="qa-card">
            <div className="qa-card-header">
              <Info size={16} className="text-accent" />
              <span>2. Why did it give this result?</span>
            </div>
            <div className="qa-card-body">
              <p style={{ margin: 0 }}>
                This result is based on the following verified characteristics and signals:
              </p>
              <ul className="qa-bullet-list">
                {plainExplanation.why.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
              {plainExplanation.llmNarrative && (
                <div style={{ marginTop: 12, padding: "10px 12px", background: "rgba(68, 199, 176, 0.06)", borderRadius: 6, border: "1px solid rgba(68, 199, 176, 0.2)" }}>
                  <strong style={{ fontSize: "0.82rem", color: "var(--accent)", display: "block", marginBottom: 4 }}>
                    AI Reasoning Narrative:
                  </strong>
                  <p style={{ margin: 0, fontSize: "0.86rem", color: "var(--text)" }}>
                    {plainExplanation.llmNarrative}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Question 3: What should the user do next? */}
          <div className="qa-card">
            <div className="qa-card-header">
              <Lock size={16} className={isPhishing ? "text-danger" : "text-success"} />
              <span>3. What should the user do next?</span>
            </div>
            <div className={`recommendation-action-box ${isPhishing ? "rec-danger" : "rec-safe"}`}>
              <p className="rec-text">{plainExplanation.next}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Optional Technical Explanation — SHAP (COLLAPSED BY DEFAULT) */}
      <div className="panel" style={{ padding: 0, overflow: "hidden", marginBottom: 22 }}>
        <button
          type="button"
          className="collapsible-trigger-btn"
          onClick={() => setShapCollapsed(!shapCollapsed)}
          aria-expanded={!shapCollapsed}
        >
          <div className="collapsible-trigger-title">
            <FileText size={18} className="text-accent" />
            <span>View Technical Explanation (SHAP)</span>
            <span className="collapsible-tag">Optional • Data Science</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
              {shapCollapsed ? "Show Technical Attribution" : "Collapse"}
            </span>
            {shapCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </div>
        </button>

        {!shapCollapsed && (
          <div style={{ padding: "0 20px 20px 20px" }}>
            {/* SHAP Guidance & Limitations Note */}
            <div className="technical-guide-box">
              <strong style={{ display: "block", color: "var(--text)", marginBottom: 4 }}>
                Understanding SHAP Log-Odds Contributions:
              </strong>
              SHAP (SHapley Additive exPlanations) values measure how much each feature shifted
              the XGBoost model's log-odds output away from the dataset baseline.
              Positive values (<span className="text-success">+Legitimate</span>) pushed the model toward
              classifying the URL as legitimate, while negative values (<span className="text-danger">-Phishing</span>)
              pushed toward phishing.
              <div className="guide-limitations-note">
                <AlertTriangle size={13} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />
                <em>Limitation: SHAP indicates statistical correlation learned by the model from the 235,795 PhiUSIIL records, not forensic causal proof.</em>
              </div>
            </div>

            {/* Feature Attribution Table */}
            {shapFeatures.length > 0 ? (
              <div className="shap-table-container">
                <div className="shap-row-grid shap-row-header">
                  <span>Feature & Meaning</span>
                  <span>Impact Direction</span>
                  <span>Support Status</span>
                  <span>Attribution</span>
                </div>

                {displayedShap.map((f, i) => {
                  const val = Number(f.shap_value || 0);
                  const isPositive = val > 0;
                  const friendlyName = FEATURE_FRIENDLY_NAMES[f.feature] || f.feature;

                  // Determine if feature supported the predicted class
                  const supportedPrediction = isPhishing ? val < 0 : val > 0;

                  return (
                    <div key={i} className="shap-row-grid">
                      <div>
                        <span className="friendly-feature-title">{friendlyName}</span>
                        <span className="technical-feature-sub">{f.feature}</span>
                      </div>
                      <div>
                        <span className={`direction-pill ${isPositive ? "push-legit" : "push-phish"}`}>
                          {isPositive ? "+Legitimate" : "-Phishing"}
                        </span>
                      </div>
                      <div>
                        <span className={`support-tag ${supportedPrediction ? "tag-supports" : "tag-opposes"}`}>
                          {supportedPrediction ? "Supports Verdict" : "Opposes Verdict"}
                        </span>
                      </div>
                      <div>
                        <code className="attribution-code">
                          {val >= 0 ? `+${val.toFixed(4)}` : val.toFixed(4)}
                        </code>
                      </div>
                    </div>
                  );
                })}

                {shapFeatures.length > 5 && (
                  <button
                    type="button"
                    className="expand-features-btn"
                    onClick={() => setShowAllShapFeatures(!showAllShapFeatures)}
                  >
                    {showAllShapFeatures
                      ? "Show top 5 features only"
                      : `View all ${shapFeatures.length} features`}
                  </button>
                )}
              </div>
            ) : (
              <div className="empty-shap-state" style={{ padding: "16px", textAlign: "center" }}>
                <p style={{ margin: "0 0 10px 0", color: "var(--muted)" }}>
                  Technical SHAP explanation was not pre-computed for this sample.
                </p>
                {onExplain && (
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={onExplain}
                    disabled={explaining}
                  >
                    {explaining ? "Computing SHAP..." : "Compute SHAP Attribution"}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. Optional Additional Technical Details (COLLAPSED BY DEFAULT) */}
      <div className="panel" style={{ padding: 0, overflow: "hidden", marginBottom: 22 }}>
        <button
          type="button"
          className="collapsible-trigger-btn"
          onClick={() => setAdvancedCollapsed(!advancedCollapsed)}
          aria-expanded={!advancedCollapsed}
        >
          <div className="collapsible-trigger-title">
            <Cpu size={18} className="text-accent" />
            <span>Advanced Details & Feature Vector</span>
            <span className="collapsible-tag">Optional • Raw Telemetry</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
              {advancedCollapsed ? "Show Raw Telemetry" : "Collapse"}
            </span>
            {advancedCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </div>
        </button>

        {!advancedCollapsed && (
          <div style={{ padding: "0 20px 20px 20px" }}>
            <div className="advanced-meta-grid">
              <div className="advanced-meta-card">
                <span>Model Architecture</span>
                <strong>XGBoost Classifier (50 features)</strong>
              </div>
              <div className="advanced-meta-card">
                <span>Evaluation Benchmark</span>
                <strong>PhiUSIIL (235,795 rows)</strong>
              </div>
              <div className="advanced-meta-card">
                <span>Registered Domain (PSL)</span>
                <strong>{result.registered_domain || "N/A (Multi-part PSL)"}</strong>
              </div>
              <div className="advanced-meta-card">
                <span>Analysis ID</span>
                <strong>{result.analysis_id || "N/A"}</strong>
              </div>
            </div>

            {result.extracted_features && result.extracted_features.length === 50 ? (
              <div className="raw-vector-table-wrap">
                <table className="raw-vector-table">
                  <thead>
                    <tr>
                      <th style={{ width: 40 }}>#</th>
                      <th>Feature Name</th>
                      <th>Meaning</th>
                      <th style={{ textAlign: "right" }}>Raw Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {FEATURE_NAMES_ORDER.map((name, idx) => (
                      <tr key={idx}>
                        <td>{idx + 1}</td>
                        <td><code>{name}</code></td>
                        <td>{FEATURE_FRIENDLY_NAMES[name] || name}</td>
                        <td style={{ textAlign: "right", fontFamily: "monospace" }}>
                          {Number(result.extracted_features[idx]).toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--muted)" }}>
                Raw 50-feature vector is not attached to this result record.
              </p>
            )}
          </div>
        )}
      </div>

      {/* 5. Feedback Integration */}
      <div className="panel feedback-submission-panel">
        <div className="section-title">
          <MessageSquare size={18} className="text-accent" />
          <span>Do you think this result is correct?</span>
          <small className="badge-pill badge-neutral">SQLite Persisted</small>
        </div>
        <p className="section-desc">
          Your feedback is recorded persistently as a community report for human auditor review
          and candidate dataset staging. It is never automatically treated as ground truth or used
          to overwrite the production model.
        </p>

        {feedbackSubmittedRecord ? (
          <div className="feedback-success-banner">
            <CheckCircle2 size={18} className="text-success" />
            <div>
              <strong>Feedback Recorded (ID #{feedbackSubmittedRecord.feedback_id})</strong>
              <p>
                Your ground-truth report ({feedbackSubmittedRecord.user_verdict}) has been persisted
                and tagged for human reviewer auditing (Status: {feedbackSubmittedRecord.verification_status}).
              </p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmitFeedback}>
            {/* Feedback Choice Cards */}
            <div className="feedback-choice-grid">
              <button
                type="button"
                className={`feedback-choice-card ${feedbackVerdict === "Legitimate" ? "choice-selected-legit" : ""}`}
                onClick={() => setFeedbackVerdict("Legitimate")}
              >
                <div className="choice-radio-dot">
                  {feedbackVerdict === "Legitimate" && <div className="choice-radio-inner" />}
                </div>
                <div className="choice-label-text">
                  <strong>The URL appears legitimate.</strong>
                  <span>Safe, authorized, or trusted website destination</span>
                </div>
              </button>

              <button
                type="button"
                className={`feedback-choice-card ${feedbackVerdict === "Phishing" ? "choice-selected-phish" : ""}`}
                onClick={() => setFeedbackVerdict("Phishing")}
              >
                <div className="choice-radio-dot">
                  {feedbackVerdict === "Phishing" && <div className="choice-radio-inner" />}
                </div>
                <div className="choice-label-text">
                  <strong>The URL appears to be phishing.</strong>
                  <span>Suspicious, credential harvesting, or deceptive</span>
                </div>
              </button>
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label>Auditor Notes / Context (Optional)</label>
              <textarea
                rows={3}
                className="form-textarea"
                placeholder="Explain why you agree or disagree (e.g. false positive on trusted portal, or novel phishing tactic)"
                value={feedbackComment}
                onChange={(e) => setFeedbackComment(e.target.value)}
                maxLength={1000}
              />
            </div>

            <button
              type="submit"
              className="primary-btn submit-feedback-btn"
              disabled={submittingFeedback}
            >
              {submittingFeedback ? (
                <>
                  <span className="btn-spinner" />
                  <span>Submitting to Database...</span>
                </>
              ) : (
                <>
                  <Send size={15} />
                  <span>Submit Ground-Truth Feedback</span>
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
