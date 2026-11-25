import { describe, expect, it } from "vitest";
import { nextNavIndex } from "./enter-nav";

describe("nextNavIndex", () => {
  it("advances and stops at the ends", () => {
    expect(nextNavIndex(3, 0)).toBe(1);
    expect(nextNavIndex(3, 2)).toBe(-1);
    expect(nextNavIndex(3, 1, true)).toBe(0);
    expect(nextNavIndex(3, 0, true)).toBe(-1);
    expect(nextNavIndex(0, 0)).toBe(-1);
  });
});
