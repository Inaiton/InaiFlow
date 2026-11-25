"use client";

import { useMutation } from "@tanstack/react-query";
import { idempotencyHeader, unwrap } from "@/core/api/client";
import { ApiError } from "@/core/api/errors";
import { uploadToTicket } from "@/core/upload";
import { useAcc } from "../../lib/api-base";

/**
 * Attach a scanned bill to a saved voucher: find `/FY…/MM - Month/Bills & Vouchers` (system_kind BILLS) → upload-url → PUT bytes →
 * complete-upload → POST /accounts/vouchers/{id}/attachments. Needs documents.capture_upload:WRITE.
 */
export function useAttachBill() {
  const { api, invalidate } = useAcc();
  return useMutation({
    mutationFn: async ({ voucherId, voucherDate, file, source }: { voucherId: string; voucherDate: string; file: File; source: "CAMERA_SCAN" | "FILE_UPLOAD" }) => {
      const month = voucherDate.slice(0, 7);
      const roots = await unwrap(api.GET("/api/v1/documents/folders"));
      let folderId: string | null = null;
      for (const fy of roots.filter((f) => f.fy_label)) {
        const months = await unwrap(api.GET("/api/v1/documents/folders", { params: { query: { parent_id: fy.id } } }));
        const m = months.find((f) => f.month_date?.slice(0, 7) === month);
        if (!m) continue;
        const kids = await unwrap(api.GET("/api/v1/documents/folders", { params: { query: { parent_id: m.id } } }));
        folderId = kids.find((f) => f.system_kind === "BILLS")?.id ?? null;
        if (folderId) break;
      }
      if (!folderId) throw new ApiError(404, "NOT_FOUND", "The Bills & Vouchers folder for this month doesn’t exist yet — open Documents once to create it.");
      const out = await unwrap(api.POST("/api/v1/documents/upload-url", {
        params: { header: idempotencyHeader() },
        body: { folder_id: folderId, title: file.name, file_name: file.name, content_type: file.type || "application/pdf", size_bytes: file.size, source_type: source, linked_voucher_id: voucherId },
      }));
      await uploadToTicket(out.upload, file, file.name);
      await unwrap(api.POST("/api/v1/documents/{document_id}/complete-upload", { params: { path: { document_id: out.document.id } }, body: {} }));
      return unwrap(api.POST("/api/v1/accounts/vouchers/{voucher_id}/attachments", { params: { path: { voucher_id: voucherId } }, body: { document_id: out.document.id } }));
    },
    onSuccess: () => invalidate("vouchers"),
    meta: { successMessage: "Bill attached and filed in Documents" },
  });
}
