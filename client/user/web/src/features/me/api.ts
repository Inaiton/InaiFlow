"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useAuth } from "@/core/auth/AuthProvider";
import { myOrgsQuery } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";
import { uploadToTicket } from "@/core/upload";

/* ---------- profile ---------- */
export function useMe() {
  const { setUser } = useAuth();
  return useQuery({
    queryKey: qk.me("profile"),
    queryFn: async () => {
      const me = await unwrap(api.GET("/api/v1/me"));
      setUser(me);
      return me;
    },
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  const { setUser } = useAuth();
  return useMutation({
    mutationFn: (body: Schemas["MeUpdateIn"]) => unwrap(api.PATCH("/api/v1/me", { body })),
    onSuccess: (me) => {
      setUser(me);
      qc.setQueryData(qk.me("profile"), me);
    },
    meta: { successMessage: "Profile saved" },
  });
}

/** Avatar / signature: upload-url → PUT file → PATCH /me with the storage key. */
export function useUploadMeFile(purpose: Schemas["FilePurpose"]) {
  const update = useUpdateMe();
  return useMutation({
    mutationFn: async (file: File) => {
      const ticket = await unwrap(api.POST("/api/v1/me/files/upload-url", { body: { purpose, content_type: file.type, size_bytes: file.size } }));
      await uploadToTicket(ticket, file, file.name);
      return update.mutateAsync(purpose === "AVATAR" ? { avatar_storage_key: ticket.storage_key } : { signature_storage_key: ticket.storage_key });
    },
  });
}

/* ---------- security ---------- */
export const useChangePassword = () =>
  useMutation({ mutationFn: (body: Schemas["PasswordChangeIn"]) => unwrap(api.POST("/api/v1/me/password", { body })), meta: { silentError: true, successMessage: "Password updated" } });

export const useMfaSetup = () => useMutation({ mutationFn: () => unwrap(api.POST("/api/v1/me/mfa/setup")) });

function useMfaMutation<TBody, TOut>(fn: (b: TBody) => Promise<TOut>, successMessage: string) {
  const { reloadUser } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void reloadUser();
      void qc.invalidateQueries({ queryKey: qk.me("profile") });
    },
    meta: { silentError: true, successMessage },
  });
}

export const useMfaEnable = () =>
  useMfaMutation((body: Schemas["MfaCodeIn"]) => unwrap(api.POST("/api/v1/me/mfa/enable", { body })), "Two-factor authentication is on");
export const useMfaDisable = () =>
  useMfaMutation((body: Schemas["MfaDisableIn"]) => unwrap(api.POST("/api/v1/me/mfa/disable", { body })), "Two-factor authentication is off");
export const useRegenerateRecoveryCodes = () =>
  useMutation({ mutationFn: (body: Schemas["MfaCodeIn"]) => unwrap(api.POST("/api/v1/me/mfa/recovery-codes", { body })), meta: { silentError: true } });

export const useSessions = () => useQuery({ queryKey: qk.me("sessions"), queryFn: () => unwrap(api.GET("/api/v1/me/sessions")) });

export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (session_id: string) => unwrap(api.DELETE("/api/v1/me/sessions/{session_id}", { params: { path: { session_id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me("sessions") }),
    meta: { successMessage: "Signed out of that device" },
  });
}

/* ---------- organizations, invitations, join requests ---------- */
export const useMyOrgs = () => useQuery(myOrgsQuery());
export const useInvitations = () => useQuery({ queryKey: qk.me("invitations"), queryFn: () => unwrap(api.GET("/api/v1/me/invitations")) });
export const useMyJoinRequests = () => useQuery({ queryKey: qk.me("join-requests"), queryFn: () => unwrap(api.GET("/api/v1/me/join-requests")) });

export function useAcceptInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitation_id: string) => unwrap(api.POST("/api/v1/me/invitations/{invitation_id}/accept", { params: { path: { invitation_id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me() }),
    meta: { successMessage: "Invitation accepted" },
  });
}

export function useDeclineInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitation_id: string) => unwrap(api.POST("/api/v1/me/invitations/{invitation_id}/decline", { params: { path: { invitation_id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me("invitations") }),
    meta: { successMessage: "Invitation declined" },
  });
}

export function useCreateJoinRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["JoinRequestIn"]) => unwrap(api.POST("/api/v1/me/join-requests", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me("join-requests") }),
    meta: { silentError: true },
  });
}

export function useCancelJoinRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (request_id: string) => unwrap(api.DELETE("/api/v1/me/join-requests/{request_id}", { params: { path: { request_id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me("join-requests") }),
    meta: { successMessage: "Request cancelled" },
  });
}

/* ---------- create organization ---------- */
export const useStates = () =>
  useQuery({ queryKey: qk.meta("states"), queryFn: () => unwrap(api.GET("/api/v1/meta/states")), staleTime: Infinity });

export async function checkSlug(slug: string): Promise<boolean> {
  const res = await unwrap(api.GET("/api/v1/organizations/check-slug", { params: { query: { slug } } }));
  return res.ok;
}

export function useCreateOrg() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["OrgCreateIn"]) => unwrap(api.POST("/api/v1/organizations", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me("organizations") }),
    meta: { silentError: true },
  });
}
