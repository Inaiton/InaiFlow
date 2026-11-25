import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export interface InvoiceFilters {
  org_id?: string;
  status?: string;
  limit: number;
  offset: number;
}

export const billingKeys = { all: ["admin", "billing"] as const, list: (f: InvoiceFilters) => ["admin", "billing", "invoices", f] as const };

export function useInvoices(f: InvoiceFilters, enabled: boolean) {
  return useQuery({
    queryKey: billingKeys.list(f),
    queryFn: () => unwrap(api.GET("/api/v1/admin/billing/invoices", { params: { query: { ...f, org_id: f.org_id || undefined, status: f.status || undefined } } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useCreateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["SubscriptionInvoiceIn"]) => unwrap(api.POST("/api/v1/admin/billing/invoices", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: billingKeys.all }),
  });
}

export function useSetInvoiceStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Schemas["InvoiceStatusIn"]) =>
      unwrap(api.PATCH("/api/v1/admin/billing/invoices/{invoice_id}", { params: { path: { invoice_id: id } }, body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: billingKeys.all }),
  });
}
