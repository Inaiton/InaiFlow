/**
 * Shortcut combos are normalised strings: modifiers in the fixed order ctrl, alt, shift, meta,
 * then the key — e.g. "alt+g", "ctrl+f8", "f4", "escape", "?".
 */
export type Combo = string;

const MOD_ORDER = ["ctrl", "alt", "shift", "meta"] as const;
type Mod = (typeof MOD_ORDER)[number];

const ALIASES: Record<string, string> = {
  esc: "escape",
  return: "enter",
  del: "delete",
  space: " ",
  spacebar: " ",
  control: "ctrl",
  cmd: "meta",
  command: "meta",
  option: "alt",
  up: "arrowup",
  down: "arrowdown",
  left: "arrowleft",
  right: "arrowright",
  plus: "+",
};

/** Parse "Ctrl+Shift+S" / "alt + g" / "Esc" into a normalised combo. */
export function parseCombo(input: string): Combo {
  const raw = input.trim().toLowerCase();
  if (raw === "+") return "+";
  const parts = raw.split("+").map((p) => p.trim()).filter(Boolean);
  if (raw.endsWith("++")) parts.push("+");
  const mods = new Set<Mod>();
  let key = "";
  for (const p of parts) {
    const a = ALIASES[p] ?? p;
    if ((MOD_ORDER as readonly string[]).includes(a)) mods.add(a as Mod);
    else key = a;
  }
  if (!key) throw new Error(`Shortcut "${input}" has no key`);
  return [...MOD_ORDER.filter((m) => mods.has(m)), key].join("+");
}

export interface KeyLike {
  key: string;
  code?: string;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  metaKey: boolean;
}

/**
 * Normalise a KeyboardEvent. Letters/digits use `code` so Alt+G works on macOS (where `key` is "©").
 * Printable symbols ("?", "/") use `key` and drop the implicit shift.
 */
export function eventToCombo(e: KeyLike): Combo {
  let key: string;
  const code = e.code ?? "";
  if (/^Key[A-Z]$/.test(code)) key = code.slice(3).toLowerCase();
  else if (/^Digit\d$/.test(code)) key = code.slice(5);
  else key = e.key.toLowerCase();
  key = ALIASES[key] ?? key;
  const isSymbol = key.length === 1 && !/[a-z0-9]/.test(key);
  const mods: string[] = [];
  if (e.ctrlKey) mods.push("ctrl");
  if (e.altKey) mods.push("alt");
  if (e.shiftKey && !isSymbol) mods.push("shift");
  if (e.metaKey) mods.push("meta");
  return [...mods, key].join("+");
}

/** Human label: "alt+g" → ["Alt", "G"] for <Kbd> rendering. */
export function comboLabel(combo: Combo): string[] {
  return parseCombo(combo)
    .split("+")
    .map((p) => {
      if (p === "ctrl") return "Ctrl";
      if (p === "alt") return "Alt";
      if (p === "shift") return "Shift";
      if (p === "meta") return "⌘";
      if (p === "escape") return "Esc";
      if (p === " ") return "Space";
      if (/^f\d{1,2}$/.test(p)) return p.toUpperCase();
      if (p.startsWith("arrow")) return { arrowup: "↑", arrowdown: "↓", arrowleft: "←", arrowright: "→" }[p] ?? p;
      return p.length === 1 ? p.toUpperCase() : p[0]!.toUpperCase() + p.slice(1);
    });
}

/** Plain keys (no modifier, not F-keys/Escape) should not fire while the user types in a field. */
export function isTypingSafe(combo: Combo): boolean {
  const parts = combo.split("+");
  if (parts.length > 1 && parts.some((p) => p === "ctrl" || p === "alt" || p === "meta")) return true;
  const key = parts[parts.length - 1] ?? "";
  return /^f\d{1,2}$/.test(key) || key === "escape";
}
