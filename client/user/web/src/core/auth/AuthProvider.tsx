"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { api, refreshSession, unwrap } from "@/core/api/client";
import { sessionStore, type MeOut, type SessionState } from "./session-store";
import { readAccessToken } from "./token";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: MeOut | null;
  isImpersonating: boolean;
  impersonation: SessionState["impersonation"];
  /** Store tokens after /auth/login, /auth/mfa/verify or OAuth refresh. */
  completeLogin: (token: unknown, user: MeOut | null) => void;
  setUser: (user: MeOut) => void;
  reloadUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const SERVER_SNAPSHOT: SessionState = { accessToken: null, user: null, impersonation: null, bootstrapped: false };
const getServerSnapshot = (): SessionState => SERVER_SNAPSHOT;

export function AuthProvider({ children }: { children: ReactNode }) {
  const session = useSyncExternalStore(sessionStore.subscribe, sessionStore.get, getServerSnapshot);
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    // /impersonate installs its own token from the URL fragment; don't race it with a refresh.
    if (window.location.pathname === "/impersonate" || sessionStore.get().accessToken) {
      sessionStore.markBootstrapped();
      return;
    }
    void refreshSession().finally(() => sessionStore.markBootstrapped());
  }, []);

  useEffect(() => {
    sessionStore.onSessionEnd((reason) => {
      queryClient.clear();
      if (reason === "impersonation-ended") router.replace("/impersonate?ended=1");
      else if (reason === "expired") {
        const next = window.location.pathname + window.location.search;
        router.replace(`/login?next=${encodeURIComponent(next)}&expired=1`);
      } else router.replace("/login");
    });
    return () => sessionStore.onSessionEnd(null);
  }, [queryClient, router]);

  const completeLogin = useCallback((token: unknown, user: MeOut | null) => {
    sessionStore.setSession(readAccessToken(token).access_token, user);
  }, []);

  const reloadUser = useCallback(async () => {
    const me = await unwrap(api.GET("/api/v1/me"));
    sessionStore.setUser(me);
  }, []);

  const logout = useCallback(async () => {
    const impersonating = sessionStore.get().impersonation !== null;
    if (!impersonating) {
      try {
        await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include", headers: { "X-Requested-With": "inaiflow" } });
      } catch {
        /* best effort */
      }
    }
    sessionStore.end(impersonating ? "impersonation-ended" : "logout");
  }, []);

  const status: AuthStatus = session.accessToken ? "authenticated" : session.bootstrapped ? "anonymous" : "loading";

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session.user,
      isImpersonating: session.impersonation !== null,
      impersonation: session.impersonation,
      completeLogin,
      setUser: sessionStore.setUser,
      reloadUser,
      logout,
    }),
    [status, session.user, session.impersonation, completeLogin, reloadUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
