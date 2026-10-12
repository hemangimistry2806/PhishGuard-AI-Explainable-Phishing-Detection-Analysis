export default function InfoGrid({ items }) {
  return (
    <div className="info-grid">
      {items.map(({ label, value, text, icon: Icon }) => (
        <article className="info-card" key={label}>
          {Icon ? <Icon size={22} aria-hidden="true" /> : null}
          <span>{label}</span>
          <strong>{value}</strong>
          <p>{text}</p>
        </article>
      ))}
    </div>
  );
}
