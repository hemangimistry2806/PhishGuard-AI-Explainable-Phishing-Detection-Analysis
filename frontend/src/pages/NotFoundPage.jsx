import { Link } from "react-router-dom";
import { Home } from "lucide-react";
import Button from "../components/common/Button.jsx";
import PageHeader from "../components/common/PageHeader.jsx";

export default function NotFoundPage() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="404" title="Page not found" description="The requested PhishGuard AI view does not exist." />
      <Link to="/" className="plain-link">
        <Button icon={Home}>Return to analysis</Button>
      </Link>
    </div>
  );
}
