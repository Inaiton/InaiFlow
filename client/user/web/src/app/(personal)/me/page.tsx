import type { Metadata } from "next";
import { PersonalHome } from "@/features/me/components/PersonalHome";

export const metadata: Metadata = { title: "Personal space" };
export default function Page() {
  return <PersonalHome />;
}
