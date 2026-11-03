import { useEffect, useState } from "react";
import { NavLink, useMatch } from "react-router";

import type { Workspace } from "../api/monitoring";
import { useCompetitor, useCompetitors, useWorkspaces } from "../api/queries";
import { useOrg } from "../org/OrgProvider";
import { Avatar } from "./Avatar";
import "./WorkspaceTree.css";

const EXPANDED_KEY = "kuzot.nav.expanded";

/** Workspace ids the user has expanded; remembered across reloads. */
function useExpanded() {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(EXPANDED_KEY) ?? "[]") as string[]);
    } catch {
      return new Set();
    }
  });

  const update = (fn: (next: Set<string>) => void) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      fn(next);
      try {
        localStorage.setItem(EXPANDED_KEY, JSON.stringify([...next]));
      } catch {
        // storage unavailable: the state lasts for this visit
      }
      return next;
    });

  return {
    isOpen: (id: string) => expanded.has(id),
    toggle: (id: string) => update((s) => (s.has(id) ? s.delete(id) : s.add(id))),
    open: (id: string) => {
      if (!expanded.has(id)) update((s) => s.add(id));
    },
  };
}

/** The workspace the current page belongs to, if any. */
function useCurrentWorkspaceId(): string | undefined {
  const onWorkspace = useMatch("/workspaces/:workspaceId/*");
  const onCompetitor = useMatch("/competitors/:competitorId/*");
  const competitor = useCompetitor(onCompetitor?.params.competitorId ?? "");
  return onWorkspace?.params.workspaceId ?? competitor.data?.workspace_id;
}

/** Sidebar tree: the current organization's workspaces, each expandable into its competitors. */
export function WorkspaceTree() {
  const { current } = useOrg();
  const { data: workspaces = [] } = useWorkspaces(current?.id);
  const expanded = useExpanded();
  const here = useCurrentWorkspaceId();

  // Show where you are: the current page's workspace opens by itself.
  useEffect(() => {
    if (here) expanded.open(here);
    // only when the location changes, not on every toggle
  }, [here]);

  if (!workspaces.length) return null;

  return (
    <div className="tree">
      <div className="nav-heading">{current?.name}</div>
      <ul className="tree__list">
        {workspaces.map((ws) => (
          <WorkspaceNode key={ws.id} ws={ws} open={expanded.isOpen(ws.id)} onToggle={() => expanded.toggle(ws.id)} />
        ))}
      </ul>
    </div>
  );
}

function WorkspaceNode({ ws, open, onToggle }: { ws: Workspace; open: boolean; onToggle: () => void }) {
  const listId = `tree-${ws.id}`;
  return (
    <li>
      <div className="tree__row">
        <NavLink to={`/workspaces/${ws.id}`} end={false} className="nav-item tree__link" title={ws.name}>
          <Avatar name={ws.name} avatar={ws} size={20} className="nav-item__avatar" />
          <span className="nav-item__label tree__name">{ws.name}</span>
        </NavLink>
        <button
          type="button"
          className="tree__toggle"
          aria-expanded={open}
          aria-controls={listId}
          aria-label={`${open ? "Hide" : "Show"} competitors in ${ws.name}`}
          onClick={onToggle}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
          </svg>
        </button>
      </div>
      {open && <CompetitorList id={listId} workspaceId={ws.id} />}
    </li>
  );
}

function CompetitorList({ id, workspaceId }: { id: string; workspaceId: string }) {
  const competitors = useCompetitors(workspaceId);
  const items = competitors.data?.items ?? [];
  return (
    <ul id={id} className="tree__children">
      {competitors.isLoading && <li className="tree__note">Loading…</li>}
      {competitors.data && items.length === 0 && <li className="tree__note">No competitors yet</li>}
      {items.map((c) => (
        <li key={c.id}>
          <NavLink to={`/competitors/${c.id}`} className="nav-item tree__child" title={c.name}>
            <Avatar name={c.name} avatar={c} size={18} className="nav-item__avatar" />
            <span className="nav-item__label tree__name">{c.name}</span>
          </NavLink>
        </li>
      ))}
    </ul>
  );
}
