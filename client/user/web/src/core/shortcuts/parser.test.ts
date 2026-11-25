import { describe, expect, it } from "vitest";
import { comboLabel, eventToCombo, isTypingSafe, parseCombo } from "./parser";

const ev = (o: Partial<Parameters<typeof eventToCombo>[0]>) => ({
  key: "", code: "", ctrlKey: false, altKey: false, shiftKey: false, metaKey: false, ...o,
});

describe("shortcut parser", () => {
  it("normalises combos", () => {
    expect(parseCombo("Alt+G")).toBe("alt+g");
    expect(parseCombo("shift + ctrl + s")).toBe("ctrl+shift+s");
    expect(parseCombo("Esc")).toBe("escape");
    expect(parseCombo("F8")).toBe("f8");
    expect(parseCombo("Ctrl+F9")).toBe("ctrl+f9");
    expect(parseCombo("?")).toBe("?");
    expect(() => parseCombo("ctrl+")).toThrow();
  });
  it("maps keyboard events", () => {
    expect(eventToCombo(ev({ key: "©", code: "KeyG", altKey: true }))).toBe("alt+g");
    expect(eventToCombo(ev({ key: "F5", code: "F5", altKey: true }))).toBe("alt+f5");
    expect(eventToCombo(ev({ key: "?", code: "Slash", shiftKey: true }))).toBe("?");
    expect(eventToCombo(ev({ key: "Escape", code: "Escape" }))).toBe("escape");
    expect(eventToCombo(ev({ key: "a", code: "KeyA", ctrlKey: true }))).toBe("ctrl+a");
  });
  it("labels and typing safety", () => {
    expect(comboLabel("alt+g")).toEqual(["Alt", "G"]);
    expect(comboLabel("ctrl+f8")).toEqual(["Ctrl", "F8"]);
    expect(isTypingSafe("alt+g")).toBe(true);
    expect(isTypingSafe("f8")).toBe(true);
    expect(isTypingSafe("?")).toBe(false);
    expect(isTypingSafe("shift+a")).toBe(false);
  });
});
