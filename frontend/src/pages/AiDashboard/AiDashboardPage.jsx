import { BrainCircuit, FileSearch, ShieldCheck, Workflow } from "lucide-react";
import EmptyState from "../../components/common/EmptyState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import InfoGrid from "../../components/dashboard/InfoGrid.jsx";

export default function AiDashboardPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Model workspace"
        title="AI Dashboard"
        description="A focused view of the finalized prediction and explanation pipeline, ready for future model telemetry."
      />
      <InfoGrid
        items={[
          { icon: BrainCircuit, label: "Model input", value: "50 features", text: "Backend requires the verified PhiUSIIL feature order." },
          { icon: FileSearch, label: "Prediction endpoint", value: "/predict/", text: "Returns label, class id, and class probabilities." },
          { icon: Workflow, label: "Explanation endpoint", value: "/explain/", text: "Returns prediction fields, SHAP features, and optional LLM text." },
          { icon: ShieldCheck, label: "Authentication", value: "Not required", text: "Public analysis remains available until real auth APIs exist." },
        ]}
      />
      <EmptyState
        icon={BrainCircuit}
        title="No model telemetry available"
        text="The current backend does not provide aggregate model metrics or analysis history. This page is structured for that future integration."
      />
    </div>
  );
}
