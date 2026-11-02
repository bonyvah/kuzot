import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { Organization } from "../api/monitoring";
import { useOrganizations } from "../api/queries";

const ORG_KEY = "kuzot.org";

interface OrgContextValue {
  orgs: Organization[];
  /** Undefined until organizations load, or when the user has none. */
  current: Organization | undefined;
  select: (orgId: string) => void;
  isLoading: boolean;
  error: Error | null;
}

const OrgContext = createContext<OrgContextValue | null>(null);

/** Tracks which organization the dashboard shows. The choice is remembered per browser. */
export function OrgProvider({ children }: { children: ReactNode }) {
  const { data: orgs = [], isLoading, error } = useOrganizations();
  const [selectedId, setSelectedId] = useState(() => safeStorage(() => localStorage.getItem(ORG_KEY)));

  const value = useMemo<OrgContextValue>(() => {
    // Fall back to the personal org when the remembered one is gone.
    const current =
      orgs.find((o) => o.id === selectedId) ?? orgs.find((o) => o.org_type === "personal") ?? orgs[0];
    return {
      orgs,
      current,
      isLoading,
      error,
      select: (orgId) => {
        setSelectedId(orgId);
        safeStorage(() => localStorage.setItem(ORG_KEY, orgId));
      },
    };
  }, [orgs, selectedId, isLoading, error]);

  return <OrgContext value={value}>{children}</OrgContext>;
}

export function useOrg(): OrgContextValue {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used inside <OrgProvider>");
  return ctx;
}

function safeStorage<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}
