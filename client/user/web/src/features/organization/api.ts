"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/core/api/client";
import type { Schemas } from "@/core/api/types";
import { useOrg } from "@/core/org/OrgProvider";
import { qk } from "@/core/query-keys";
import { uploadToTicket } from "@/core/upload";

/**
 * Organization module hooks. Pattern for every feature (W2/W3 copy this):
 *  - `const { orgId, api } = useOrg()` — org-bound client, header injected
 *  - query keys `qk.org(orgId, "<domain>", ...)`
 *  - `unwrap(...)` throws ApiError; mutations toast errors globally (opt out with meta.silentError)
 */
const KEY = "organization" as const;

function useOrgKey() {
  const { orgId } = useOrg();
  return (...rest: unknown[]) => qk.org(orgId, KEY, ...rest);
}

function useInvalidate() {
  const qc = useQueryClient();
  const { orgId } = useOrg();
  return (...rest: unknown[]) => qc.invalidateQueries({ queryKey: qk.org(orgId, KEY, ...rest) });
}

/* ---------- profile & branches ---------- */
export function useOrgProfile() {
  const { api } = useOrg();
  const key = useOrgKey();
  return useQuery({ queryKey: key("profile"), queryFn: () => unwrap(api.GET("/api/v1/organization/profile")) });
}

export function useUpdateOrgProfile() {
  const { api, refetchContext } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["OrgUpdateIn"]) => unwrap(api.PATCH("/api/v1/organization/profile", { body })),
    onSuccess: () => {
      void inv("profile");
      refetchContext();
    },
    meta: { successMessage: "Organization profile saved" },
  });
}

export function useUploadOrgFile(purpose: Schemas["OrgFilePurpose"]) {
  const { api } = useOrg();
  const update = useUpdateOrgProfile();
  return useMutation({
    mutationFn: async (file: File) => {
      const ticket = await unwrap(api.POST("/api/v1/organization/files/upload-url", { body: { purpose, content_type: file.type, size_bytes: file.size } }));
      await uploadToTicket(ticket, file, file.name);
      return update.mutateAsync(purpose === "LOGO" ? { logo_storage_key: ticket.storage_key } : { stamp_storage_key: ticket.storage_key });
    },
  });
}

export function useBranches() {
  const { api } = useOrg();
  const key = useOrgKey();
  return useQuery({ queryKey: key("branches"), queryFn: () => unwrap(api.GET("/api/v1/organization/branches")) });
}

export function useSaveBranch() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["BranchIn"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/organization/branches/{branch_id}", { params: { path: { branch_id: id } }, body }))
        : unwrap(api.POST("/api/v1/organization/branches", { body })),
    onSuccess: () => inv("branches"),
    meta: { successMessage: "Branch saved" },
  });
}

export function useDeleteBranch() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (branch_id: string) => unwrap(api.DELETE("/api/v1/organization/branches/{branch_id}", { params: { path: { branch_id } } })),
    onSuccess: () => inv("branches"),
    meta: { successMessage: "Branch removed" },
  });
}

/* ---------- members, invitations, join requests ---------- */
export function useMembers(query: { q?: string; status?: string } = {}) {
  const { api } = useOrg();
  const key = useOrgKey();
  return useQuery({ queryKey: key("members", query), queryFn: () => unwrap(api.GET("/api/v1/organization/members", { params: { query } })) });
}

export function useUpdateMember() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["MemberUpdateIn"] }) =>
      unwrap(api.PATCH("/api/v1/organization/members/{membership_id}", { params: { path: { membership_id: id } }, body })),
    onSuccess: () => inv("members"),
    meta: { successMessage: "Member updated" },
  });
}

export function useRevokeMember() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (membership_id: string) => unwrap(api.DELETE("/api/v1/organization/members/{membership_id}", { params: { path: { membership_id } } })),
    onSuccess: () => inv("members"),
    meta: { successMessage: "Access revoked" },
  });
}

export function useTransferOwnership() {
  const { api, refetchContext } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["TransferOwnershipIn"]) => unwrap(api.POST("/api/v1/organization/transfer-ownership", { body })),
    onSuccess: () => {
      void inv("members");
      refetchContext();
    },
    meta: { silentError: true, successMessage: "Ownership transferred" },
  });
}

export function useOrgInvitations(status?: string) {
  const { api } = useOrg();
  const key = useOrgKey();
  return useQuery({ queryKey: key("invitations", status ?? "all"), queryFn: () => unwrap(api.GET("/api/v1/organization/invitations", { params: { query: status ? { status } : {} } })) });
}

export function useInvite() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: Schemas["InvitationIn"]) => unwrap(api.POST("/api/v1/organization/invitations", { body })),
    onSuccess: () => inv("invitations"),
    meta: { silentError: true },
  });
}

export function useInvitationAction() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "resend" | "revoke" }) =>
      action === "resend"
        ? unwrap(api.POST("/api/v1/organization/invitations/{invitation_id}/resend", { params: { path: { invitation_id: id } } }))
        : unwrap(api.DELETE("/api/v1/organization/invitations/{invitation_id}", { params: { path: { invitation_id: id } } })),
    onSuccess: () => inv("invitations"),
  });
}

export function useOrgJoinRequests(status?: string) {
  const { api } = useOrg();
  const key = useOrgKey();
  return useQuery({ queryKey: key("join-requests", status ?? "all"), queryFn: () => unwrap(api.GET("/api/v1/organization/join-requests", { params: { query: status ? { status } : {} } })) });
}

export function useDecideJoinRequest() {
  const { api } = useOrg();
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, approve }: { id: string; approve?: Schemas["JoinDecisionIn"] }) =>
      approve
        ? unwrap(api.POST("/api/v1/organization/join-requests/{request_id}/approve", { params: { path: { request_id: id } }, body: approve }))
        : unwrap(api.POST("/api/v1/organization/join-requests/{request_id}/reject", { params: { path: { request_id: id } } })),
    onSuccess: () => {
      void inv("join-requests");
      void inv("members");
    },
  });
}
