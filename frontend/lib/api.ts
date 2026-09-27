/**
 * Client for the DriftKing API. Requests go to same-origin `/api/*`, which
 * Next.js proxies to the backend (see next.config.ts), so no CORS setup is
 * needed.
 */

import type { ChangeSet } from "./changeModel";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the DriftKing backend.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body !== null && typeof body === "object" && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}).`;
    throw new ApiError(detail);
  }
  return body as T;
}

export interface FixtureList {
  fixtures: { name: string }[];
}

export function listFixtures(): Promise<FixtureList> {
  return request<FixtureList>("/api/fixtures");
}

export function fixtureChanges(name: string): Promise<ChangeSet> {
  return request<ChangeSet>(`/api/fixtures/${encodeURIComponent(name)}`);
}

export function interpretPlan(planJson: string): Promise<ChangeSet> {
  return request<ChangeSet>("/api/plans", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: planJson,
  });
}
