import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router";

import { errorText } from "../api/client";
import type { Competitor, Workspace } from "../api/monitoring";
import {
  useCompetitors,
  useDeleteWorkspace,
  useMembers,
  useUpdateWorkspace,
  useWorkspace,
} from "../api/queries";
import { useUser } from "../auth/AuthProvider";
import { AvatarDialog } from "../components/AvatarDialog";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { CompetitorWizard } from "../components/discovery/CompetitorWizard";
import { HeadAvatar } from "../components/HeadAvatar";
import { InsightFeed } from "../components/insights/InsightFeed";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { WorkspaceDialog } from "../components/WorkspaceDialog";
import { hostname, timeAgo } from "../format";
import "./Page.css";

/** Workspace header and tabs; the tab pages render in the outlet. */
export function WorkspaceLayout() {
  const { workspaceId = "" } = useParams();
  const navigate = useNavigate();
  const workspace = useWorkspace(workspaceId);
  const [modal, setModal] = useState<"edit" | "delete" | "avatar" | null>(null);
  const user = useUser();
  const members = useMembers(workspace.data?.org_id ?? "");
  const myRole = members.data?.find((m) => m.user_id === user.id)?.role;
  const canAdmin = myRole === "admin" || myRole === "owner";

  if (workspace.isLoading) return <p className="page page__note">Loading…</p>;
  if (workspace.error || !workspace.data) {
    return <p className="page page__error">{workspace.error ? errorText(workspace.error) : "Workspace not found"}</p>;
  }
  const ws = workspace.data;
  const close = () => setModal(null);
  const base = `/workspaces/${ws.id}`;

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/workspaces">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">{ws.name}</span>
      </nav>
      <div className="page__head">
        <HeadAvatar name={ws.name} avatar={ws} editable={canAdmin} onEdit={() => setModal("avatar")} />
        <div className="page__heading">
          <h1 className="page__title">{ws.name}</h1>
          {ws.description && <p className="page__subtitle">{ws.description}</p>}
        </div>
        <div className="page__actions">
          <Button variant="text" onClick={() => setModal("edit")}>
            Edit
          </Button>
          <Button variant="text" className="btn--danger" onClick={() => setModal("delete")}>
            Delete
          </Button>
        </div>
      </div>

      <nav className="tabs" aria-label="Workspace sections">
        <NavLink to={base} end className="tabs__tab">
          Insights
        </NavLink>
        <NavLink to={`${base}/competitors`} className="tabs__tab">
          Competitors
        </NavLink>
        <NavLink to={`${base}/search`} className="tabs__tab">
          Search
        </NavLink>
        <NavLink to={`${base}/reports`} className="tabs__tab">
          Reports
        </NavLink>
      </nav>

      <Outlet context={ws satisfies Workspace} />

      {modal === "edit" && <EditWorkspace id={ws.id} initial={ws} onClose={close} />}
      {modal === "avatar" && <AvatarDialog kind="workspace" id={ws.id} name={ws.name} avatar={ws} onClose={close} />}
      {modal === "delete" && (
        <DeleteWorkspace id={ws.id} orgId={ws.org_id} name={ws.name} onClose={close} onDeleted={() => navigate("/workspaces")} />
      )}
    </div>
  );
}

/** The workspace the surrounding <WorkspaceLayout> loaded. */
export const useCurrentWorkspace = () => useOutletContext<Workspace>();

/** Insights tab (default): what changed across this workspace's competitors. */
export function WorkspaceInsights() {
  const ws = useCurrentWorkspace();
  return (
    <div className="page__section">
      <InsightFeed
        scope={{ kind: "workspace", id: ws.id }}
        emptyAction={
          <Link to={`/workspaces/${ws.id}/competitors`} className="btn btn--filled btn-link">
            Add competitors
          </Link>
        }
      />
    </div>
  );
}

/** Competitors tab: the workspace's competitors and how fresh their data is. */
export function WorkspaceCompetitors() {
  const ws = useCurrentWorkspace();
  const navigate = useNavigate();
  const competitors = useCompetitors(ws.id);
  const [adding, setAdding] = useState(false);

  return (
    <section className="page__section" aria-labelledby="competitors-title">
      <div className="page__section-head">
        <h2 id="competitors-title" className="page__section-title">
          Competitors{competitors.data ? ` (${competitors.data.total})` : ""}
        </h2>
        <Button onClick={() => setAdding(true)}>Add competitor</Button>
      </div>

      {competitors.isLoading && <p className="page__note">Loading competitors…</p>}
      {competitors.error && <p className="page__error">{errorText(competitors.error)}</p>}
      {competitors.data?.items.length === 0 && (
        <div className="blank">
          <h2 className="blank__title">No competitors yet</h2>
          <p>Add a competitor and the pages you want watched for changes.</p>
          <Button onClick={() => setAdding(true)}>Add competitor</Button>
        </div>
      )}
      {!!competitors.data?.items.length && (
        <div className="cards">
          {competitors.data.items.map((c) => (
            <CompetitorCard key={c.id} competitor={c} />
          ))}
        </div>
      )}

      {adding && (
        <AddCompetitor
          workspaceId={ws.id}
          onClose={() => setAdding(false)}
          onCreated={(c) => navigate(`/competitors/${c.id}`)}
        />
      )}
    </section>
  );
}

function CompetitorCard({ competitor: c }: { competitor: Competitor }) {
  const lastScraped = c.urls
    .map((u) => u.last_scraped_at)
    .filter((t): t is string => !!t)
    .sort()
    .at(-1);

  return (
    <Link to={`/competitors/${c.id}`} className="card">
      <h3 className="card__title">{c.name}</h3>
      {c.website_url && <p className="card__text">{hostname(c.website_url)}</p>}
      <div className="card__meta">
        {!c.is_active && <Chip tone="warning">Paused</Chip>}
        <span>
          {c.urls.length} {c.urls.length === 1 ? "page" : "pages"}
        </span>
        <span aria-hidden="true">·</span>
        <span>Checked {lastScraped ? timeAgo(lastScraped) : "never"}</span>
      </div>
    </Link>
  );
}

function EditWorkspace({
  id,
  initial,
  onClose,
}: {
  id: string;
  initial: { name: string; description: string | null };
  onClose: () => void;
}) {
  const update = useUpdateWorkspace(id);
  return (
    <WorkspaceDialog
      title="Edit workspace"
      confirmLabel="Save"
      initial={initial}
      onSave={async (input) => {
        await update.mutateAsync(input);
        onClose();
      }}
      onClose={onClose}
    />
  );
}

function DeleteWorkspace({
  id,
  orgId,
  name,
  onClose,
  onDeleted,
}: {
  id: string;
  orgId: string;
  name: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const remove = useDeleteWorkspace(id, orgId);
  return (
    <ConfirmDialog
      title="Delete workspace?"
      confirmLabel="Delete"
      onConfirm={async () => {
        await remove.mutateAsync();
        onDeleted();
      }}
      onClose={onClose}
    >
      “{name}” and all of its competitors, monitored pages and scrape history will be deleted. This can't be undone.
    </ConfirmDialog>
  );
}

function AddCompetitor({
  workspaceId,
  onClose,
  onCreated,
}: {
  workspaceId: string;
  onClose: () => void;
  onCreated: (c: Competitor) => void;
}) {
  return <CompetitorWizard workspaceId={workspaceId} onClose={onClose} onCreated={onCreated} />;
}
