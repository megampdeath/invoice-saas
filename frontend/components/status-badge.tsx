const COLORS: Record<string, string> = {
  uploaded: "bg-gray-100 text-gray-700",
  processing: "bg-blue-100 text-blue-700",
  needs_review: "bg-amber-100 text-amber-800",
  approved: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  archived: "bg-gray-200 text-gray-600",
};

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 border-blue-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  error: "bg-red-50 text-red-700 border-red-200",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = COLORS[status] || "bg-gray-100 text-gray-700";
  const label = status.replace(/_/g, " ");
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {label}
    </span>
  );
}

export function WarningChip({ severity, code, message }: { severity: string; code: string; message: string }) {
  const cls = SEVERITY_COLORS[severity] || SEVERITY_COLORS.warning;
  return (
    <div className={`rounded border px-2 py-1 text-xs ${cls}`}>
      <span className="font-mono">{code}</span>: {message}
    </div>
  );
}