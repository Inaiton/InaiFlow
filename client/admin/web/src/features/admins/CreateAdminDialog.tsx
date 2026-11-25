"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { CopyButton } from "@/components/ui/misc";
import { Spinner } from "@/components/ui/states";
import { errorMessage } from "@/lib/api/errors";
import type { Schemas } from "@/lib/api/client";
import { useCreateAdmin } from "./api";

const schema = z.object({
  email: z.email("Enter a valid email"),
  full_name: z.string().min(2, "Name is required"),
  role: z.enum(["SUPERADMIN", "SUPPORT_ADMIN", "BILLING_ADMIN"]),
});
type Values = z.infer<typeof schema>;

export function CreateAdminDialog({ onClose }: { onClose: () => void }) {
  const m = useCreateAdmin();
  const [created, setCreated] = useState<Schemas["AdminAccountCreatedOut"] | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", full_name: "", role: "SUPPORT_ADMIN" } });
  const submit = form.handleSubmit((v) => m.mutate(v, { onSuccess: setCreated, onError: (e) => toast.error(errorMessage(e)) }));
  const e = form.formState.errors;

  if (created) {
    return (
      <Dialog open onOpenChange={(o) => !o && onClose()}>
        <DialogContent title="Admin created" description={`${created.admin.email} · ${created.admin.role}`} footer={<Button variant="primary" onClick={onClose}>Done</Button>}>
          <p className="mb-2 rounded-md bg-warning-tint px-3 py-2 text-[13px] text-warning-ink">This temporary password is shown only once. Share it over a secure channel; the admin must change it and set up TOTP at first sign-in.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 select-all rounded-md bg-subtle px-3 py-2 font-mono text-sm text-ink">{created.temporary_password}</code>
            <CopyButton value={created.temporary_password} />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title="New platform admin"
        footer={
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={() => void submit()} disabled={m.isPending}>
              {m.isPending ? <Spinner /> : null} Create admin
            </Button>
          </>
        }
      >
        <form onSubmit={submit} className="space-y-3" noValidate>
          <Field label="Email" error={e.email?.message}>
            <Input type="email" {...form.register("email")} />
          </Field>
          <Field label="Full name" error={e.full_name?.message}>
            <Input {...form.register("full_name")} />
          </Field>
          <Field label="Role">
            <NativeSelect {...form.register("role")}>
              <option value="SUPPORT_ADMIN">Support admin — orgs/users, lifecycle (no archive), impersonation</option>
              <option value="BILLING_ADMIN">Billing admin — plans, billing, org plan changes</option>
              <option value="SUPERADMIN">Superadmin — everything</option>
            </NativeSelect>
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
