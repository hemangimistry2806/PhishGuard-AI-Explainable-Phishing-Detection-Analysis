import { Loader2 } from "lucide-react";

export default function Button({ children, icon: Icon, loading = false, className = "", ...props }) {
  return (
    <button {...props} className={`button ${className}`} disabled={loading || props.disabled}>
      {loading ? <Loader2 className="spin" size={18} /> : Icon ? <Icon size={18} /> : null}
      <span>{children}</span>
    </button>
  );
}
