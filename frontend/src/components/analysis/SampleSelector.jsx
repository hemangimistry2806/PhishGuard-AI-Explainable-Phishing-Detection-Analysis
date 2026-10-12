import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp, Filter, ShieldAlert } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function SampleSelector({ samples, selectedSample, onSelect }) {
  const [filter, setFilter] = useState("all"); // 'all' | 'Phishing' | 'Legitimate'
  const [expanded, setExpanded] = useState(false);

  const filteredSamples = samples.filter((s) => {
    if (filter === "all") return true;
    return s.label === filter;
  });

  const displayedSamples = expanded ? filteredSamples : filteredSamples.slice(0, 4);

  return (
    <section className="panel sample-selector-panel">
      <div className="sample-selector-header">
        <div className="section-title" style={{ margin: 0 }}>
          <span>Verified dataset samples</span>
          <small>{samples.length} benchmark items</small>
        </div>
        <div className="sample-filter-group">
          <button
            type="button"
            className={`filter-chip ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All ({samples.length})
          </button>
          <button
            type="button"
            className={`filter-chip danger ${filter === "Phishing" ? "active" : ""}`}
            onClick={() => setFilter("Phishing")}
          >
            Phishing ({samples.filter((s) => s.label === "Phishing").length})
          </button>
          <button
            type="button"
            className={`filter-chip success ${filter === "Legitimate" ? "active" : ""}`}
            onClick={() => setFilter("Legitimate")}
          >
            Legitimate ({samples.filter((s) => s.label === "Legitimate").length})
          </button>
        </div>
      </div>

      <div className="sample-grid">
        {displayedSamples.map((sample, index) => {
          const selected = selectedSample?.url === sample.url;
          const isPhishing = sample.label === "Phishing";
          return (
            <motion.button
              type="button"
              key={sample.url}
              className={`sample-card ${selected ? "selected" : ""}`}
              onClick={() => onSelect(sample)}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.99 }}
              aria-pressed={selected}
            >
              <div className="sample-card-top">
                <span className={`status-pill ${isPhishing ? "danger" : "success"}`}>
                  {isPhishing ? <ShieldAlert size={14} /> : <CheckCircle2 size={14} />}
                  {sample.label}
                </span>
                <span className="sample-id">#{index + 1}</span>
              </div>
              <code className="sample-url-text">{sample.url}</code>
              <span className="sample-desc-text">{sample.description}</span>
            </motion.button>
          );
        })}
      </div>

      {filteredSamples.length > 4 ? (
        <div className="sample-footer">
          <button
            type="button"
            className="toggle-more-samples-btn"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
          >
            <span>
              {expanded
                ? "Show fewer samples"
                : `View all ${filteredSamples.length} ${filter === "all" ? "" : filter.toLowerCase()} samples`}
            </span>
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      ) : null}
    </section>
  );
}
