"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { supabase } from "@/lib/auth";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

export interface Org {
  id: string;
  name: string;
  slug: string;
  plan: string;
  role: string;
}

interface OrgCtx {
  orgId: string | null;
  orgs: Org[];
  loading: boolean;
  setOrgId: (id: string) => void;
}

const Ctx = createContext<OrgCtx>({ orgId: null, orgs: [], loading: true, setOrgId: () => {} });

export function OrgProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace("/login");
        return;
      }
      try {
        // /api/me auto-creates a free workspace for new users (no payment)
        // and returns the user's organizations. Using it here guarantees a
        // brand-new signup lands with an org instead of an empty list.
        const me = await api.get<{ organizations: Org[] }>("/api/me");
        setOrgs(me.organizations || []);
        const stored = typeof window !== "undefined" ? localStorage.getItem("activeOrgId") : null;
        const active = stored && (me.organizations || []).some((o) => o.id === stored)
          ? stored
          : me.organizations?.[0]?.id ?? null;
        setOrgIdState(active);
        if (active) localStorage.setItem("activeOrgId", active);
      } catch {
        // network/auth error; stay empty
      }
      setLoading(false);
    })();
  }, [router]);

  const setOrgId = useCallback((id: string) => {
    setOrgIdState(id);
    localStorage.setItem("activeOrgId", id);
  }, []);

  return <Ctx.Provider value={{ orgId, orgs, loading, setOrgId }}>{children}</Ctx.Provider>;
}

export function useOrg(): OrgCtx {
  return useContext(Ctx);
}
