import { useState } from "react";
import { Link } from "react-router";

import { errorText } from "../api/client";
import { useCreateWorkspace, useWorkspaces } from "../api/queries";
import { Button } from "../components/Button";
import { SelectField } from "../components/SelectField";
import { WorkspaceDialog } from "../components/WorkspaceDialog";
import { formatDate } from "../format";
import { useOrg } from "../org/OrgProvider";
import "./Page.css";

/** Home: the current organization's workspaces. */
export function DashboardPage() {
  const { orgs, current, select, isLoading, error } = useOrg();
  const workspaces = useWorkspaces(current?.id);
  const [creating, setCreating] = useState(false);

  if (isLoading) return <p className="page page__note">Loading…</p>;
  if (error) return <p className="page page__error">{errorText(error)}</p>;
  if (!current) return <p className="page page__note">You don't belong to any organization yet.</p>;

  return (
    <div className="page">
      <div className="page__head">
        <div className="page__heading">
          <h1 className="page__title">Workspaces</h1>
          <p className="page__subtitle">Group the competitors you track, one workspace per market or product.</p>
        </div>
        <div className="page__actions">
          {orgs.length > 1 && (
            <SelectField
              label="Organization"
              value={current.id}
              onChange={(e) => select(e.target.value)}
              options={orgs.map((o) => ({ value: o.id, label: o.name }))}
            />
          )}
          <Button onClick={() => setCreating(true)}>New workspace</Button>
        </div>
      </div>

      {workspaces.isLoading && <p className="page__note">Loading workspaces…</p>}
      {workspaces.error && <p className="page__error">{errorText(workspaces.error)}</p>}
      {workspaces.data?.length === 0 && (
        <div className="blank">
          <h2 className="blank__title">No workspaces yet</h2>
          <p>Create one to start adding competitors.</p>
          <Button onClick={() => setCreating(true)}>New workspace</Button>
        </div>
      )}
      {!!workspaces.data?.length && (
        <div className="cards">
          {workspaces.data.map((ws) => (
            <Link key={ws.id} to={`/workspaces/${ws.id}`} className="card">
              <h2 className="card__title">{ws.name}</h2>
              {ws.description && <p className="card__text">{ws.description}</p>}
              <div className="card__meta">Created {formatDate(ws.created_at)}</div>
            </Link>
          ))}
        </div>
      )}

      {creating && <CreateWorkspace orgId={current.id} onClose={() => setCreating(false)} />}
    </div>
  );
}

function CreateWorkspace({ orgId, onClose }: { orgId: string; onClose: () => void }) {
  const create = useCreateWorkspace(orgId);
  return (
    <WorkspaceDialog
      title="New workspace"
      confirmLabel="Create"
      onSave={async (input) => {
        await create.mutateAsync(input);
        onClose();
      }}
      onClose={onClose}
    />
  );
}
