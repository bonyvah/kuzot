import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { useCreateOrganization } from "../api/queries";
import { useOrg } from "../org/OrgProvider";
import { Dialog } from "./Dialog";
import { TextField } from "./TextField";
import { useSave } from "./useSave";
import "./OrgSwitcher.css";

/** App-bar menu: switch organization, create a team, open org settings. */
export function OrgSwitcher() {
  const { orgs, current, select } = useOrg();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
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

  if (!current) return null;

  const switchTo = (orgId: string) => {
    setOpen(false);
    if (orgId === current.id) return;
    select(orgId);
    // Pages below belong to the old org's workspaces.
    navigate("/");
  };

  return (
    <div className="orgs" ref={rootRef}>
      <button
        type="button"
        className="orgs__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <OrgBadge name={current.name} />
        <span className="orgs__name">{current.name}</span>
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path fill="currentColor" d="M7 10l5 5 5-5z" />
        </svg>
      </button>
      {open && (
        <div className="orgs__panel" role="menu" aria-label="Organizations">
          {orgs.map((o) => (
            <button
              key={o.id}
              type="button"
              role="menuitemradio"
              aria-checked={o.id === current.id}
              className="orgs__item"
              onClick={() => switchTo(o.id)}
            >
              <OrgBadge name={o.name} />
              <span className="orgs__item-text">
                <span className="orgs__item-name">{o.name}</span>
                <span className="orgs__item-type">{o.org_type === "personal" ? "Personal" : "Team"}</span>
              </span>
              {o.id === current.id && (
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                  <path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                </svg>
              )}
            </button>
          ))}
          <div className="orgs__divider" role="separator" />
          <Link to="/organization" role="menuitem" className="orgs__item orgs__action" onClick={() => setOpen(false)}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path
                fill="currentColor"
                d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"
              />
            </svg>
            Members &amp; settings
          </Link>
          <button
            type="button"
            role="menuitem"
            className="orgs__item orgs__action"
            onClick={() => {
              setOpen(false);
              setCreating(true);
            }}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
            </svg>
            Create an organization
          </button>
        </div>
      )}
      {creating && (
        <CreateTeamDialog
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            select(id);
            navigate("/organization");
          }}
        />
      )}
    </div>
  );
}

function CreateTeamDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const create = useCreateOrganization();
  const [name, setName] = useState("");
  const save = useSave(async (value: string) => {
    const org = await create.mutateAsync(value);
    onCreated(org.id);
  });

  return (
    <Dialog
      open
      title="Create a team"
      confirmLabel="Create"
      onClose={onClose}
      onSubmit={() => (name.trim() ? save.run(name.trim()) : save.setError("Enter a team name"))}
      busy={save.busy}
      error={save.error}
    >
      <p className="dialog__lead">
        A team is a shared organization: invite colleagues and track competitors together. It starts with a “General”
        workspace.
      </p>
      <TextField label="Team name" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={255} />
    </Dialog>
  );
}

export function OrgBadge({ name, size = 28 }: { name: string; size?: number }) {
  return (
    <span className="org-badge" style={{ width: size, height: size, fontSize: size * 0.45 }} aria-hidden="true">
      {name[0]?.toUpperCase()}
    </span>
  );
}
