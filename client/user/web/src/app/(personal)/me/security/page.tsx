import type { Metadata } from "next";
import { SecurityPage } from "@/features/me/components/SecurityPage";

export const metadata: Metadata = { title: "Profile & security" };
export default function Page() {
  return <SecurityPage />;
}
