/// <reference types="vite/client" />
import type { D1Migration } from "@cloudflare/vitest-plugin";

declare global {
  namespace Cloudflare {
    interface Env {
      TEST_MIGRATIONS: D1Migration[];
      CONTRACT: OpenApiDocument;
      DEPENDENCY_VERSIONS: Record<string, { declared: string; resolved: string }>;
    }
  }
}

export interface OpenApiDocument {
  paths: Record<string, Record<string, OpenApiOperation>>;
  components: { schemas: Record<string, unknown> };
}

export interface OpenApiOperation {
  operationId?: string;
  responses: Record<string, { content?: Record<string, { schema?: unknown }> }>;
}
