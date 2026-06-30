"use client";

import { getAccessToken } from "./auth";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${BACKEND}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || JSON.stringify(j);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(p: string, body: unknown) =>
    request<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  upload: <T>(p: string, formData: FormData) =>
    request<T>(p, { method: "POST", body: formData }),
};

export interface InvoiceListItem {
  id: string;
  status: string;
  original_filename: string;
  invoice_number: string | null;
  invoice_date: string | null;
  total_amount: string | null;
  currency: string | null;
  created_at: string;
}

export interface InvoiceList {
  items: InvoiceListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface InvoiceWarning {
  code: string;
  message: string;
  severity: string;
}

export interface InvoiceDetail {
  id: string;
  status: string;
  original_filename: string;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  currency: string | null;
  subtotal_amount: string | null;
  tax_amount: string | null;
  total_amount: string | null;
  iban: string | null;
  payment_terms: string | null;
  supplier: { name: string | null; vat_number: string | null };
  confidence: number;
  warnings: InvoiceWarning[];
  file_preview_url: string | null;
}

export interface OrgOut {
  id: string;
  name: string;
  slug: string;
  plan: string;
  subscription_status: string;
  billing_email: string | null;
}