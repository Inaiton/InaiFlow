"use client";

import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { Table, TBody, TD, TH, THead, TR } from "./table";
import { cn } from "@/lib/utils";

export function DataTable<T>({
  data,
  columns,
  onRowClick,
  getRowId,
}: {
  data: T[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[];
  onRowClick?: (row: T) => void;
  getRowId?: (row: T) => string;
}) {
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel(), getRowId });
  return (
    <Table>
      <THead>
        {table.getHeaderGroups().map((hg) => (
          <TR key={hg.id}>
            {hg.headers.map((h) => (
              <TH key={h.id}>{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</TH>
            ))}
          </TR>
        ))}
      </THead>
      <TBody>
        {table.getRowModel().rows.map((row) => (
          <TR
            key={row.id}
            className={cn(onRowClick && "cursor-pointer hover:bg-canvas")}
            onClick={onRowClick ? () => onRowClick(row.original) : undefined}
            tabIndex={onRowClick ? 0 : undefined}
            onKeyDown={onRowClick ? (e) => e.key === "Enter" && onRowClick(row.original) : undefined}
          >
            {row.getVisibleCells().map((cell) => (
              <TD key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TD>
            ))}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
