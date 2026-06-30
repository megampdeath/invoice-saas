"use client";

import { useEffect, useState } from "react";
import { api, type OrgOut, ApiError } from "@/lib/api";
import { useOrg } from "@/lib/org-context";

interface Usage {
  plan: string;
  subscription_status: string;
  used: number;
  limit: number;
  usage_period_start: string;
  usage_period_end: string;
}

export default function SettingsPage() {
  const { orgId, loading } = useOrg();
  const [org, setOrg] = useState<OrgOut | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!orgId) return;
    api.get<OrgOut>(`/api/organizations/${orgId}`).then(setOrg).catch(() => {});
    api.get<Usage>(`/api/organizations/${orgId}/usage`).then(setUsage).catch(() => {});
  }, [orgId]);

  async function upgrade(plan: string) {
    if (!orgId) return;
    setMsg(null); setErr(null);
    try {
      const res = await api.post<{ url: string }>("/api/billing/checkout", { organization_id: orgId, plan });
      if (res.url) window.location.href = res.url;
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Checkout failed");
    }
  }

  if (loading || !orgId) return <p className="text-sm text-gray-500">Loading your workspace…</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-lg font-semibold">Settings</h1>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold">Organization</h2>
        {org ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-500">Name</dt><dd>{org.name}</dd>
            <dt className="text-gray-500">Slug</dt><dd className="font-mono">{org.slug}</dd>
            <dt className="text-gray-500">Plan</dt><dd>{org.plan}</dd>
            <dt className="text-gray-500">Status</dt><dd>{org.subscription_status}</dd>
            <dt className="text-gray-500">Billing email</dt><dd>{org.billing_email || "—"}</dd>
          </dl>
        ) : <p className="text-sm text-gray-400">Loading…</p>}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold">Plan &amp; usage</h2>
        {usage ? (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Usage this period</span>
              <span>{usage.used} / {usage.limit} invoices</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded bg-gray-100">
              <div className="h-2 bg-blue-500" style={{ width: `${Math.min(100, (usage.used / usage.limit) * 100)}%` }} />
            </div>
            <p className="text-xs text-gray-400">Period: {usage.usage_period_start} → {usage.usage_period_end}</p>
            <div className="flex gap-2 pt-2">
              {(["starter", "pro", "business"] as const).map((p) => (
                <button key={p} onClick={() => upgrade(p)}
                  className="rounded border px-3 py-1.5 text-xs capitalize hover:bg-gray-100">
                  Upgrade to {p}
                </button>
              ))}
            </div>
            {msg && <p className="text-sm text-green-700">{msg}</p>}
            {err && <p className="text-sm text-red-600">{err}</p>}
          </div>
        ) : <p className="text-sm text-gray-400">Loading…</p>}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold">Data retention</h2>
        <p className="text-sm text-gray-500">Files and extracted data are kept until you delete them. Auto-deletion policies arrive in a future release.</p>
      </section>
    </div>
  );
}