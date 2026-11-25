import type { Metadata } from "next";
import { OrgCreateWizard } from "@/features/org-create/components/OrgCreateWizard";

export const metadata: Metadata = { title: "Create organization" };
export default function Page() {
  return <OrgCreateWizard />;
}
