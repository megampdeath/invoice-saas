"use client";

/**
 * Render an invoice file (PDF or image) inline.
 *
 * The `url` is a same-origin relative URL (`/api/invoices/{id}/file?...`)
 * proxied to the backend via next.config.js rewrites. Same-origin inline PDFs
 * render natively in the browser's PDF viewer inside an <iframe>; cross-origin
 * PDFs are force-downloaded by Chrome, which is why we keep this same-origin.
 *
 * The URL carries a short-lived HMAC token (no Bearer header needed) so the
 * <iframe>/<img> can fetch it directly.
 */
export function InvoicePreview({ url, filename }: { url: string | null; filename: string }) {
  if (!url) {
    return (
      <div className="flex h-full items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-400">
        No preview available
      </div>
    );
  }

  const isImage = /\.(png|jpe?g|tiff?)$/i.test(filename);
  if (isImage) {
    return (
      <div className="h-full w-full overflow-auto rounded border border-gray-200 bg-white">
        <img src={url} alt={filename} className="h-full w-full object-contain" />
      </div>
    );
  }

  // PDF: <iframe> with the browser's native PDF viewer. Same-origin so it
  // renders inline (no download). A "Open in new tab" link is provided as a
  // fallback for any browser that still won't render inline.
  return (
    <div className="flex h-full w-full flex-col rounded border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b bg-gray-50 px-3 py-1 text-xs text-gray-500">
        <span className="truncate">{filename}</span>
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
          Open in new tab
        </a>
      </div>
      <iframe title={filename} src={url} className="h-full w-full flex-1 bg-white" />
    </div>
  );
}
