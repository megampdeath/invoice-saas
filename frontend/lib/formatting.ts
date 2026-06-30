export function formatMoney(amount: string | number | null, currency: string | null): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (Number.isNaN(n)) return String(amount);
  try {
    return new Intl.NumberFormat("fr-FR", { style: "currency", currency: currency || "EUR" }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency || ""}`.trim();
  }
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR");
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("fr-FR");
}

export const STATUS_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  needs_review: "Needs review",
  approved: "Approved",
  failed: "Failed",
  archived: "Archived",
};