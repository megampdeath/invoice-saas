"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useOrg } from "@/lib/org-context";

interface Supplier {
  id: string;
  name: string;
  vat_number: string | null;
  iban: string | null;
  default_expense_category: string | null;
}

export default function SuppliersPage() {
  const { orgId, loading } = useOrg();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!orgId) return;
    api.get<Supplier[]>(`/api/suppliers?organization_id=${orgId}`)
      .then(setSuppliers)
      .catch(() => setSuppliers([]));
  }, [orgId]);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Suppliers</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">VAT</th>
              <th className="px-3 py-2">IBAN</th>
              <th className="px-3 py-2">Category</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-8 text-center text-gray-400">
                Suppliers are created automatically from reviewed invoices.
              </td></tr>
            )}
            {suppliers.map((s) => (
              <tr key={s.id} className="border-t">
                <td className="px-3 py-2 font-medium">{s.name}</td>
                <td className="px-3 py-2">{s.vat_number || "—"}</td>
                <td className="px-3 py-2">{s.iban || "—"}</td>
                <td className="px-3 py-2">{s.default_expense_category || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}