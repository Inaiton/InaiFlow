"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import type { Schemas } from "@/core/api/types";
import { describeError } from "@/core/api/error-messages";
import { useAccHref } from "../../lib/api-base";
import { useSaveVoucher } from "../api";
import { useAttachBill } from "./attach";

/** Save (create/edit) with a per-submission Idempotency-Key, then attach the bill and open the printable view. */
export function useVoucherSave(editId?: string) {
  const router = useRouter();
  const href = useAccHref();
  const save = useSaveVoucher();
  const attach = useAttachBill();
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [serverError, setServerError] = useState<string | null>(null);

  const submit = async (body: Schemas["VoucherIn"], file: File | null, then: "view" | "next") => {
    setServerError(null);
    try {
      const v = await save.mutateAsync({ id: editId, body, key });
      setKey(crypto.randomUUID());
      toast.success(`${v.voucher_type_name} ${v.voucher_number} ${editId ? "altered" : "saved"}`);
      if (file) {
        try {
          await attach.mutateAsync({ voucherId: v.id, voucherDate: v.voucher_date, file, source: file.type.startsWith("image/") ? "CAMERA_SCAN" : "FILE_UPLOAD" });
        } catch (e) {
          toast.error(`Voucher saved, but the bill wasn’t attached: ${describeError(e)}`);
        }
      }
      if (then === "view" || editId) router.push(href(`/vouchers/${v.id}?saved=1`));
      return v;
    } catch (e) {
      setServerError(describeError(e)); // same key is reused on retry
      return null;
    }
  };
  return { submit, saving: save.isPending || attach.isPending, serverError };
}
