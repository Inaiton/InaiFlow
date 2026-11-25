import type { components, paths } from "@/lib/api/schema";

/** Generated contract schemas. Use `Schemas["LedgerOut"]` — never hand-write payload shapes. */
export type Schemas = components["schemas"];
export type ErrorCode = Schemas["ErrorCode"];
export type ApiPaths = paths;

type OrgHeaderName = "X-Organization-ID";

type StripParams<P> = P extends { header: infer H }
  ? [Exclude<keyof H, OrgHeaderName>] extends [never]
    ? Omit<P, "header"> & { header?: never }
    : Partial<Omit<H, OrgHeaderName>> extends Omit<H, OrgHeaderName>
      ? Omit<P, "header"> & { header?: Omit<H, OrgHeaderName> } // only optional headers left (e.g. Idempotency-Key)
      : Omit<P, "header"> & { header: Omit<H, OrgHeaderName> }
  : P;

type StripOp<O> = O extends { parameters: infer P } ? Omit<O, "parameters"> & { parameters: StripParams<P> } : O;

type StripPathItem<I> = { [M in keyof I]: M extends "parameters" ? I[M] : StripOp<I[M]> };

/**
 * Same as `paths` but with the required `X-Organization-ID` header removed — the org-bound client
 * (see `createOrgClient`) injects it, so feature code never passes it by hand.
 */
export type OrgPaths = { [K in keyof paths]: StripPathItem<paths[K]> };
