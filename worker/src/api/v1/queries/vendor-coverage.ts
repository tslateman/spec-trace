import { and, asc, desc, eq, inArray, ne } from "drizzle-orm";
import type { Database } from "../../../db/client";
import { inAppValidationResults, inAppValidations, requirements } from "../../../db/schema";
import { isoformat, roundHalfEven } from "./time";

export type VendorRegression = { name: string; regressed_at: string; run_id: number };
export type VendorFlagCount = { flag: string; count: number };

export type VendorCoverage = {
  name: string;
  total: number;
  passing: number;
  failing: number;
  not_run: number;
  pass_rate: number;
  regressions: VendorRegression[];
  common_flags: VendorFlagCount[];
};

export type VendorCoverageReport = {
  vendors: VendorCoverage[];
  all_flags: string[];
  total_vendors: number;
  total_validations: number;
};

type VendorAccumulator = Omit<VendorCoverage, "pass_rate" | "common_flags"> & { flagCounts: Map<string, number> };

export async function vendorCoverage(db: Database, project: string): Promise<VendorCoverageReport> {
  const validations = await db
    .select({
      id: inAppValidations.id,
      name: inAppValidations.name,
      vendor: inAppValidations.vendor,
      featureFlags: inAppValidations.featureFlags,
    })
    .from(inAppValidations)
    .innerJoin(requirements, eq(requirements.id, inAppValidations.requirementId))
    .where(and(eq(requirements.project, project), ne(inAppValidations.vendor, "")))
    .orderBy(asc(inAppValidations.requirementId), asc(inAppValidations.name));

  const validationIds = validations.map((validation) => validation.id);
  const results = validationIds.length
    ? await db
        .select({
          validationId: inAppValidationResults.validationId,
          status: inAppValidationResults.status,
          checkedAt: inAppValidationResults.checkedAt,
          validationRunId: inAppValidationResults.validationRunId,
        })
        .from(inAppValidationResults)
        .where(inArray(inAppValidationResults.validationId, validationIds))
        .orderBy(desc(inAppValidationResults.checkedAt))
    : [];

  const resultsByValidation = new Map<number, typeof results>();
  for (const result of results) {
    resultsByValidation.set(result.validationId, [...(resultsByValidation.get(result.validationId) ?? []), result]);
  }

  const vendors = new Map<string, VendorAccumulator>();
  const allFlags = new Set<string>();

  for (const validation of validations) {
    let vendor = vendors.get(validation.vendor);
    if (!vendor) {
      vendor = {
        name: validation.vendor,
        total: 0,
        passing: 0,
        failing: 0,
        not_run: 0,
        regressions: [],
        flagCounts: new Map(),
      };
      vendors.set(validation.vendor, vendor);
    }
    vendor.total += 1;

    const history = resultsByValidation.get(validation.id) ?? [];
    const status = history[0]?.status ?? "not_run";
    if (status === "success") vendor.passing += 1;
    else if (status === "failure") vendor.failing += 1;
    else if (status === "not_run") vendor.not_run += 1;

    if (history.length >= 2 && history[1].status === "success" && history[0].status === "failure") {
      vendor.regressions.push({
        name: validation.name,
        regressed_at: isoformat(history[0].checkedAt),
        run_id: history[0].validationRunId,
      });
    }

    const flags = validation.featureFlags as Record<string, unknown> | null;
    if (flags && Object.keys(flags).length > 0) {
      for (const flag of Object.keys(flags)) {
        allFlags.add(flag);
        vendor.flagCounts.set(flag, (vendor.flagCounts.get(flag) ?? 0) + 1);
      }
    }
  }

  const sortedVendors = [...vendors.values()]
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
    .map(({ flagCounts, ...vendor }) => ({
      ...vendor,
      pass_rate: roundHalfEven((vendor.passing / vendor.total) * 100, 1),
      common_flags: [...flagCounts.entries()]
        .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
        .map(([flag, count]) => ({ flag, count })),
    }));

  return {
    vendors: sortedVendors,
    all_flags: [...allFlags].sort(),
    total_vendors: sortedVendors.length,
    total_validations: sortedVendors.reduce((sum, vendor) => sum + vendor.total, 0),
  };
}
