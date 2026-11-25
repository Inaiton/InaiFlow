import { useMutation } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export function useAdminLogin() {
  return useMutation({
    mutationFn: (body: Schemas["AdminLoginIn"]) => unwrap(api.POST("/api/v1/admin/auth/login", { body })),
  });
}

export function useAdminMfaVerify() {
  return useMutation({
    mutationFn: (body: Schemas["AdminMfaVerifyIn"]) => unwrap(api.POST("/api/v1/admin/auth/mfa/verify", { body })),
  });
}
