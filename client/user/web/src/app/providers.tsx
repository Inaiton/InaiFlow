"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Toaster, toast } from "sonner";
import { describeError } from "@/core/api/error-messages";
import { ApiError } from "@/core/api/errors";
import { AuthProvider } from "@/core/auth/AuthProvider";
import { ShortcutProvider } from "@/core/shortcuts/registry";
import { ShellUIProvider } from "@/components/shell/shell-ui";
import { TooltipProvider } from "@/components/ui/popover";

declare module "@tanstack/react-query" {
  interface Register {
    /** `meta: { silentError: true }` on a mutation/query opts out of the global error toast. */
    mutationMeta: { silentError?: boolean; successMessage?: string };
    queryMeta: { silentError?: boolean };
  }
}

function makeClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (err, query) => {
        // Background refetch failures toast; first-load failures render inline ErrorState.
        if (query.meta?.silentError || query.state.data === undefined) return;
        toast.error(describeError(err));
      },
    }),
    mutationCache: new MutationCache({
      onError: (err, _v, _c, mutation) => {
        if (!mutation.meta?.silentError) toast.error(describeError(err));
      },
      onSuccess: (_d, _v, _c, mutation) => {
        if (mutation.meta?.successMessage) toast.success(mutation.meta.successMessage);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      },
      mutations: { retry: false },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <ShortcutProvider>
          <ShellUIProvider>
            <TooltipProvider>
              {children}
              <Toaster position="bottom-right" richColors closeButton toastOptions={{ className: "font-sans text-[13px]" }} />
            </TooltipProvider>
          </ShellUIProvider>
        </ShortcutProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
