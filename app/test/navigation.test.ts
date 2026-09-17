import { describe, expect, it } from "vitest";
import appSource from "../src/client/App.tsx?raw";
import { navigation } from "../src/client/navigation";

const routed = new Set(
  [...appSource.matchAll(/path="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((path) => !path.includes(":") && path !== "*"),
);
const linked = navigation.flatMap((group) => group.items.map((item) => item.href));

describe("sidebar navigation", () => {
  it("opens with Overview and closes with Docs", () => {
    expect(navigation[0].title).toBe("Overview");
    expect(navigation.at(-1)?.title).toBe("Docs");
  });

  it("leads Overview with Merge Safety", () => {
    expect(navigation[0].items[0].label).toBe("Merge Safety");
  });

  it("gives no group the same name as one of its items", () => {
    for (const group of navigation) {
      expect(group.items.map((item) => item.label)).not.toContain(group.title);
    }
  });

  it("groups at least two pages under every heading", () => {
    for (const group of navigation) {
      expect(group.items.length, group.title).toBeGreaterThan(1);
    }
  });

  it("links every list route exactly once", () => {
    expect(new Set(linked)).toEqual(routed);
    expect(linked.length).toBe(routed.size);
  });
});

describe("catch-all route", () => {
  const catchAll = appSource.slice(appSource.indexOf('path="*"'));

  it("routes every unmatched path", () => {
    expect(appSource).toContain('path="*"');
  });

  it("renders the not-found page inside the shell", () => {
    expect(catchAll).toContain("<Page ");
    expect(catchAll).toContain("<NotFound />");
  });

  it("names the missing path and links back to a real page", () => {
    const notFound = appSource.slice(appSource.indexOf("function NotFound()"));
    expect(notFound).toContain("{pathname}");
    expect(notFound).toContain('<Link to="/"');
  });
});

describe("document title", () => {
  it("sets a title per route", () => {
    expect(appSource).toContain("document.title");
  });

  it("wraps every route element so each route sets its own title", () => {
    const routes = appSource.match(/<Route\b/g) ?? [];
    const pages = appSource.match(/<Page /g) ?? [];
    expect(pages.length).toBe(routes.length);
    expect(appSource).not.toContain('<Shell title="');
  });
});
