import { describe, expect, it } from "vitest";
import { parseMarkdown } from "../src/client/pages/requirement";

const SOURCE = [
  "# Single Sign-On (SSO) Support",
  "",
  "Tenants sign in through their own provider.",
  "",
  "## Requirements",
  "1. ++Protocol Support++: accept `SAML 2.0` and OIDC.",
  "2. Session lifetime follows the provider.",
].join("\n");

describe("parseMarkdown", () => {
  it("keeps headings, paragraphs and list structure apart", () => {
    expect(parseMarkdown(SOURCE).map((block) => block.kind)).toEqual(["heading", "paragraph", "heading", "list"]);
  });

  it("reads the heading level from the hash count", () => {
    const [top, , section] = parseMarkdown(SOURCE);
    expect(top).toMatchObject({ kind: "heading", level: 1 });
    expect(section).toMatchObject({ kind: "heading", level: 2 });
  });

  it("gathers consecutive numbered lines into one ordered list", () => {
    const list = parseMarkdown(SOURCE).at(-1);
    expect(list).toMatchObject({ kind: "list", ordered: true });
    expect(list?.kind === "list" && list.items).toHaveLength(2);
  });

  it("strips the markers from emphasis and code spans", () => {
    const list = parseMarkdown(SOURCE).at(-1);
    const spans = list?.kind === "list" ? list.items[0].spans : [];
    expect(spans.filter((span) => span.kind === "emphasis")).toEqual([
      { key: expect.any(String), kind: "emphasis", text: "Protocol Support" },
    ]);
    expect(spans.filter((span) => span.kind === "code")).toEqual([
      { key: expect.any(String), kind: "code", text: "SAML 2.0" },
    ]);
  });

  it("joins wrapped paragraph lines and splits on a blank line", () => {
    const blocks = parseMarkdown("one\ntwo\n\nthree");
    expect(blocks).toHaveLength(2);
    expect(blocks[0].kind === "paragraph" && blocks[0].spans.map((span) => span.text).join("")).toBe("one two");
  });

  it("gives every block a distinct key", () => {
    const keys = parseMarkdown(SOURCE).map((block) => block.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
