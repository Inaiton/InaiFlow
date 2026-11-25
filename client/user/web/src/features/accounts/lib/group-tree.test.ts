import { describe, expect, it } from "vitest";
import { flattenGroups, ledgerClass, lineageCodes } from "./group-tree";

const g = (id: string, name: string, parent: string | null, code: string | null = null) => ({ id, name, parent_group_id: parent, system_code: code });
const groups = [
  g("ca", "Current Assets", null, "CURRENT_ASSETS"),
  g("cl", "Current Liabilities", null, "CURRENT_LIABILITIES"),
  g("sd", "Sundry Debtors", "ca", "SUNDRY_DEBTORS"),
  g("bank", "Bank Accounts", "ca", "BANK_ACCOUNTS"),
  g("north", "Debtors North", "sd"),
  g("dt", "Duties & Taxes", "cl", "DUTIES_TAXES"),
  g("orphan", "Orphan", "missing"),
];

describe("group tree", () => {
  it("flattens depth-first, sorted", () => {
    const flat = flattenGroups(groups).map((n) => `${"-".repeat(n.depth)}${n.group.name}`);
    expect(flat).toEqual(["Current Assets", "-Bank Accounts", "-Sundry Debtors", "--Debtors North", "Current Liabilities", "-Duties & Taxes", "Orphan"]);
    expect(flattenGroups(groups).find((n) => n.group.id === "sd")?.hasChildren).toBe(true);
  });
  it("classifies ledgers by lineage", () => {
    expect([...lineageCodes("north", groups)]).toEqual(["SUNDRY_DEBTORS", "CURRENT_ASSETS"]);
    expect(ledgerClass(lineageCodes("north", groups))).toBe("party");
    expect(ledgerClass(lineageCodes("bank", groups))).toBe("bank");
    expect(ledgerClass(lineageCodes("dt", groups))).toBe("tax");
    expect(ledgerClass(lineageCodes("ca", groups))).toBe("other");
    expect(ledgerClass(lineageCodes(null, groups))).toBe("other");
  });
});
