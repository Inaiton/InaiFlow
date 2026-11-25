import Link from "next/link";
import { Compass } from "lucide-react";
import { Button, EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-6">
      <div className="w-full max-w-md">
        <EmptyState icon={Compass} tone="indigo" title="Page not found" description="The page you’re looking for doesn’t exist or has moved." action={<Button asChild variant="primary"><Link href="/">Go home</Link></Button>} />
      </div>
    </div>
  );
}
