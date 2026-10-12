export default function EmptyState({ icon: Icon, title, text }) {
  return (
    <div className="empty-state">
      {Icon ? (
        <span className="empty-icon" aria-hidden="true">
          <Icon size={22} />
        </span>
      ) : null}
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
