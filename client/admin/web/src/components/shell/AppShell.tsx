"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { Spinner } from "@/components/ui/states";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";

export function AppShell({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [palette, setPalette] = useState(false);

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.altKey && e.key.toLowerCase() === "g") || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) {
        e.preventDefault();
        setPalette(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (status !== "authenticated") {
    return (
      <div className="flex h-screen items-center justify-center text-faint">
        <Spinner className="size-5" />
      </div>
    );
  }
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenPalette={() => setPalette(true)} />
        <main className="flex-1 overflow-y-auto px-6 py-5">{children}</main>
      </div>
      <CommandPalette open={palette} onOpenChange={setPalette} />
    </div>
  );
}

/** Page-level role guard for routes whose list endpoint the admin's role cannot call. */
export function Forbidden() {
  return (
    <div className="mx-auto mt-16 max-w-md text-center">
      <h2 className="text-lg font-semibold text-ink">Not available for your role</h2>
      <p className="mt-1 text-[13px] text-muted">Ask a SUPERADMIN if you need access to this section.</p>
    </div>
  );
}
