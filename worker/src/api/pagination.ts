import type { Context } from "hono";

export const DEFAULT_PER_PAGE = 25;
export const MAX_PER_PAGE = 100;

export interface PageRequest {
  page: number;
  perPage: number;
}

export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export class InvalidPageParam extends Error {
  constructor(readonly param: string) {
    super(`Invalid ${param} parameter`);
  }
}

export function positiveInt(raw: string | undefined, fallback: number, max: number, param: string): number {
  if (raw === undefined || raw === "") return fallback;
  if (!/^\d+$/.test(raw)) throw new InvalidPageParam(param);
  return Math.max(1, Math.min(Number.parseInt(raw, 10), max));
}

export function pageRequest(c: Context, defaultPerPage = DEFAULT_PER_PAGE): PageRequest {
  return {
    page: positiveInt(c.req.query("page"), 1, 10000, "page"),
    perPage: positiveInt(c.req.query("per_page"), defaultPerPage, MAX_PER_PAGE, "per_page"),
  };
}

export function pageMeta(request: PageRequest, total: number): PageMeta {
  const totalPages = Math.max(1, Math.ceil(total / request.perPage));
  const page = Math.min(request.page, totalPages);
  return {
    page,
    per_page: request.perPage,
    total,
    total_pages: totalPages,
    has_next: page < totalPages,
    has_prev: page > 1,
  };
}

export function clampedOffset(request: PageRequest, total: number): number {
  return (pageMeta(request, total).page - 1) * request.perPage;
}
