import { ApiError, UnauthorizedError } from "./errors";

const BASE_URL = import.meta.env.VITE_BACKEND_API_BASE_URL;

if (!BASE_URL) {
  throw new Error("VITE_BACKEND_API_BASE_URL is not set");
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (res.status === 401) {
    throw new UnauthorizedError();
  }
  if (!res.ok) {
    throw new ApiError(`Request failed: ${res.status}`, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const backendUrl = (path: string) => `${BASE_URL}${path}`;
