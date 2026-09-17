import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    reporters: ["default", ["junit", { classnameTemplate: "examples/session-api-typescript/{filename}" }]],
    outputFile: { junit: "junit.xml" },
  },
});
