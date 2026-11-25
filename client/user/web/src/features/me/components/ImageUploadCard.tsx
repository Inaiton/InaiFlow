"use client";

import { Upload } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { toast } from "sonner";
import { IMAGE_TYPES, validateFile } from "@/core/upload";
import { Button, Card } from "@/components/ui";

interface ImageUploadCardProps {
  title: string;
  description: string;
  imageUrl: string | null | undefined;
  placeholder: ReactNode;
  hint: string;
  uploading: boolean;
  disabled?: boolean;
  onFile: (file: File) => void;
  maxBytes?: number;
}

/** Image upload card (avatar, signature stamp, org logo, digital stamp). */
export function ImageUploadCard({ title, description, imageUrl, placeholder, hint, uploading, disabled, onFile, maxBytes = 2 * 1024 * 1024 }: ImageUploadCardProps) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <Card title={title} description={description}>
      <div className="grid h-28 place-items-center overflow-hidden rounded-xl border border-dashed border-line-strong bg-canvas">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- short-lived signed storage URL
          <img src={imageUrl} alt={title} className="max-h-24 max-w-full object-contain" />
        ) : (
          placeholder
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-fg-muted">{hint}</span>
        <Button size="sm" onClick={() => input.current?.click()} loading={uploading} disabled={disabled}>
          <Upload /> {imageUrl ? "Replace" : "Upload"}
        </Button>
      </div>
      <input
        ref={input}
        type="file"
        accept={IMAGE_TYPES.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-label={`Upload ${title}`}
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          const err = validateFile(f, { types: IMAGE_TYPES, maxBytes });
          if (err) toast.error(err);
          else onFile(f);
        }}
      />
    </Card>
  );
}
