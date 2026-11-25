import type { Schemas } from "@/core/api/types";
import { ApiError } from "@/core/api/errors";

export type UploadTicket = Schemas["UploadTicket"];

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

/** Same-origin rewrite for the dev local-storage provider so the PUT goes through /api/v1. */
function resolveUploadUrl(url: string): string {
  try {
    const u = new URL(url, window.location.origin);
    if (u.pathname.startsWith("/api/v1/storage/local/")) return u.pathname + u.search;
    return u.toString();
  } catch {
    return url;
  }
}

/**
 * Upload a file to an `UploadTicket` from the API (avatar, logo, documents…).
 * When the ticket supplies a Content-Type header the raw bytes are sent; otherwise the file is sent
 * as multipart field `file` (local dev storage + Supabase signed upload URLs accept multipart).
 */
export async function uploadToTicket(ticket: UploadTicket, file: Blob, fileName = "upload"): Promise<void> {
  const headers = new Headers(ticket.headers);
  const hasContentType = headers.has("Content-Type");
  let body: BodyInit;
  if (hasContentType) body = file;
  else {
    const form = new FormData();
    form.append("file", file, fileName);
    body = form;
  }
  let res: Response;
  try {
    res = await fetch(resolveUploadUrl(ticket.upload_url), { method: ticket.method || "PUT", headers, body });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Upload failed — check your connection.");
  }
  if (!res.ok) throw new ApiError(res.status, "UPLOAD_INCOMPLETE", "The upload didn’t finish. Try again.");
}

export function validateFile(file: File, opts: { types?: string[]; maxBytes?: number } = {}): string | null {
  const { types, maxBytes = MAX_UPLOAD_BYTES } = opts;
  if (types && !types.includes(file.type)) return "That file type isn’t supported.";
  if (file.size > maxBytes) return `That file is too large (max ${Math.round(maxBytes / 1024 / 1024)} MB).`;
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}
