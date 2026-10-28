import { Navigate, Outlet, useLocation } from "react-router";

import { useAuth } from "./AuthProvider";
import { Splash } from "../components/Splash";

interface FromState {
  from?: string;
}

/** Renders child routes only for signed-in users; others go to /signin and come back after. */
export function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === "loading") return <Splash />;
  if (state.status === "anonymous") {
    const from = location.pathname + location.search + location.hash;
    return <Navigate to="/signin" replace state={{ from } satisfies FromState} />;
  }
  return <Outlet />;
}

/** Keeps signed-in users off the auth pages. */
export function RedirectIfAuthed() {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === "loading") return <Splash />;
  if (state.status === "authenticated") {
    const from = (location.state as FromState | null)?.from;
    return <Navigate to={from ?? "/"} replace />;
  }
  return <Outlet />;
}
