import type { LucideIcon } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/ui";

/** Placeholder landing used until W2/W3 replace a module's pages. */
export function ComingSoon({ module, title, icon }: { module: string; title: string; icon: LucideIcon }) {
  return (
    <>
      <PageHeader crumbs={[{ label: module }]} title={title} />
      <EmptyState icon={icon} tone="indigo" title={`${module} is coming soon`} description="This module is being built. Navigation, permissions and shortcuts are already wired." />
    </>
  );
}
