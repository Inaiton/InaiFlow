import { ApiError, toApiError } from "@/core/api/errors";

type FileResult = { data?: unknown; error?: unknown; response: Response };

function fileNameFrom(res: Response, fallback: string): string {
  const cd = res.headers.get("Content-Disposition") ?? "";
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (star?.[1]) return decodeURIComponent(star[1]);
  const plain = /filename="?([^";]+)"?/i.exec(cd);
  return plain?.[1] ?? fallback;
}

/**
 * Await an openapi-fetch file call made with `parseAs: "blob"` and either save it (default) or open it in a new tab (PDF preview).
 *   await fetchFile(api.GET("/api/v1/accounts/vouchers/{voucher_id}/print", { params, parseAs: "blob" }), "voucher.pdf", "open")
 */
export async function fetchFile(call: Promise<FileResult>, fallbackName: string, mode: "save" | "open" = "save"): Promise<void> {
  let result: FileResult;
  try {
    result = await call;
  } catch (e) {
    throw new ApiError(0, "NETWORK_ERROR", e instanceof Error ? e.message : "Network error");
  }
  if (result.error !== undefined || !result.response.ok || !(result.data instanceof Blob)) throw toApiError(result.response.status, result.error);
  const url = URL.createObjectURL(result.data);
  if (mode === "open") {
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return;
  }
  const a = document.createElement("a");
  a.href = url;
  a.download = fileNameFrom(result.response, fallbackName);
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}
