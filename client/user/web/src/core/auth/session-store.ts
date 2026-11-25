import type { Schemas } from "@/core/api/types";

export type MeOut = Schemas["MeOut"];

export interface ImpersonationSession {
  orgId: string | null;
  orgSlug: string | null;
}

export interface SessionState {
  /** Short-lived access JWT. Lives ONLY in this module's memory — never web storage. */
  accessToken: string | null;
  user: MeOut | null;
  /** Set when the tab runs on a support impersonation token (no refresh cookie). */
  impersonation: ImpersonationSession | null;
  /** True once the initial refresh attempt (on page load) has finished. */
  bootstrapped: boolean;
}

export type SessionEndReason = "expired" | "logout" | "impersonation-ended";

let state: SessionState = { accessToken: null, user: null, impersonation: null, bootstrapped: false };
const listeners = new Set<() => void>();
let endHandler: ((reason: SessionEndReason) => void) | null = null;

function emit() {
  for (const l of listeners) l();
}

export const sessionStore = {
  get: (): SessionState => state,
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  setSession(accessToken: string, user: MeOut | null) {
    state = { ...state, accessToken, user: user ?? state.user };
    emit();
  },
  setUser(user: MeOut) {
    state = { ...state, user };
    emit();
  },
  startImpersonation(accessToken: string, imp: ImpersonationSession) {
    state = { accessToken, user: null, impersonation: imp, bootstrapped: true };
    emit();
  },
  markBootstrapped() {
    if (state.bootstrapped) return;
    state = { ...state, bootstrapped: true };
    emit();
  },
  clear() {
    state = { accessToken: null, user: null, impersonation: null, bootstrapped: true };
    emit();
  },
  /** Registered by AuthProvider; called when the session can no longer be refreshed. */
  onSessionEnd(handler: ((reason: SessionEndReason) => void) | null) {
    endHandler = handler;
  },
  end(reason: SessionEndReason) {
    const wasImpersonating = state.impersonation !== null;
    this.clear();
    endHandler?.(wasImpersonating && reason === "expired" ? "impersonation-ended" : reason);
  },
};
