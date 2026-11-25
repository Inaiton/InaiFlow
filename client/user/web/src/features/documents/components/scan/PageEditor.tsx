"use client";

import { RotateCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, SwitchRow } from "@/components/ui";
import { renderPage, type PageEdit } from "../../lib/scan-image";

export interface ScanPageItem { id: string; image: HTMLImageElement; edit: PageEdit }

/** Rotate / crop (margins) / enhance one page with a live preview. */
export function PageEditor({ page, onChange, onRemove }: { page: ScanPageItem; onChange: (e: PageEdit) => void; onRemove: () => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    const url = renderPage(page.image, page.edit).toDataURL("image/jpeg", 0.7);
    const t = requestAnimationFrame(() => setPreview(url));
    return () => cancelAnimationFrame(t);
  }, [page]);
  const e = page.edit;
  const crop = (k: keyof PageEdit["crop"]) => (
    <label className="flex items-center gap-2 text-[12px] text-fg-2">
      <span className="w-12 capitalize">{k}</span>
      <input type="range" min={0} max={40} value={e.crop[k]} onChange={(ev) => onChange({ ...e, crop: { ...e.crop, [k]: Number(ev.target.value) } })} className="flex-1" aria-label={`Crop ${k}`} />
      <span className="tabular w-8 text-right text-fg-muted">{e.crop[k]}%</span>
    </label>
  );
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_260px]">
      <div className="grid min-h-64 place-items-center rounded-xl bg-subtle p-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- local data URL preview */}
        {preview ? <img src={preview} alt="Page preview" className="max-h-[56vh] max-w-full rounded shadow-xs" /> : null}
      </div>
      <div className="flex flex-col gap-3">
        <Button onClick={() => onChange({ ...e, rotation: (((e.rotation + 90) % 360) as PageEdit["rotation"]) })}><RotateCw /> Rotate</Button>
        <SwitchRow label="Enhance" description="Clean white paper, dark text" checked={e.enhance} onCheckedChange={(v) => onChange({ ...e, enhance: v })} />
        <div className="flex flex-col gap-1.5">
          <span className="text-[12.5px] font-medium text-fg-2">Crop edges</span>
          {crop("top")}{crop("bottom")}{crop("left")}{crop("right")}
        </div>
        <Button variant="destructive" onClick={onRemove}><Trash2 /> Remove page</Button>
      </div>
    </div>
  );
}
