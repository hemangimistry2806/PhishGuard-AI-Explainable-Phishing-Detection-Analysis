import { api } from "../../services/api.js";

export default function Footer() {
  return (
    <footer className="site-footer">
      <span>PhishGuard AI</span>
      <span>Backend: {api.baseUrl}</span>
      <span>Public analysis mode</span>
    </footer>
  );
}
