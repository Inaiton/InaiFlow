"use client";

import { FileWarning, Lock } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button, EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useCan } from "@/core/permissions/Can";
import { useInventoryDefaults } from "../inventory/defaults";
import { useAccHref } from "../lib/api-base";
import { kindOf, type VoucherKind } from "../lib/voucher-kinds";
import { useVoucherTypes } from "../masters/api";
import { useVoucher } from "./api";
import { VoucherEntry } from "./entry/VoucherEntry";

function Loading() {
  return <div className="flex flex-col gap-3"><Skeleton className="h-10 w-64" /><Skeleton className="h-[480px] w-full" /></div>;
}

function Ready({ kind, editId }: { kind: VoucherKind; editId?: string }) {
  const types = useVoucherTypes();
  const inv = useInventoryDefaults(kind);
  const voucher = useVoucher(editId);
  if (types.isPending || inv.loading || (editId && voucher.isPending)) return <Loading />;
  if (types.isError) return <ErrorState message={describeError(types.error)} onRetry={() => void types.refetch()} />;
  if (voucher.isError) return <ErrorState message={describeError(voucher.error)} onRetry={() => void voucher.refetch()} />;
  const list = types.data.filter((t) => t.base_type === kind.base);
  if (list.length === 0) return <EmptyState icon={FileWarning} title={`No ${kind.label} voucher type`} description="Create one under Masters → Voucher types." />;
  const sorted = [...list].sort((a, b) => Number(b.is_system) - Number(a.is_system));
  return <VoucherEntry key={`${kind.base}-${editId ?? "new"}`} kind={kind} types={sorted} voucher={voucher.data} />;
}

/** /accounts/vouchers/new?type=SALES */
export function VoucherNewPage() {
  const params = useSearchParams();
  const href = useAccHref();
  const canWrite = useCan("accounts.vouchers", "WRITE");
  const kind = kindOf(params.get("type") ?? "JOURNAL");
  if (!canWrite) return <EmptyState icon={Lock} tone="warning" title="You can view vouchers but not create them" description="Ask an admin for Write access to accounts.vouchers." />;
  if (!kind) return <EmptyState icon={FileWarning} title="Unknown voucher type" action={<Button asChild variant="primary"><Link href={href("/vouchers/new?type=JOURNAL")}>New journal</Link></Button>} />;
  return <Ready kind={kind} />;
}

/** /accounts/vouchers/[id]/edit */
export function VoucherEditPage({ id }: { id: string }) {
  const voucher = useVoucher(id);
  const canWrite = useCan("accounts.vouchers", "WRITE");
  if (!canWrite) return <EmptyState icon={Lock} tone="warning" title="You can’t alter vouchers" description="Write access to accounts.vouchers is required." />;
  if (voucher.isPending) return <Loading />;
  if (voucher.isError) return <ErrorState message={describeError(voucher.error)} onRetry={() => void voucher.refetch()} />;
  const kind = kindOf(voucher.data.base_type);
  if (!kind || voucher.data.status === "CANCELLED") return <EmptyState icon={FileWarning} title="This voucher can’t be altered" description={voucher.data.status === "CANCELLED" ? "Cancelled vouchers are kept for the audit trail." : "System vouchers (payroll, run postings) are altered from their source module."} />;
  return <Ready kind={kind} editId={id} />;
}
