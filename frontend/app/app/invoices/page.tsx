"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type InvoiceList, type InvoiceListItem } from "@/lib/api";
import { UploadDropzone } from "@/components/upload-dropzone";
import { StatusBadge } from "@/components/status-badge";
import { formatDate, formatMoney } from "@/lib/formatting";
import Link from "next/link";

const STATUSES = ["", "uploaded", "processing", "needs_review", "approved", "failed", "archived"];

export default function InvoicesPage() {
  const [orgId, setOrgId] = useState<string | null>(null);
  const [data, setData] = useState<InvoiceList | null>(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") setOrgId(localStorage.getItem("activeOrgId"));
  }, []);

  const load = useCallback(async () => {
    if (!orgId) return;
    setErr(null);
    try {
      const params = new URLSearchParams({ organization_id: orgId, page: "1", page_size: "50" });
      if (status) params.set("status", status);
      if (search) params.set("search", search);
      setData(await api.get<InvoiceList>(`/api/invoices?${params}`));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load invoices");
    }
  }, [orgId, status, search]);

  useEffect(() => { load(); }, [load]);

  if (!orgId) return <p className="text-sm text-gray-500">Select or create an organization first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Invoices</h1>
      </div>

      <UploadDropzone orgId={orgId} onUploaded={load} />

      <div className="flex flex-wrap gap-2">
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm">
          {STATUSES.map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}
        </select>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search invoice number…"
          className="rounded border border-gray-300 px-2 py-1 text-sm" />
        <button onClick={load} className="rounded border px-3 py-1 text-sm hover:bg-gray-100">Refresh</button>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">File / Invoice</th>
              <th className="px-3 py-2">Invoice date</th>
              <th className="px-3 py-2">Total</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-gray-400">
                No invoices yet. Upload a PDF or image to get started.
              </td></tr>
            )}
            {data?.items.map((it: InvoiceListItem) => (
              <tr key={it.id} className="border-t hover:bg-gray-50">
                <td className="px-3 py-2">
                  <Link href={`/app/invoices/${it.id}`} className="font-medium text-blue-600 hover:underline">
                    {it.invoice_number || it.original_filename}
                  </Link>
                  <div className="text-xs text-gray-500">{it.original_filename}</div>
                </td>
                <td className="px-3 py-2">{formatDate(it.invoice_date)}</td>
                <td className="px-3 py-2">{formatMoney(it.total_amount, it.currency)}</td>
                <td className="px-3 py-2"><StatusBadge status={it.status} /></td>
                <td className="px-3 py-2 text-gray-500">{formatDate(it.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <p className="text-xs text-gray-500">{data.total} total</p>}
    </div>
  );
}