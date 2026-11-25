import type { Schemas } from "@/core/api/types";
import { ApiError } from "@/core/api/errors";

type UploadTicket = Schemas["UploadTicket"];

/** Same-origin rewrite for the dev local-storage provider (mirrors core/upload). */
function resolveUrl(url: string): string {
  try {
    const u = new URL(url, window.location.origin);
    return u.pathname.startsWith("/api/v1/storage/local/") ? u.pathname + u.search : u.toString();
  } catch {
    return url;
  }
}

/**
 * Raw PUT of the file bytes to an UploadTicket with every ticket header (plan §7.1),
 * reporting progress 0–100. XHR is used because fetch has no upload progress.
 */
export function putWithProgress(ticket: UploadTicket, file: Blob, onProgress?: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(ticket.method || "PUT", resolveUrl(ticket.upload_url));
    for (const [k, v] of Object.entries(ticket.headers ?? {})) xhr.setRequestHeader(k, v);
    if (!Object.keys(ticket.headers ?? {}).some((k) => k.toLowerCase() === "content-type") && file.type) xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new ApiError(xhr.status, "UPLOAD_INCOMPLETE", "The upload didn’t finish. Try again.")));
    xhr.onerror = () => reject(new ApiError(0, "NETWORK_ERROR", "Upload failed — check your connection."));
    xhr.send(file);
  });
}

/** Save a Blob as a file download. */
export function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export const ALLOWED_MIME = [
  "application/pdf", "image/png", "image/jpeg", "image/webp", "image/heic",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv", "text/plain",
];

export const fileKind = (mime: string | null | undefined): "pdf" | "image" | "doc" | "sheet" | "text" | "report" | "other" => {
  if (!mime) return "report";
  if (mime === "application/pdf") return "pdf";
  if (mime.startsWith("image/")) return "image";
  if (mime.includes("wordprocessingml")) return "doc";
  if (mime.includes("spreadsheetml") || mime === "text/csv") return "sheet";
  if (mime.startsWith("text/")) return "text";
  return "other";
};

export const titleFromFile = (name: string) => name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim() || name;
