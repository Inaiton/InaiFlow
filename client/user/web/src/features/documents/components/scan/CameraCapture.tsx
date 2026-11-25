"use client";

import { Camera, ImagePlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Hint } from "@/components/ui";

/** Live camera (rear camera on phones) with a capture button; falls back to picking photos. */
export function CameraCapture({ onCapture }: { onCapture: (blob: Blob) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      queueMicrotask(() => setError("This browser can’t open the camera. Pick photos instead."));
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play().then(() => setReady(true)).catch(() => setReady(true));
        }
      })
      .catch(() => setError("Camera access was blocked. Allow the camera, or pick photos instead."));
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const capture = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    c.toBlob((b) => b && onCapture(b), "image/jpeg", 0.92);
  };

  return (
    <div className="flex flex-col gap-3">
      {error ? <Hint tone="warning">{error}</Hint> : (
        <div className="relative overflow-hidden rounded-xl bg-ink">
          <video ref={video} playsInline muted className="aspect-[3/4] w-full object-cover sm:aspect-video" aria-label="Camera preview" />
          <div className="pointer-events-none absolute inset-6 rounded-lg border-2 border-dashed border-white/60" aria-hidden />
        </div>
      )}
      <input ref={fileRef} type="file" accept="image/*" multiple className="sr-only" aria-label="Pick photos"
        onChange={(e) => { Array.from(e.target.files ?? []).forEach(onCapture); e.target.value = ""; }} />
      <div className="flex gap-2">
        {!error ? <Button variant="primary" size="lg" className="flex-1" disabled={!ready} onClick={capture}><Camera /> Capture page</Button> : null}
        <Button size="lg" className={error ? "flex-1" : undefined} onClick={() => fileRef.current?.click()}><ImagePlus /> {error ? "Pick photos" : "Photos"}</Button>
      </div>
    </div>
  );
}
