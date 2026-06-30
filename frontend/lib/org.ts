"use client";

/** Get the active organization id from localStorage (client only). */
export function useActiveOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("activeOrgId");
}

/** Read the active org id synchronously (no hook). Returns null on SSR. */
export function getActiveOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("activeOrgId");
}
