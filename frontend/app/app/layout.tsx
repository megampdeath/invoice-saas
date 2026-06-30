"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { signOut } from "@/lib/auth";
import { OrgProvider, useOrg } from "@/lib/org-context";
import { useRouter } from "next/navigation";

const NAV = [
  { href: "/app/invoices", label: "Inbox" },
  { href: "/app/suppliers", label: "Suppliers" },
  { href: "/app/exports", label: "Exports" },
  { href: "/app/settings", label: "Settings" },
];

function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { orgs, orgId, setOrgId, loading } = useOrg();

  if (loading) return <div className="p-8 text-sm text-gray-500">Loading…</div>;

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
              onChange={(e) => { setOrgId(e.target.value); router.refresh(); }}
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

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <OrgProvider>
      <Shell>{children}</Shell>
    </OrgProvider>
  );
}
