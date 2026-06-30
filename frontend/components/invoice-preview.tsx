"use client";

import { useEffect, useState } from "react";

/**
 * Render an invoice file (PDF or image) inline.
 *
 * The backend serves the file at `file_preview_url` with
 * Content-Disposition: inline, but that URL is cross-origin to the frontend
 * (api.vercel.app vs web.vercel.app), and browsers won't reliably render a
 * cross-origin PDF inside <iframe src="..."> — they download it instead.
 *
 * Fix: fetch the bytes with the HMAC token URL (no Bearer header needed), turn
 * them into a same-origin blob: URL, and point the iframe/<img> at that. Browsers
 * always render blob: URLs inline.
 */
export function InvoicePreview({ url, filename }: { url: string | null; filename: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setBlobUrl(null);
    setErr(null);
    if (!url) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load preview");
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (!url) {
    return (
      <div className="flex h-full items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-400">
        No preview available
      </div>
    );
  }
  if (err) {
    return (
      <div className="flex h-full items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-red-500">
        Preview failed: {err}
      </div>
    );
  }
  if (!blobUrl) {
    return (
      <div className="flex h-full items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-400">
        Loading preview…
      </div>
    );
  }

  const isImage = /\.(png|jpe?g|tiff?)$/i.test(filename) || blobUrl.startsWith("data:image");
  if (isImage) {
    return <img src={blobUrl} alt={filename} className="h-full w-full rounded border border-gray-200 object-contain" />;
  }
  // PDF: <object> is more reliable than <iframe> for rendering blob PDFs across browsers.
  return (
    <object
      data={blobUrl}
      type="application/pdf"
      className="h-full w-full rounded border border-gray-200 bg-white"
      aria-label={filename}
    >
      <iframe title={filename} src={blobUrl} className="h-full w-full rounded border border-gray-200 bg-white" />
    </object>
  );
}
