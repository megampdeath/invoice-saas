"use client";

export function InvoicePreview({ url, filename }: { url: string | null; filename: string }) {
  if (!url) {
    return (
      <div className="flex h-full items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-400">
        No preview available
      </div>
    );
  }
  const isImage = /\.(png|jpe?g|tiff?)$/i.test(filename) || url.startsWith("data:image");
  if (isImage) {
    return <img src={url} alt={filename} className="h-full w-full rounded border border-gray-200 object-contain" />;
  }
  return (
    <iframe title={filename} src={url} className="h-full w-full rounded border border-gray-200 bg-white" />
  );
}