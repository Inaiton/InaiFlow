"use client";

import {
  flexRender, getCoreRowModel, getPaginationRowModel, getSortedRowModel, useReactTable,
  type ColumnDef, type OnChangeFn, type PaginationState, type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { EmptyState, Skeleton } from "./feedback";

export type { ColumnDef } from "@tanstack/react-table";

export interface ServerPagination {
  /** Contract Page<T> fields. */
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[] | undefined;
  loading?: boolean;
  /** Rendered when `data` is empty (defaults to a calm EmptyState). */
  empty?: ReactNode;
  /** Server-side pagination (Page<T>). Omit for client pagination of `data`. */
  pagination?: ServerPagination;
  pageSize?: number;
  onRowClick?: (row: T) => void;
  getRowId?: (row: T) => string;
  /** Column ids to right-align (numbers/money). Or set `meta: { align: "right" }` on a column. */
  minWidth?: number;
  className?: string;
  "aria-label"?: string;
}

type ColMeta = { align?: "left" | "right" | "center"; className?: string };

/**
 * Table wrapper over TanStack Table v8 with the design's table styling (uppercase grey header,
 * row dividers), sorting, client or server pagination, skeleton rows and empty state.
 */
export function DataTable<T>({
  columns, data, loading, empty, pagination, pageSize = 25, onRowClick, getRowId, minWidth = 640, className, ...aria
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [page, setPage] = useState<PaginationState>({ pageIndex: 0, pageSize });
  const manual = Boolean(pagination);
  const table = useReactTable<T>({
    data: data ?? [],
    columns,
    state: { sorting, ...(manual ? {} : { pagination: page }) },
    onSortingChange: setSorting as OnChangeFn<SortingState>,
    onPaginationChange: manual ? undefined : setPage,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    ...(manual ? { manualPagination: true } : { getPaginationRowModel: getPaginationRowModel() }),
    getRowId,
  });

  const rows = table.getRowModel().rows;
  const colCount = table.getVisibleLeafColumns().length;
  const total = pagination ? pagination.total : (data?.length ?? 0);
  const from = pagination ? pagination.offset : page.pageIndex * page.pageSize;
  const size = pagination ? pagination.limit : page.pageSize;
  const to = Math.min(from + size, total);
  const canPrev = from > 0;
  const canNext = to < total;
  const go = (dir: -1 | 1) => {
    if (pagination) pagination.onOffsetChange(Math.max(0, pagination.offset + dir * pagination.limit));
    else setPage((p) => ({ ...p, pageIndex: p.pageIndex + dir }));
  };

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px] text-fg-3" style={{ minWidth }} aria-label={aria["aria-label"]} aria-busy={loading || undefined}>
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="bg-subtle text-[11px] tracking-[0.4px] text-fg-muted">
                {hg.headers.map((h, i) => {
                  const meta = (h.column.columnDef.meta ?? {}) as ColMeta;
                  const sortable = h.column.getCanSort() && h.column.columnDef.enableSorting !== false && Boolean(h.column.accessorFn);
                  const dir = h.column.getIsSorted();
                  return (
                    <th
                      key={h.id}
                      scope="col"
                      aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                      className={cn(
                        "px-2.5 py-2 font-semibold whitespace-nowrap uppercase",
                        i === 0 && "rounded-l-lg",
                        i === hg.headers.length - 1 && "rounded-r-lg",
                        meta.align === "right" ? "text-right" : meta.align === "center" ? "text-center" : "text-left",
                      )}
                    >
                      {h.isPlaceholder ? null : sortable ? (
                        <button type="button" onClick={h.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 uppercase hover:text-fg">
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {dir === "asc" ? <ArrowUp className="size-3" /> : dir === "desc" ? <ArrowDown className="size-3" /> : null}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 5 }, (_, r) => (
                  <tr key={`sk-${r}`} className="border-b border-line">
                    {Array.from({ length: colCount }, (_, c) => (
                      <td key={c} className="px-2.5 py-3"><Skeleton className="h-4 w-full max-w-40" /></td>
                    ))}
                  </tr>
                ))
              : rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    onKeyDown={onRowClick ? (e) => { if (e.key === "Enter") onRowClick(row.original); } : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    className={cn("border-b border-line", onRowClick && "cursor-pointer hover:bg-canvas focus-visible:bg-canvas")}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const meta = (cell.column.columnDef.meta ?? {}) as ColMeta;
                      return (
                        <td key={cell.id} className={cn("px-2.5 py-2.5 align-middle", meta.align === "right" && "tabular text-right", meta.align === "center" && "text-center", meta.className)}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
      {!loading && rows.length === 0 ? (empty ?? <EmptyState title="Nothing here yet" />) : null}
      {!loading && total > size ? (
        <div className="flex items-center justify-between gap-2 text-[12.5px] text-fg-muted">
          <span className="tabular">{from + 1}–{to} of {total}</span>
          <div className="flex gap-1.5">
            <Button size="icon-sm" aria-label="Previous page" disabled={!canPrev} onClick={() => go(-1)}><ChevronLeft /></Button>
            <Button size="icon-sm" aria-label="Next page" disabled={!canNext} onClick={() => go(1)}><ChevronRight /></Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
