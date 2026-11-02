import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorText } from "../api/client";
import type { Competitor } from "../api/monitoring";
import {
  useCompetitors,
  useCreateCompetitor,
  useDeleteWorkspace,
  useUpdateWorkspace,
  useWorkspace,
} from "../api/queries";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { CompetitorDialog } from "../components/CompetitorDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { WorkspaceDialog } from "../components/WorkspaceDialog";
import { hostname, timeAgo } from "../format";
import "./Page.css";

type Modal = "edit" | "delete" | "add" | null;

/** One workspace: its competitors and how fresh their data is. */
export function WorkspacePage() {
  const { workspaceId = "" } = useParams();
  const navigate = useNavigate();
  const workspace = useWorkspace(workspaceId);
  const competitors = useCompetitors(workspaceId);
  const [modal, setModal] = useState<Modal>(null);

  if (workspace.isLoading) return <p className="page page__note">Loading…</p>;
  if (workspace.error || !workspace.data) {
    return <p className="page page__error">{workspace.error ? errorText(workspace.error) : "Workspace not found"}</p>;
  }
  const ws = workspace.data;
  const close = () => setModal(null);

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">{ws.name}</span>
      </nav>
      <div className="page__head">
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

      <section className="page__section" aria-labelledby="competitors-title">
        <div className="page__section-head">
          <h2 id="competitors-title" className="page__section-title">
            Competitors{competitors.data ? ` (${competitors.data.total})` : ""}
          </h2>
          <Button onClick={() => setModal("add")}>Add competitor</Button>
        </div>

        {competitors.isLoading && <p className="page__note">Loading competitors…</p>}
        {competitors.error && <p className="page__error">{errorText(competitors.error)}</p>}
        {competitors.data?.items.length === 0 && (
          <div className="blank">
            <h2 className="blank__title">No competitors yet</h2>
            <p>Add a competitor and the pages you want watched for changes.</p>
            <Button onClick={() => setModal("add")}>Add competitor</Button>
          </div>
        )}
        {!!competitors.data?.items.length && (
          <div className="cards">
            {competitors.data.items.map((c) => (
              <CompetitorCard key={c.id} competitor={c} />
            ))}
          </div>
        )}
      </section>

      {modal === "edit" && <EditWorkspace id={ws.id} initial={ws} onClose={close} />}
      {modal === "delete" && (
        <DeleteWorkspace id={ws.id} orgId={ws.org_id} name={ws.name} onClose={close} onDeleted={() => navigate("/")} />
      )}
      {modal === "add" && (
        <AddCompetitor
          workspaceId={ws.id}
          onClose={close}
          onCreated={(c) => navigate(`/competitors/${c.id}`)}
        />
      )}
    </div>
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
  const create = useCreateCompetitor(workspaceId);
  return (
    <CompetitorDialog
      title="Add competitor"
      confirmLabel="Add"
      withFirstUrl
      onSave={async (input, firstUrl) => {
        const competitor = await create.mutateAsync({ ...input, initial_urls: firstUrl ? [firstUrl] : [] });
        onCreated(competitor);
      }}
      onClose={onClose}
    />
  );
}
