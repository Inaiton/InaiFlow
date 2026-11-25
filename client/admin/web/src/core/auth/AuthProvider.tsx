"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, refreshSession, setOnAuthLost, type Schemas } from "@/lib/api/client";
import { setAccessToken } from "./token-store";
import { useIdleTimeout } from "./useIdleTimeout";
import { toast } from "sonner";

type AdminMe = Schemas["AdminMeOut"];
type Status = "loading" | "anonymous" | "authenticated";

interface AuthState {
  status: Status;
  admin: AdminMe | null;
  signIn: (result: Schemas["AdminLoginSuccessOut"]) => void;
  signOut: (reason?: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);
const IDLE_MS = 30 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [admin, setAdmin] = useState<AdminMe | null>(null);

  const clear = useCallback(() => {
    setAccessToken(null);
    setAdmin(null);
    setStatus("anonymous");
    qc.clear();
  }, [qc]);

  const signIn = useCallback((result: Schemas["AdminLoginSuccessOut"]) => {
    setAccessToken(result.token.access_token);
    setAdmin(result.admin);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(
    async (reason?: string) => {
      try {
        await api.POST("/api/v1/admin/auth/logout");
      } catch {
        /* best effort */
      }
      clear();
      if (reason) toast.info(reason);
    },
    [clear],
  );

  useEffect(() => {
    let alive = true;
    setOnAuthLost(() => clear());
    refreshSession().then((r) => {
      if (!alive) return;
      if (r) {
        setAdmin(r.admin);
        setStatus("authenticated");
      } else setStatus("anonymous");
    });
    return () => {
      alive = false;
      setOnAuthLost(null);
    };
  }, [clear]);

  useIdleTimeout(status === "authenticated", IDLE_MS, () => {
    void signOut("Signed out after 30 minutes of inactivity.");
  });

  const value = useMemo(() => ({ status, admin, signIn, signOut }), [status, admin, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
