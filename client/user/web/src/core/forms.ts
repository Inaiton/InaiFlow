"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, type FieldValues, type Path, type Resolver, type UseFormProps, type UseFormReturn } from "react-hook-form";
import type { z } from "zod";
import { ApiError } from "@/core/api/errors";

/**
 * react-hook-form + zod in one call:
 *   const form = useZodForm(schema, { defaultValues: {...} });
 */
export function useZodForm<S extends z.ZodType<FieldValues, FieldValues>>(
  schema: S,
  props?: Omit<UseFormProps<z.input<S>, unknown, z.output<S>>, "resolver">,
): UseFormReturn<z.input<S>, unknown, z.output<S>> {
  return useForm<z.input<S>, unknown, z.output<S>>({ mode: "onTouched", ...props, resolver: zodResolver(schema) as unknown as Resolver<z.input<S>, unknown, z.output<S>> });
}

/** Push server-side field errors (ApiError.fieldErrors) into the form. Returns true if any were applied. */
export function applyServerErrors<T extends FieldValues, O>(form: UseFormReturn<T, unknown, O>, err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  const fields = err.fieldErrors;
  const keys = Object.keys(fields);
  for (const k of keys) form.setError(k as Path<T>, { type: "server", message: fields[k] });
  return keys.length > 0;
}
