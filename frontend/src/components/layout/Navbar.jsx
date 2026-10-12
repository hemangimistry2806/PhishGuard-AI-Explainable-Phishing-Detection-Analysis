import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Activity, BarChart3, Home, Menu, MessageSquare, ShieldCheck, X } from "lucide-react";

const links = [
  { to: "/", label: "Analyze", icon: Home },
  { to: "/ai-dashboard", label: "AI Dashboard", icon: Activity },
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/feedback", label: "Feedback", icon: MessageSquare },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="site-header">
      <NavLink to="/" className="brand" aria-label="PhishGuard AI home" onClick={() => setOpen(false)}>
        <span className="brand-mark" aria-hidden="true">
          <ShieldCheck size={22} />
        </span>
        <span>
          <strong>PhishGuard AI</strong>
          <small>Explainable phishing detection</small>
        </span>
      </NavLink>

      <button className="icon-button menu-button" type="button" aria-label="Toggle navigation" onClick={() => setOpen((value) => !value)}>
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      <nav className={`nav-links ${open ? "open" : ""}`} aria-label="Primary navigation">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="nav-link" onClick={() => setOpen(false)}>
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
