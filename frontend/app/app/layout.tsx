"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { supabase, signOut } from "@/lib/auth";
import { api, type OrgOut } from "@/lib/api";

const NAV = [
  { href: "/app/invoices", label: "Inbox" },
  { href: "/app/suppliers", label: "Suppliers" },
  { href: "/app/exports", label: "Exports" },
  { href: "/app/settings", label: "Settings" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [orgs, setOrgs] = useState<OrgOut[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace("/login");
        return;
      }
      try {
        const list = await api.get<OrgOut[]>("/api/organizations");
        setOrgs(list);
        const stored = typeof window !== "undefined" ? localStorage.getItem("activeOrgId") : null;
        const active = stored && list.some((o) => o.id === stored) ? stored : list[0]?.id ?? null;
        setOrgId(active);
        if (active) localStorage.setItem("activeOrgId", active);
      } catch {
        // user may have no org yet
      }
      setReady(true);
    })();
  }, [router]);

  if (!ready) return <div className="p-8 text-sm text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r bg-white">
        <div className="border-b px-4 py-3 font-semibold">Invoice SaaS</div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`block rounded px-3 py-2 text-sm ${
                pathname?.startsWith(n.href) ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="border-t p-3">
          {orgs.length > 0 && (
            <select
              value={orgId ?? ""}
              onChange={(e) => {
                setOrgId(e.target.value);
                localStorage.setItem("activeOrgId", e.target.value);
                router.refresh();
              }}
              className="mb-2 w-full rounded border border-gray-300 px-2 py-1 text-xs"
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name} ({o.plan})</option>
              ))}
            </select>
          )}
          <button
            onClick={async () => { await signOut(); router.replace("/login"); }}
            className="w-full rounded border px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}