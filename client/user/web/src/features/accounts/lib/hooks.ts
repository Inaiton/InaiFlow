"use client";

import { useEffect, useState } from "react";

/** Value that settles `delay` ms after the last change (search boxes, compute-tax). */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}
