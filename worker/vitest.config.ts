import { readFile } from "node:fs/promises";
import path from "node:path";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";
import { parse } from "yaml";

export default defineConfig({
  plugins: [
    cloudflareTest(async () => {
      const migrations = await readD1Migrations(path.join(import.meta.dirname, "migrations"));
      const contractPath = path.join(import.meta.dirname, "..", "plans", "openapi-worker.yaml");
      const contract = parse(await readFile(contractPath, "utf8"));
      const packageJson = JSON.parse(await readFile(path.join(import.meta.dirname, "package.json"), "utf8"));
      const lockfile = JSON.parse(await readFile(path.join(import.meta.dirname, "package-lock.json"), "utf8"));
      const dependencyVersions = {
        "drizzle-orm": {
          declared: packageJson.dependencies["drizzle-orm"],
          resolved: lockfile.packages["node_modules/drizzle-orm"].version,
        },
      };
      return {
        wrangler: { configPath: "./wrangler.toml" },
        miniflare: {
          bindings: {
            TEST_MIGRATIONS: migrations,
            SPECTRACE_API_KEY: "test-key",
            CONTRACT: contract,
            DEPENDENCY_VERSIONS: dependencyVersions,
          },
        },
      };
    }),
  ],
  test: {
    setupFiles: ["./test/apply-migrations.ts"],
    reporters: ["default", ["junit", { classnameTemplate: "worker/{filename}" }]],
    outputFile: { junit: "junit.xml" },
  },
});
