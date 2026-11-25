import { Suspense } from "react";
import { ConfigHubPage } from "@/features/config/ConfigHubPage";

export const metadata = { title: "Global config" };

export default function Page() {
  return (
    <Suspense>
      <ConfigHubPage />
    </Suspense>
  );
}
