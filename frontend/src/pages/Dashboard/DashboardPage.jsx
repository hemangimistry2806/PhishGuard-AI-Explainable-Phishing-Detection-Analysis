import { BarChart3, Clock, Database, ListChecks } from "lucide-react";
import EmptyState from "../../components/common/EmptyState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import InfoGrid from "../../components/dashboard/InfoGrid.jsx";

export default function DashboardPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Operations"
        title="Dashboard Panel"
        description="Operational shell for future analysis history, saved reports, and project-level monitoring."
      />
      <InfoGrid
        items={[
          { icon: ListChecks, label: "Current workflow", value: "Sample analysis", text: "Home page runs the complete verified flow." },
          { icon: Database, label: "History source", value: "Unavailable", text: "No backend endpoint currently exposes user analysis history." },
          { icon: BarChart3, label: "Statistics", value: "Not provided", text: "No invented phishing or legitimate totals are displayed." },
          { icon: Clock, label: "Recent activity", value: "Pending API", text: "Ready for future backend support." },
        ]}
      />
      <EmptyState
        icon={BarChart3}
        title="No dashboard data available"
        text="Real statistics will appear here when the backend provides aggregate analysis data."
      />
    </div>
  );
}
