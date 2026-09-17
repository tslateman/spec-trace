import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const sources = import.meta.glob("../src/**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const SCREEN_MODULES = [
  "../src/screens/data/demos.ts",
  "../src/screens/layout.tsx",
  "../src/screens/pages/demo.tsx",
  "../src/screens/redirects.ts",
  "../src/screens/routes/demo.tsx",
];

function exportedNames(source: string): string[] {
  return [...source.matchAll(/^export\s+(?:const|let|function|class|type|interface)\s+(\w+)/gm)].map(
    (match) => match[1],
  );
}

function resolveImport(importer: string, specifier: string): string | undefined {
  const segments = importer.split("/").slice(0, -1);
  for (const part of specifier.split("/")) {
    if (part === "..") segments.pop();
    else if (part !== ".") segments.push(part);
  }
  const base = segments.join("/");
  return [`${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`].find(
    (candidate) => candidate in sources,
  );
}

function importedNames(): Map<string, Set<string>> {
  const byModule = new Map<string, Set<string>>();
  for (const [importer, source] of Object.entries(sources)) {
    for (const match of source.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+"(\.[^"]+)"/g)) {
      const target = resolveImport(importer, match[2]);
      if (!target) continue;
      const names = byModule.get(target) ?? new Set<string>();
      for (const raw of match[1].split(",")) {
        const name = raw
          .trim()
          .replace(/^type\s+/, "")
          .split(/\s+as\s+/)[0];
        if (name) names.add(name);
      }
      byModule.set(target, names);
    }
  }
  return byModule;
}

describe("screen module exports", () => {
  it("audits the five screen modules and reads their real source", () => {
    const found = Object.keys(sources)
      .filter((key) => key.startsWith("../src/screens/"))
      .sort();
    expect(found).toEqual(SCREEN_MODULES);
    expect(exportedNames(sources["../src/screens/routes/demo.tsx"])).toContain("publicDemo");
  });

  it("AC1: every export from a screen module is imported by name somewhere under src", () => {
    const imports = importedNames();
    const orphans = SCREEN_MODULES.flatMap((module) =>
      exportedNames(sources[module])
        .filter((name) => !imports.get(module)?.has(name))
        .map((name) => `${module.replace("../src/", "")}: ${name}`),
    );
    expect(orphans).toEqual([]);
  });

  it("AC2: layout.tsx exports only renderScreen", () => {
    expect(exportedNames(sources["../src/screens/layout.tsx"])).toEqual(["renderScreen"]);
  });

  it("AC3: data/demos.ts exports only demoCatalog", () => {
    expect(exportedNames(sources["../src/screens/data/demos.ts"])).toEqual(["demoCatalog"]);
  });

  it("AC4: only redirects.ts mentions an /admin/ path", () => {
    const offenders = SCREEN_MODULES.filter(
      (module) => module !== "../src/screens/redirects.ts" && sources[module].includes("/admin/"),
    ).map((module) => module.replace("../src/", ""));
    expect(offenders).toEqual([]);
  });
});

describe("demo page body", () => {
  it("AC5: GET /demo/ returns the same body as before the prune", async () => {
    const body = await (await SELF.fetch("http://spectrace/demo/")).text();
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body));
    const hex = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    expect(body.length).toBe(4459);
    expect(hex).toBe("1a10ec70c69ed2f2fc3f36d2e28c2aa14e85cd6a438c8bf94b3446bd5e54ee66");
  });
});
