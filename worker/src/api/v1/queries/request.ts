import type { Context } from "hono";

const integerPattern = /^\s*[+-]?\d+\s*$/;

export function parseInteger(raw: string | undefined, fallback: number): number | undefined {
  if (raw === undefined) return fallback;
  return integerPattern.test(raw) ? Number.parseInt(raw, 10) : undefined;
}

export class InvalidJsonBody extends Error {}

export async function jsonBody(c: Context): Promise<Record<string, unknown>> {
  const text = await c.req.text();
  if (text === "") return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new InvalidJsonBody((error as Error).message);
  }
}

export function isJsonRequest(c: Context): boolean {
  return (c.req.header("content-type") ?? "").includes("application/json");
}
