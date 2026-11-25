"use client";

import { useEffect, useRef } from "react";

const EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "visibilitychange"] as const;

/** Calls onIdle after `ms` without user activity while `enabled`. */
export function useIdleTimeout(enabled: boolean, ms: number, onIdle: () => void) {
  const cb = useRef(onIdle);
  useEffect(() => {
    cb.current = onIdle;
  }, [onIdle]);

  useEffect(() => {
    if (!enabled) return;
    let last = Date.now();
    let timer: ReturnType<typeof setTimeout>;
    const arm = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (Date.now() - last >= ms) cb.current();
        else arm();
      }, ms - (Date.now() - last));
    };
    const bump = () => {
      // Hidden-tab time still counts toward idleness; only real interaction resets.
      if (document.visibilityState === "visible") last = Date.now();
      if (Date.now() - last >= ms) cb.current();
    };
    EVENTS.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    arm();
    return () => {
      clearTimeout(timer);
      EVENTS.forEach((e) => window.removeEventListener(e, bump));
    };
  }, [enabled, ms]);
}
