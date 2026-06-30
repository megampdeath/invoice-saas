"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type InvoiceDetail } from "@/lib/api";
import { StatusBadge, WarningChip } from "./status-badge";
import { formatMoney } from "@/lib/formatting";

export function InvoiceReviewForm({ id }: { id: string }) {
  const [inv, setInv] = useState<InvoiceDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    try {
      setInv(await api.get<InvoiceDetail>(`/api/invoices/${id}`));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (err) return <p className="text-red-600">{err}</p>;
  if (!inv) return <p>Loading…</p>;

  function set<K extends keyof InvoiceDetail>(key: K, value: InvoiceDetail[K]) {
    setInv({ ...inv!, [key]: value });
  }
  function setSupplier(key: "name" | "vat_number", value: string) {
    setInv({ ...inv!, supplier: { ...inv!.supplier, [key]: value } });
  }

  async function save() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await api.patch(`/api/invoices/${id}`, {
        invoice_number: inv!.invoice_number,
        invoice_date: inv!.invoice_date,
        due_date: inv!.due_date,
        currency: inv!.currency,
        subtotal_amount: inv!.subtotal_amount,
        tax_amount: inv!.tax_amount,
        total_amount: inv!.total_amount,
        iban: inv!.iban,
        payment_terms: inv!.payment_terms,
        supplier: inv!.supplier,
      });
      setMsg("Saved");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function approve() {
    setErr(null);
    try {
      await api.post(`/api/invoices/${id}/approve`);
      await load();
    } catch (e) {
      const m = e instanceof ApiError ? e.message : "Approve failed";
      setErr(m);
    }
  }

  async function reprocess() {
    setErr(null);
    try {
      await api.post(`/api/invoices/${id}/reprocess`);
      setMsg("Reprocessing started");
      setTimeout(load, 1500);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Reprocess failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusBadge status={inv.status} />
          <span className="text-sm text-gray-500">
            Confidence: <span className="font-medium">{Math.round(inv.confidence * 100)}%</span>
          </span>
        </div>
        <div className="flex gap-2">
          <button onClick={reprocess} className="rounded border px-3 py-1.5 text-sm hover:bg-gray-100">Reprocess</button>
          <button onClick={save} disabled={saving} className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
          {inv.status === "needs_review" && (
            <button onClick={approve} className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-500">
              Approve
            </button>
          )}
        </div>
      </div>

      {msg && <p className="text-sm text-green-700">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {inv.warnings.length > 0 && (
        <div className="space-y-1">
          {inv.warnings.map((w, i) => <WarningChip key={i} {...w} />)}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Invoice number" value={inv.invoice_number ?? ""} onChange={(v) => set("invoice_number", v)} />
        <Field label="Supplier name" value={inv.supplier.name ?? ""} onChange={(v) => setSupplier("name", v)} />
        <Field label="Invoice date" type="date" value={inv.invoice_date ?? ""} onChange={(v) => set("invoice_date", v)} />
        <Field label="Due date" type="date" value={inv.due_date ?? ""} onChange={(v) => set("due_date", v)} />
        <Field label="Currency" value={inv.currency ?? ""} onChange={(v) => set("currency", v)} />
        <Field label="Supplier VAT" value={inv.supplier.vat_number ?? ""} onChange={(v) => setSupplier("vat_number", v)} />
        <Field label="Subtotal" type="number" value={inv.subtotal_amount ?? ""} onChange={(v) => set("subtotal_amount", v)} />
        <Field label="Tax" type="number" value={inv.tax_amount ?? ""} onChange={(v) => set("tax_amount", v)} />
        <Field label="Total" type="number" value={inv.total_amount ?? ""} onChange={(v) => set("total_amount", v)} />
        <Field label="IBAN" value={inv.iban ?? ""} onChange={(v) => set("iban", v)} />
        <Field label="Payment terms" value={inv.payment_terms ?? ""} onChange={(v) => set("payment_terms", v)} />
        <div className="flex items-end text-sm text-gray-500">
          Display total: {formatMoney(inv.total_amount, inv.currency)}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }: {
  label: string; value: string; onChange: (v: string) => void; type?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
      />
    </label>
  );
}