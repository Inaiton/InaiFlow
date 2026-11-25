/**
 * Tally-style Enter-to-advance. Fields that take part carry `data-nav`; Enter moves focus to the next one in DOM order.
 * Pickers that consume Enter themselves call `e.preventDefault()` first, which skips the advance.
 */
export const NAV_ATTR = "data-nav";

/** Index of the next navigable field (−1 when at the end). Pure for testing. */
export function nextNavIndex(count: number, current: number, backwards = false): number {
  if (count === 0) return -1;
  const next = backwards ? current - 1 : current + 1;
  return next < 0 || next >= count ? -1 : next;
}

function navFields(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(`[${NAV_ATTR}]`)).filter(
    (el) => !el.hasAttribute("disabled") && el.getAttribute("aria-disabled") !== "true" && el.offsetParent !== null,
  );
}

/** onKeyDown handler for a voucher form container. Returns true when focus moved. */
export function handleEnterAdvance(e: { key: string; shiftKey: boolean; defaultPrevented: boolean; target: EventTarget | null; preventDefault(): void }, root: HTMLElement | null, onEnd?: () => void): boolean {
  if (e.key !== "Enter" || e.defaultPrevented || !root) return false;
  const target = e.target as HTMLElement | null;
  if (!target || target.tagName === "TEXTAREA" || target.tagName === "BUTTON" || !target.hasAttribute(NAV_ATTR)) return false;
  const fields = navFields(root);
  const idx = nextNavIndex(fields.length, fields.indexOf(target), e.shiftKey);
  e.preventDefault();
  if (idx < 0) {
    onEnd?.();
    return false;
  }
  fields[idx]?.focus();
  const el = fields[idx];
  if (el instanceof HTMLInputElement) el.select();
  return true;
}

/** Focus the first navigable field inside `root`. */
export function focusFirstNav(root: HTMLElement | null): void {
  if (!root) return;
  navFields(root)[0]?.focus();
}
