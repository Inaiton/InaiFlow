import type { Metadata } from "next";
import { Suspense } from "react";
import { LaunchRunPage } from "@/features/operations/components/runs/LaunchRunPage";

export const metadata: Metadata = { title: "Launch run" };
export default function Page() {
  return <Suspense><LaunchRunPage /></Suspense>;
}
