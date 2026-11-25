import type { UseFormReturn } from "react-hook-form";
import type { OrgCreateOutput, OrgCreateValues } from "../schema";

export type OrgForm = UseFormReturn<OrgCreateValues, unknown, OrgCreateOutput>;
