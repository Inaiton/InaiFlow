"use client";

import { useDeferredValue, useState } from "react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { useOrgs } from "@/features/organizations/api";
import { usePushConfig } from "./api";

export function PushDialog({ configId, label, onClose }: { configId: string; label: string; onClose: () => void }) {
  const [all, setAll] = useState(false);
  const [q, setQ] = useState("");
  const dq = useDeferredValue(q);
  const [picked, setPicked] = useState<Map<string, string>>(new Map());
  const orgs = useOrgs({ q: dq, limit: 10, offset: 0 });
  const m = usePushConfig(configId);
  const toggle = (id: string, name: string) =>
    setPicked((p) => {
      const n = new Map(p);
      if (n.has(id)) n.delete(id);
      else n.set(id, name);
      return n;
    });

  return (
    <ConfirmReasonDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Push to organizations"
      description={`Offer the current version of “${label}” to existing organizations. Orgs that customised it may be skipped.`}
      confirmLabel={all ? "Push to all organizations" : `Push to ${picked.size} org(s)`}
      destructive={all}
      pending={m.isPending}
      extraValid={all || picked.size > 0}
      onConfirm={(reason) =>
        m.mutate(all ? { all_orgs: true, reason } : { org_ids: [...picked.keys()], reason }, {
          onSuccess: (r) => {
            toast.success(`Pushed: ${r.orgs_updated} updated, ${r.orgs_skipped} skipped`);
            onClose();
          },
          onError: (e) => toast.error(errorMessage(e)),
        })
      }
    >
      <label className="flex items-center gap-2 text-[13px] text-ink-2">
        <input type="checkbox" className="size-4 accent-[#C35E49]" checked={all} onChange={(e) => setAll(e.target.checked)} />
        All organizations
      </label>
      {!all ? (
        <>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search organizations…" aria-label="Search organizations" />
          <ul className="max-h-48 overflow-y-auto rounded-md border border-line">
            {orgs.data?.items.map((o) => (
              <li key={o.id} className="border-b border-line last:border-0">
                <label className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-[13px] hover:bg-canvas">
                  <input type="checkbox" className="size-4 accent-[#C35E49]" checked={picked.has(o.id)} onChange={() => toggle(o.id, o.legal_name)} />
                  <span className="text-ink">{o.legal_name}</span>
                  <span className="ml-auto font-mono text-[11px] text-faint">{o.public_join_code}</span>
                </label>
              </li>
            ))}
          </ul>
          {picked.size ? <p className="text-xs text-faint">Selected: {[...picked.values()].join(", ")}</p> : null}
        </>
      ) : null}
    </ConfirmReasonDialog>
  );
}
