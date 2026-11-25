"use client";

import { Card, KeyValue } from "@/components/ui";
import { formatDate } from "@/core/dates";
import { GST_REG_TYPES, INDUSTRIES } from "../schema";
import type { OrgForm } from "./types";

export function StepReview({ form }: { form: OrgForm }) {
  const v = form.getValues();
  const label = (list: { value: string; label: string }[], val: string) => list.find((x) => x.value === val)?.label ?? val;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Company">
        <KeyValue rows={[
          ["Legal name", v.legal_name], ["Trade name", v.mailing_name || "—"],
          ["Address", [v.address_line1, v.address_line2, v.city, v.pincode].filter(Boolean).join(", ")],
          ["State", v.state_code], ["Contact", `${v.contact_email} · ${v.contact_phone}`],
        ]} />
      </Card>
      <Card title="Tax & books">
        <KeyValue rows={[
          ["GST", `${label(GST_REG_TYPES, v.gst_reg_type)}${v.gstin ? ` · ${v.gstin}` : ""}`], ["PAN", v.pan || "—"], ["TAN", v.tan || "—"],
          ["Financial year from", formatDate(v.fy_begins_from)], ["Books from", formatDate(v.books_beginning_from)],
          ["Workspace", `/o/${v.workspace_slug}`], ["Industry", label(INDUSTRIES, v.industry_type)],
        ]} />
      </Card>
    </div>
  );
}
