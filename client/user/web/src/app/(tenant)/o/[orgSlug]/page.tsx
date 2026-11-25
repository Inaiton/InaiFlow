import { Suspense } from "react";
import { TenantHome } from "@/features/tenant/TenantHome";

export default function Page() {
  return (
    <Suspense>
      <TenantHome />
    </Suspense>
  );
}
