"use client";

import { FileCheck2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Card, Field, Hint, Input, PageHeader, Stepper } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { formatDate, todayIso } from "@/core/dates";
import { cn } from "@/lib/utils";
import { useUploadDocument } from "../../api/documents";
import { useFolder, type FolderOut } from "../../api/folders";
import { useCurrentMonthFolder } from "../../lib/folders";
import { stitchPdf } from "../../lib/pdf-stitch";
import { DEFAULT_EDIT, canvasToJpeg, loadImage, renderPage } from "../../lib/scan-image";
import { useDocsPath } from "../../paths";
import { FolderPickerDialog } from "../explorer/FolderPickerDialog";
import { CameraCapture } from "./CameraCapture";
import { PageEditor, type ScanPageItem } from "./PageEditor";

/** /documents/scan — camera scanner: capture pages → tidy → one PDF filed in the right folder (design Doc-Scan). */
export function ScanPage() {
  const d = useDocsPath();
  const router = useRouter();
  const params = useSearchParams();
  const runId = params.get("run");
  const stepId = params.get("step");
  const voucherId = params.get("voucher");
  const paramFolder = useFolder(params.get("folder"));
  const monthFolder = useCurrentMonthFolder("BILLS", !params.get("folder"));
  const [picked, setPicked] = useState<FolderOut | null>(null);
  const folder = picked ?? paramFolder.data ?? monthFolder.data ?? null;
  const [pages, setPages] = useState<ScanPageItem[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState(`Scan ${formatDate(todayIso())}`);
  const [choosing, setChoosing] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const upload = useUploadDocument();

  const addCapture = async (blob: Blob) => {
    try {
      const image = await loadImage(blob);
      const id = crypto.randomUUID();
      setPages((p) => [...p, { id, image, edit: DEFAULT_EDIT }]);
      setCurrent(id);
      toast.success("Page added", { duration: 1200 });
    } catch {
      toast.error("That file isn’t an image.");
    }
  };
  const sel = pages.find((p) => p.id === current) ?? pages[0];

  const save = async () => {
    if (!folder || pages.length === 0) return;
    try {
      setProgress(0);
      const rendered = await Promise.all(pages.map(async (p) => {
        const c = renderPage(p.image, p.edit);
        return { jpeg: await canvasToJpeg(c), width: c.width, height: c.height };
      }));
      const pdf = await stitchPdf(rendered, title);
      const file = new File([pdf], `${title.replace(/[^\w\- ]+/g, "").trim() || "scan"}.pdf`, { type: "application/pdf" });
      const doc = await upload.mutateAsync({ file, onProgress: setProgress, meta: {
        folder_id: folder.id, title: title.trim() || "Scan", source_type: "CAMERA_SCAN",
        linked_period_run_id: runId, linked_step_id: stepId, linked_voucher_id: voucherId,
      } });
      toast.success("Scan saved", { description: `${pages.length} page(s) · ${folder.name}` });
      router.push(d(`?folder=${doc.folder_id}&doc=${doc.id}`));
    } catch (e) {
      setProgress(null);
      toast.error(describeError(e));
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Scanner" }]} title="Scan a document" description="Snap each page, tidy it up, and we file one clean PDF for you"
        actions={step < 2
          ? <Button variant="primary" disabled={pages.length === 0} onClick={() => setStep(step + 1)}>Next</Button>
          : <Button variant="primary" disabled={!folder || !title.trim()} loading={progress !== null} onClick={() => void save()}><FileCheck2 /> Save PDF{progress !== null ? ` · ${progress}%` : ""}</Button>} />
      <Stepper current={step} steps={[{ title: "Capture", description: "One photo per page" }, { title: "Tidy up", description: "Rotate, crop, enhance" }, { title: "Save", description: "Choose the folder" }]} />
      {runId ? <Hint tone="sky">This scan will be attached to the run step you came from.</Hint> : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <Card>
          {step === 0 ? <CameraCapture onCapture={(b) => void addCapture(b)} /> : null}
          {step === 1 && sel ? (
            <PageEditor page={sel} onChange={(edit) => setPages((ps) => ps.map((p) => (p.id === sel.id ? { ...p, edit } : p)))}
              onRemove={() => { setPages((ps) => ps.filter((p) => p.id !== sel.id)); setCurrent(null); if (pages.length === 1) setStep(0); }} />
          ) : null}
          {step === 2 ? (
            <div className="flex flex-col gap-3.5">
              <Field label="Title" required><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
              <Field label="Save to" hint={folder ? undefined : "This month’s folders don’t exist yet — pick a folder"}>
                <div className="flex items-center gap-2">
                  <span className="flex-1 truncate rounded-lg border border-line bg-canvas px-3 py-2 text-[13px] text-fg">{folder?.name ?? "No folder chosen"}</span>
                  <Button onClick={() => setChoosing(true)}>Change</Button>
                </div>
              </Field>
              <p className="m-0 text-xs text-fg-muted">{pages.length} page(s) · stitched into one PDF on this device before upload. Text recognition (OCR) comes later.</p>
            </div>
          ) : null}
        </Card>
        <Card title={`Pages (${pages.length})`}>
          {pages.length === 0 ? <p className="m-0 text-xs text-fg-muted">Captured pages appear here.</p> : (
            <ol className="m-0 grid list-none grid-cols-3 gap-2 p-0 lg:grid-cols-2">
              {pages.map((p, i) => (
                <li key={p.id}>
                  <button type="button" onClick={() => { setCurrent(p.id); if (step === 0) setStep(1); }} className={cn("relative block w-full overflow-hidden rounded-lg border-2", sel?.id === p.id && step === 1 ? "border-primary" : "border-line")}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
                    <img src={p.image.src} alt={`Page ${i + 1}`} className="aspect-[3/4] w-full object-cover" style={{ transform: `rotate(${p.edit.rotation}deg)` }} />
                    <span className="absolute bottom-1 left-1 rounded bg-ink/70 px-1.5 text-[11px] text-white">{i + 1}</span>
                  </button>
                </li>
              ))}
            </ol>
          )}
          {step > 0 ? <Button size="sm" onClick={() => setStep(0)}>Add more pages</Button> : null}
        </Card>
      </div>
      <FolderPickerDialog open={choosing} onOpenChange={setChoosing} title="Save scan to…" onPick={(f) => { setPicked(f); setChoosing(false); }} />
    </div>
  );
}
