"use client";

import { useState } from "react";
import { api } from "@/lib/api";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,.tif,.tiff";

export function UploadDropzone({ orgId, onUploaded }: { orgId: string; onUploaded?: () => void }) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("organization_id", orgId);
      await api.upload("/api/invoices", fd);
      onUploaded?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) upload(f);
      }}
      className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
        drag ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-white"
      }`}
    >
      <p className="text-sm text-gray-600">
        Drop an invoice here (PDF, JPG, PNG, TIFF — max 25 MB), or
      </p>
      <label className="mt-2 inline-block cursor-pointer rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700">
        {busy ? "Uploading…" : "Choose file"}
        <input
          type="file"
          accept={ACCEPT}
          className="hidden"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
          }}
        />
      </label>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}