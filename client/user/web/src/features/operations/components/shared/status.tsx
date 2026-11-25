import { Badge, type Tone } from "@/components/ui";
import type { Schemas } from "@/core/api/types";

type StepStatus = Schemas["StepStatus"];
type RunStatus = Schemas["RunStatus"];

export const STEP_TONE: Record<StepStatus, Tone> = {
  PENDING: "gray", ACTIVE: "sky", PASSED: "success", REJECTED: "danger", SKIPPED: "violet", LOCKED: "teal",
};
export const STEP_LABEL: Record<StepStatus, string> = {
  PENDING: "Waiting", ACTIVE: "Running", PASSED: "Done", REJECTED: "Rejected", SKIPPED: "Skipped", LOCKED: "Signed off",
};
export const RUN_TONE: Record<RunStatus, Tone> = {
  PLANNED: "indigo", IN_PROGRESS: "sky", QC_HOLD: "warning", COMPLETED: "success", CANCELLED: "danger",
};
export const RUN_LABEL: Record<RunStatus, string> = {
  PLANNED: "Planned", IN_PROGRESS: "In progress", QC_HOLD: "QC hold", COMPLETED: "Completed", CANCELLED: "Cancelled",
};

export function StepStatusBadge({ status }: { status: StepStatus }) {
  return <Badge tone={STEP_TONE[status]} dot>{STEP_LABEL[status]}</Badge>;
}
export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <Badge tone={RUN_TONE[status]} dot>{RUN_LABEL[status]}</Badge>;
}

const INSTRUMENT: Record<string, [Tone, string]> = { VALID: ["success", "Valid"], DUE_SOON: ["warning", "Due soon"], EXPIRED: ["danger", "Expired"] };
export function InstrumentBadge({ status }: { status: string }) {
  const [tone, label] = INSTRUMENT[status] ?? ["gray", status];
  return <Badge tone={tone} dot>{label}</Badge>;
}

const NCR: Record<string, [Tone, string]> = { OPEN: ["danger", "Open"], INVESTIGATING: ["warning", "Investigating"], VERIFIED_CLOSED: ["success", "Closed"] };
export const NCR_STATUSES = Object.keys(NCR);
export function NcrBadge({ status }: { status: string }) {
  const [tone, label] = NCR[status] ?? ["gray", status];
  return <Badge tone={tone} dot>{label}</Badge>;
}

const CHECK: Record<string, [Tone, string]> = {
  NOT_STARTED: ["gray", "Not started"], IN_PROGRESS: ["warning", "In progress"], COMPLIANT: ["success", "Compliant"], NOT_APPLICABLE: ["violet", "Not applicable"],
};
export const CHECKLIST_STATUSES = Object.entries(CHECK).map(([value, [, label]]) => ({ value, label }));
export function ChecklistBadge({ status }: { status: string }) {
  const [tone, label] = CHECK[status] ?? ["gray", status];
  return <Badge tone={tone}>{label}</Badge>;
}

/** "Nov 2026" from a first-of-month date. */
export function periodLabel(periodMonth: string): string {
  const [y, m] = periodMonth.split("-").map(Number);
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];
  return `${names[(m ?? 1) - 1]} ${y}`;
}
