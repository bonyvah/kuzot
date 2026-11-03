import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { useAuth, useUser } from "../auth/AuthProvider";
import { OrgProvider } from "../org/OrgProvider";
import { Avatar } from "./Avatar";
import { AvatarDialog } from "./AvatarDialog";
import { Logo } from "./Logo";
import { OrgSwitcher } from "./OrgSwitcher";
import { WorkspaceTree } from "./WorkspaceTree";
import "./AppShell.css";

/** Gmail-style frame: app bar, collapsible nav rail, rounded content panel. */
export function AppShell() {
  return (
    <OrgProvider>
      <Shell />
    </OrgProvider>
  );
}

function Shell() {
  const [navOpen, setNavOpen] = useState(true);

  return (
    <div className={`shell${navOpen ? "" : " shell--collapsed"}`}>
      <header className="shell__bar">
        <button
          type="button"
          className="icon-btn"
          aria-label="Main menu"
          aria-expanded={navOpen}
          onClick={() => setNavOpen((v) => !v)}
        >
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
          </svg>
        </button>
        <Link to="/" className="shell__brand" aria-label="Kuzot home">
          <Logo />
        </Link>
        <OrgSwitcher />
        <div className="shell__spacer" />
        <AccountMenu />
      </header>

      <nav className="shell__nav" aria-label="Main">
        <NavLink to="/" end className="nav-item">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M7 2v11h3v9l7-12h-4l4-8z" />
          </svg>
          <span className="nav-item__label">Insights</span>
        </NavLink>
        <NavLink to="/workspaces" end className="nav-item">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
          </svg>
          <span className="nav-item__label">Workspaces</span>
        </NavLink>
        <WorkspaceTree />
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}

function AccountMenu() {
  const user = useUser();
  const { signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const name = user.full_name || user.email;

  return (
    <div className="account" ref={rootRef}>
      <button
        type="button"
        className="account__trigger"
        aria-label={`Kuzot Account: ${name} (${user.email})`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
      >
        <Avatar name={name} avatar={user} size={32} round />
      </button>
      {open && (
        <div className="account__panel" role="dialog" aria-label="Account">
          <div className="account__email">{user.email}</div>
          <button
            type="button"
            className="account__picture"
            aria-label="Change your picture"
            onClick={() => {
              setOpen(false);
              setPicking(true);
            }}
          >
            <Avatar name={name} avatar={user} size={80} round />
            <span className="account__picture-edit" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16">
                <path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
              </svg>
            </span>
          </button>
          <div className="account__greeting">Hi, {name.split(" ")[0]}!</div>
          <button type="button" className="account__signout" onClick={signOut}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path
                fill="currentColor"
                d="M10.09 15.59 11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5a2 2 0 0 0-2 2v4h2V5h14v14H5v-4H3v4a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"
              />
            </svg>
            Sign out
          </button>
        </div>
      )}
      {picking && <AvatarDialog kind="user" id="" name={name} avatar={user} onClose={() => setPicking(false)} />}
    </div>
  );
}
