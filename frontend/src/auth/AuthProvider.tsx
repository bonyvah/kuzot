import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { authApi, type User } from "../api/auth";
import { refreshSession, session, setSessionExpiredHandler } from "../api/client";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: User };

interface AuthContextValue {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string | null) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ANONYMOUS: AuthState = { status: "anonymous", user: null };

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>(() =>
    session.hinted() ? { status: "loading", user: null } : ANONYMOUS,
  );

  const dropSession = useCallback(() => {
    queryClient.clear();
    setState(ANONYMOUS);
  }, [queryClient]);

  // Restore the session from the refresh cookie on first load.
  useEffect(() => {
    if (state.status !== "loading") return;
    let cancelled = false;
    (async () => {
      try {
        const ok = await refreshSession();
        const user = ok ? await authApi.me() : null;
        if (!cancelled) setState(user ? { status: "authenticated", user } : ANONYMOUS);
      } catch {
        if (!cancelled) setState(ANONYMOUS);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.status]);

  useEffect(() => {
    setSessionExpiredHandler(dropSession);

    // Signing out in another tab removes the shared session hint.
    const onStorage = (e: StorageEvent) => {
      if (e.key === session.hintKey && e.newValue === null) dropSession();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [dropSession]);

  const signIn = useCallback(async (email: string, password: string) => {
    session.start(await authApi.login(email, password));
    const user = await authApi.me();
    setState({ status: "authenticated", user });
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, fullName: string | null) => {
      await authApi.register(email, password, fullName);
      await signIn(email, password);
    },
    [signIn],
  );

  const signOut = useCallback(async () => {
    // Revoke first: the cookie can only be cleared by the server.
    await authApi.logout().catch(() => {});
    session.end();
    dropSession();
  }, [dropSession]);

  const value = useMemo(() => ({ state, signIn, signUp, signOut }), [state, signIn, signUp, signOut]);

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** The signed-in user. Only call below a route guarded by <RequireAuth>. */
export function useUser(): User {
  const { state } = useAuth();
  if (state.status !== "authenticated") throw new Error("useUser called without a session");
  return state.user;
}
