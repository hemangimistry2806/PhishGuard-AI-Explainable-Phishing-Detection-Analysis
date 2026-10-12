import { motion } from "framer-motion";

export default function PageHeader({ eyebrow, title, description, children }) {
  return (
    <motion.section
      className="page-header"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
    >
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {children ? <div className="page-header-actions">{children}</div> : null}
    </motion.section>
  );
}
