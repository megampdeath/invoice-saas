"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/formatting";
import { useOrg } from "@/lib/org-context";

interface ExportJob {
  id: string;
  status: string;
  format: string;
  row_count: number | null;
  download_url: string | null;
}

export default function ExportsPage() {
  const { orgId, loading } = useOrg();
  const [fmt, setFmt] = useState<"csv" | "xlsx">("xlsx");
  const [status, setStatus] = useState("approved");
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      setJobs(await api.get<ExportJob[]>(`/api/exports?organization_id=${orgId}`));
    } catch {
      setJobs([]);
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  async function createExport() {
    if (!orgId) return;
    setMsg(null); setErr(null);
    try {
      const res = await api.post<{ export_job_id: string }>("/api/exports", {
        organization_id: orgId, format: fmt, status,
      });
      setMsg(`Export queued (${res.export_job_id})`);
      setTimeout(load, 2000);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Export failed");
    }
  }

  if (loading || !orgId) return <p className="text-sm text-gray-500">Loading your workspace…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Exports</h1>

      <div className="flex flex-wrap items-end gap-2 rounded-lg border bg-white p-4">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-600">Format</span>
          <select value={fmt} onChange={(e) => setFmt(e.target.value as "csv" | "xlsx")}
            className="rounded border border-gray-300 px-2 py-1 text-sm">
            <option value="xlsx">XLSX</option>
            <option value="csv">CSV</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-600">Status filter</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm">
            <option value="approved">Approved</option>
            <option value="needs_review">Needs review</option>
            <option value="">All</option>
          </select>
        </label>
        <button onClick={createExport} className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700">
          Create export
        </button>
      </div>

      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Format</th>
              <th className="px-3 py-2">Rows</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Download</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-8 text-center text-gray-400">No exports yet.</td></tr>
            )}
            {jobs.map((j) => (
              <tr key={j.id} className="border-t">
                <td className="px-3 py-2 uppercase">{j.format}</td>
                <td className="px-3 py-2">{j.row_count ?? "—"}</td>
                <td className="px-3 py-2">{j.status}</td>
                <td className="px-3 py-2">
                  {j.download_url ? (
                    <a href={j.download_url} className="text-blue-600 hover:underline">Download</a>
                  ) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400">Created: {jobs.length ? formatDateTime(jobs[0].id) : "—"}</p>
    </div>
  );
}