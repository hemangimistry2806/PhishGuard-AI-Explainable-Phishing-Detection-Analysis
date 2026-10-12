import { CheckCircle2, ShieldAlert } from "lucide-react";
import { motion } from "framer-motion";

export default function SampleSelector({ samples, selectedSample, onSelect }) {
  return (
    <section className="panel">
      <div className="section-title">
        <span>Verified dataset samples</span>
        <small>{samples.length} samples</small>
      </div>
      <div className="sample-grid">
        {samples.map((sample, index) => {
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
              <span className={`status-pill ${isPhishing ? "danger" : "success"}`}>
                {isPhishing ? <ShieldAlert size={14} /> : <CheckCircle2 size={14} />}
                Sample {index + 1}
              </span>
              <strong>{sample.label}</strong>
              <code>{sample.url}</code>
              <span>{sample.description}</span>
            </motion.button>
          );
        })}
      </div>
    </section>
  );
}
