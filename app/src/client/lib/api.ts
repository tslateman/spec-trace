import { hc } from "hono/client";
import type { AppType } from "../../server/index";
import type { CoverageTrend, ResolutionReason, SpecDecisionResult } from "../../shared/spectrace";

export const api = hc<AppType>("/");

export function reauthenticate(): never {
  const returnTo = window.location.pathname + window.location.search;
  window.location.assign(`/auth/login?return_to=${encodeURIComponent(returnTo)}`);
  throw new Error("Session expired");
}

export function assertAuthorized(res: { status: number }) {
  if (res.status === 401) reauthenticate();
}

export class ApiError extends Error {
  readonly status: number;
  readonly label: string;

  constructor(message: string, status: number, label: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.label = label;
  }
}

function loadFailure(label: string, status: number): ApiError {
  if (status === 404) return new ApiError(`We could not find the ${label}.`, status, label);
  if (status === 403) return new ApiError(`You do not have access to the ${label}.`, status, label);
  if (status === 409) return new ApiError(`The ${label} is not ready yet.`, status, label);
  if (status >= 500) return new ApiError(`The server failed while loading the ${label}.`, status, label);
  return new ApiError(`We could not load the ${label}.`, status, label);
}

function actionFailure(label: string, status: number): ApiError {
  if (status === 403) return new ApiError(`You do not have permission to ${label}.`, status, label);
  if (status === 404) return new ApiError(`We could not ${label} because it no longer exists.`, status, label);
  if (status >= 500) return new ApiError(`The server failed and could not ${label}.`, status, label);
  return new ApiError(`We could not ${label}.`, status, label);
}

export async function getJson<T>(path: string, label: string): Promise<T> {
  const res = await fetch(path);
  if (res.status === 401) reauthenticate();
  if (!res.ok) throw loadFailure(label, res.status);
  return (await res.json()) as T;
}

export async function getJsonOrNull<T>(path: string, label: string): Promise<T | null> {
  const res = await fetch(path);
  if (res.status === 401) reauthenticate();
  if (res.status === 404 || res.status === 409) return null;
  if (!res.ok) throw loadFailure(label, res.status);
  return (await res.json()) as T;
}

export async function postJson<T>(path: string, body: unknown, label: string): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) reauthenticate();
  if (!res.ok) throw actionFailure(label, res.status);
  return (await res.json()) as T;
}

export function getCoverageTrend() {
  return getJson<CoverageTrend>("/api/spectrace/coverage/trend", "coverage trend");
}

export function resolveConflict(id: number, notes: string, reason?: ResolutionReason) {
  return postJson<{ data: { conflict_id: number; resolved_at: string } }>(
    `/api/spectrace/conflicts/${id}/resolve`,
    reason ? { resolution_notes: notes, resolution_reason: reason } : { resolution_notes: notes },
    "resolve conflict",
  );
}

interface ErrorEnvelope {
  error?: { message?: string };
}

export async function postForResult<T>(path: string, body: unknown, label: string): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) reauthenticate();
  const payload = (await res.json()) as T & ErrorEnvelope;
  if (!res.ok) {
    const detail = payload.error?.message;
    throw detail ? new ApiError(detail, res.status, label) : actionFailure(label, res.status);
  }
  return payload;
}

async function asReviewer<T>(decide: () => Promise<T>): Promise<T> {
  await postForResult("/api/spectrace/reviewer", {}, "register reviewer");
  return decide();
}

function specDecision(taskId: string, action: string, body: unknown, label: string) {
  return asReviewer(() =>
    postForResult<SpecDecisionResult>(`/api/spectrace/tasks/${encodeURIComponent(taskId)}/${action}`, body, label),
  );
}

export function approveSpec(taskId: string, feedback: string) {
  return specDecision(taskId, "approve-spec", { feedback }, "approve spec");
}

export function rejectSpec(taskId: string, reason: string) {
  return specDecision(taskId, "reject-spec", { reason }, "reject spec");
}
