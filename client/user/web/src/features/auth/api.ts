"use client";

import { useMutation } from "@tanstack/react-query";
import { api, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";

/** Auth mutations. All are public endpoints on the personal client (no org header). */
export const useLogin = () =>
  useMutation({ mutationFn: (body: Schemas["LoginIn"]) => unwrap(api.POST("/api/v1/auth/login", { body })), meta: { silentError: true } });

export const useMfaVerify = () =>
  useMutation({ mutationFn: (body: Schemas["MfaVerifyIn"]) => unwrap(api.POST("/api/v1/auth/mfa/verify", { body })), meta: { silentError: true } });

export const useSignup = () =>
  useMutation({ mutationFn: (body: Schemas["SignupIn"]) => unwrap(api.POST("/api/v1/auth/signup", { body })) });

export const useVerifyEmail = () =>
  useMutation({ mutationFn: (body: Schemas["VerifyEmailIn"]) => unwrap(api.POST("/api/v1/auth/verify-email", { body })), meta: { silentError: true } });

export const useResendVerification = () =>
  useMutation({
    mutationFn: (body: Schemas["EmailIn"]) => unwrap(api.POST("/api/v1/auth/resend-verification", { body })),
    meta: { successMessage: "A new code is on its way." },
  });

export const useForgotPassword = () =>
  useMutation({ mutationFn: (body: Schemas["EmailIn"]) => unwrap(api.POST("/api/v1/auth/password/forgot", { body })) });

export const useResetPassword = () =>
  useMutation({ mutationFn: (body: Schemas["PasswordResetIn"]) => unwrap(api.POST("/api/v1/auth/password/reset", { body })), meta: { silentError: true } });

/** Full-page navigation to the server's Google OIDC start (302 chain → /auth/callback). */
export function startGoogleLogin(next: string) {
  const redirect = `/auth/callback?next=${encodeURIComponent(next)}`;
  // Full navigation to an API route (not a Next page) so the server can 302 to Google.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/api/v1/auth/oauth/google/start?redirect_to=${encodeURIComponent(redirect)}`);
}
