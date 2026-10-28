import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { useAuth, useUser } from "../auth/AuthProvider";
import { Logo } from "./Logo";
import "./AppShell.css";

/** Gmail-style frame: app bar, collapsible nav rail, rounded content panel. */
export function AppShell() {
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
        <div className="shell__spacer" />
        <AccountMenu />
      </header>

      <nav className="shell__nav" aria-label="Main">
        <NavLink to="/" end className="nav-item">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
          </svg>
          <span className="nav-item__label">Dashboard</span>
        </NavLink>
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
        <Avatar name={name} size={32} />
      </button>
      {open && (
        <div className="account__panel" role="dialog" aria-label="Account">
          <div className="account__email">{user.email}</div>
          <Avatar name={name} size={80} />
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
    </div>
  );
}

function Avatar({ name, size }: { name: string; size: number }) {
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.45 }} aria-hidden="true">
      {name[0]?.toUpperCase()}
    </span>
  );
}
