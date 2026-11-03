import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorText } from "../api/client";
import { useCompetitor, useDeleteCompetitor, useUpdateCompetitor, useWorkspace } from "../api/queries";
import { AvatarDialog } from "../components/AvatarDialog";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { CompetitorDialog } from "../components/CompetitorDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { HeadAvatar } from "../components/HeadAvatar";
import { InsightFeed } from "../components/insights/InsightFeed";
import "./Page.css";

type Modal =
  | { kind: "edit" }
  | { kind: "avatar" }
  | { kind: "delete" }
  | null;

/** One competitor: what changed on its pages. Its monitored pages live on their own page. */
export function CompetitorPage() {
  const { competitorId = "" } = useParams();
  const navigate = useNavigate();
  const competitor = useCompetitor(competitorId);
  const workspace = useWorkspace(competitor.data?.workspace_id ?? "");
  const update = useUpdateCompetitor(competitorId);
  const [modal, setModal] = useState<Modal>(null);

  if (competitor.isLoading) return <p className="page page__note">Loading…</p>;
  if (competitor.error || !competitor.data) {
    return (
      <p className="page page__error">{competitor.error ? errorText(competitor.error) : "Competitor not found"}</p>
    );
  }
  const c = competitor.data;
  const close = () => setModal(null);

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/workspaces">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <Link to={`/workspaces/${c.workspace_id}`}>{workspace.data?.name ?? "Workspace"}</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">{c.name}</span>
      </nav>
      <div className="page__head">
        <HeadAvatar name={c.name} avatar={c} editable onEdit={() => setModal({ kind: "avatar" })} />
        <div className="page__heading">
          <h1 className="page__title">
            {c.name} {!c.is_active && <Chip tone="warning">Paused</Chip>}
          </h1>
          {c.website_url && (
            <p className="page__subtitle">
              <a href={c.website_url} target="_blank" rel="noreferrer noopener">
                {c.website_url}
              </a>
            </p>
          )}
          {c.description && <p className="page__subtitle">{c.description}</p>}
        </div>
        <div className="page__actions">
          <Link to={`/competitors/${c.id}/pages`} className="btn btn--text btn-link">
            Pages ({c.urls.length})
          </Link>
          <Link to={`/competitors/${c.id}/history`} className="btn btn--text btn-link">
            History
          </Link>
          <Button
            variant="text"
            disabled={update.isPending}
            onClick={() => update.mutate({ is_active: !c.is_active })}
          >
            {c.is_active ? "Pause" : "Resume"}
          </Button>
          <Button variant="text" onClick={() => setModal({ kind: "edit" })}>
            Edit
          </Button>
          <Button variant="text" className="btn--danger" onClick={() => setModal({ kind: "delete" })}>
            Delete
          </Button>
        </div>
      </div>
      {update.error && <p className="page__error">{errorText(update.error)}</p>}

      <section className="page__section page--feed" aria-labelledby="insights-title">
        
        <InsightFeed scope={{ kind: "competitor", id: c.id }} />
      </section>

      {modal?.kind === "avatar" && (
        <AvatarDialog kind="competitor" id={c.id} name={c.name} avatar={c} onClose={close} />
      )}
      {modal?.kind === "edit" && (
        <CompetitorDialog
          initial={c}
          onSave={async (input) => {
            await update.mutateAsync(input);
            close();
          }}
          onClose={close}
        />
      )}
      {modal?.kind === "delete" && (
        <DeleteCompetitor
          id={c.id}
          workspaceId={c.workspace_id}
          name={c.name}
          onClose={close}
          onDeleted={() => navigate(`/workspaces/${c.workspace_id}/competitors`)}
        />
      )}
    </div>
  );
}

function DeleteCompetitor({
  id,
  workspaceId,
  name,
  onClose,
  onDeleted,
}: {
  id: string;
  workspaceId: string;
  name: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const remove = useDeleteCompetitor(id, workspaceId);
  return (
    <ConfirmDialog
      title="Delete competitor?"
      confirmLabel="Delete"
      onConfirm={async () => {
        await remove.mutateAsync();
        onDeleted();
      }}
      onClose={onClose}
    >
      “{name}”, its monitored pages and their scrape history will be deleted. This can't be undone.
    </ConfirmDialog>
  );
}
