import { describe, expect, it } from "vitest";
import { setAllLevels } from "./PermissionMatrix";

const modules = [
  { module: "accounts", label: "Accounts", keys: [{ key: "accounts.vouchers", label: "", description: "" }, { key: "accounts.reports", label: "", description: "" }] },
  { module: "documents", label: "Documents", keys: [{ key: "documents.explorer", label: "", description: "" }] },
];

describe("setAllLevels", () => {
  it("sets a module or everything", () => {
    expect(setAllLevels(modules, { "documents.explorer": "FULL" }, "READ", "accounts")).toEqual({ "accounts.vouchers": "READ", "accounts.reports": "READ", "documents.explorer": "FULL" });
    expect(Object.values(setAllLevels(modules, {}, "NONE"))).toEqual(["NONE", "NONE", "NONE"]);
  });
});
