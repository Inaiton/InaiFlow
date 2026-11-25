"use client";

import { Copy, Download } from "lucide-react";
import { toast } from "sonner";
import { Button, Hint } from "@/components/ui";

export function downloadText(fileName: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

/** One-time display of MFA recovery codes with download/copy. */
export function RecoveryCodes({ codes }: { codes: string[] }) {
  const text = `InaiFlow recovery codes — each works once.\n\n${codes.join("\n")}\n`;
  return (
    <div className="flex flex-col gap-3">
      <Hint tone="warning" title="Save these backup codes now">They are shown only once. Each code signs you in once if you lose your phone.</Hint>
      <ul className="grid grid-cols-2 gap-2 rounded-xl bg-subtle p-3 font-mono text-[13px]">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => downloadText("inaiflow-recovery-codes.txt", text)}><Download /> Download backup codes</Button>
        <Button size="sm" variant="ghost" onClick={() => void navigator.clipboard.writeText(codes.join("\n")).then(() => toast.success("Copied"))}><Copy /> Copy</Button>
      </div>
    </div>
  );
}
