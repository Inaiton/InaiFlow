import { Stepper } from "@/components/ui";

/** The three-step inspection report wizard header (design Doc-Report-New / Editor / Review). */
export function ReportSteps({ current }: { current: 0 | 1 | 2 }) {
  return (
    <Stepper current={current} steps={[
      { title: "What is this report for?", description: "Pick a template, run and step" },
      { title: "Fill in the results", description: "Readings are pre-filled — change only what you measured" },
      { title: "Review & sign", description: "Check the page, then send for approval" },
    ]} />
  );
}
