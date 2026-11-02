import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { errorText } from "../api/client";
import type { MonitoredUrl } from "../api/monitoring";
import {
  useAddUrl,
  useCompetitor,
  useDeleteCompetitor,
  useDeleteUrl,
  useTriggerScrape,
  useUpdateCompetitor,
  useUpdateUrl,
  useWorkspace,
} from "../api/queries";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { CompetitorDialog } from "../components/CompetitorDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { JobHistory } from "../components/JobHistory";
import { IntervalDialog, UrlDialog } from "../components/UrlDialog";
import { urlTypeLabel } from "../components/urlForm";
import { formatDate, formatInterval, timeAgo } from "../format";
import "./Page.css";

type Modal =
  | { kind: "edit" }
  | { kind: "delete" }
  | { kind: "add-url" }
  | { kind: "interval"; url: MonitoredUrl }
  | { kind: "delete-url"; url: MonitoredUrl }
  | null;

/** One competitor: its monitored pages, and scrape history for the selected page. */
export function CompetitorPage() {
  const { competitorId = "" } = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
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

  // The selected page's history is in the URL so it survives reloads and can be shared.
  const selected = c.urls.find((u) => u.id === search.get("url")) ?? c.urls[0];
  const selectUrl = (id: string) => setSearch({ url: id }, { replace: true });

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <Link to={`/workspaces/${c.workspace_id}`}>{workspace.data?.name ?? "Workspace"}</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">{c.name}</span>
      </nav>
      <div className="page__head">
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

      <section className="page__section" aria-labelledby="urls-title">
        <div className="page__section-head">
          <h2 id="urls-title" className="page__section-title">
            Monitored pages ({c.urls.length})
          </h2>
          <Button onClick={() => setModal({ kind: "add-url" })}>Add page</Button>
        </div>
        {c.urls.length === 0 ? (
          <div className="blank">
            <h2 className="blank__title">No pages monitored</h2>
            <p>Add a pricing page, changelog or blog to start tracking changes.</p>
            <Button onClick={() => setModal({ kind: "add-url" })}>Add page</Button>
          </div>
        ) : (
          <UrlTable
            competitorId={c.id}
            urls={c.urls}
            selectedId={selected?.id}
            onSelect={selectUrl}
            onEditInterval={(url) => setModal({ kind: "interval", url })}
            onDelete={(url) => setModal({ kind: "delete-url", url })}
          />
        )}
      </section>

      {selected && (
        <section className="page__section" aria-labelledby="history-title">
          <div className="page__section-head">
            <h2 id="history-title" className="page__section-title">
              Scrape history · <span className="page__note">{selected.url}</span>
            </h2>
          </div>
          <JobHistory key={selected.id} url={selected} competitorId={c.id} />
        </section>
      )}

      {modal?.kind === "edit" && (
        <CompetitorDialog
          title="Edit competitor"
          confirmLabel="Save"
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
          onDeleted={() => navigate(`/workspaces/${c.workspace_id}`)}
        />
      )}
      {modal?.kind === "add-url" && <AddUrl competitorId={c.id} onClose={close} onAdded={selectUrl} />}
      {modal?.kind === "interval" && <EditInterval competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "delete-url" && <DeleteUrl competitorId={c.id} url={modal.url} onClose={close} />}
    </div>
  );
}

interface UrlTableProps {
  competitorId: string;
  urls: MonitoredUrl[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  onEditInterval: (url: MonitoredUrl) => void;
  onDelete: (url: MonitoredUrl) => void;
}

function UrlTable({ competitorId, urls, selectedId, onSelect, onEditInterval, onDelete }: UrlTableProps) {
  const updateUrl = useUpdateUrl(competitorId);
  const trigger = useTriggerScrape(competitorId);
  const busyId = trigger.isPending ? trigger.variables : undefined;
  const error = trigger.error ?? updateUrl.error;

  return (
    <>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Page</th>
              <th scope="col">Type</th>
              <th scope="col">Check</th>
              <th scope="col">Last checked</th>
              <th scope="col">Active</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {urls.map((url) => (
              <tr key={url.id} className={url.id === selectedId ? "table__row--selected" : undefined}>
                <td className="table__url" title={url.url}>
                  <a href={url.url} target="_blank" rel="noreferrer noopener">
                    {url.url}
                  </a>
                </td>
                <td>{urlTypeLabel(url.url_type)}</td>
                <td>
                  <Button variant="text" onClick={() => onEditInterval(url)} aria-label={`Change check frequency for ${url.url}`}>
                    {formatInterval(url.scrape_interval_minutes)}
                  </Button>
                </td>
                <td title={formatDate(url.last_scraped_at)}>{timeAgo(url.last_scraped_at)}</td>
                <td>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={url.is_active}
                      disabled={updateUrl.isPending}
                      onChange={() => updateUrl.mutate({ id: url.id, is_active: !url.is_active })}
                    />
                    <span className="visually-hidden">Monitor {url.url}</span>
                  </label>
                </td>
                <td>
                  <div className="table__actions">
                    <Button
                      variant="text"
                      disabled={busyId === url.id}
                      onClick={() => {
                        onSelect(url.id);
                        trigger.mutate(url.id);
                      }}
                    >
                      Scrape now
                    </Button>
                    <Button variant="text" onClick={() => onSelect(url.id)} aria-pressed={url.id === selectedId}>
                      History
                    </Button>
                    <Button variant="text" className="btn--danger" onClick={() => onDelete(url)}>
                      Remove
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error && <p className="page__error">{errorText(error)}</p>}
    </>
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

function AddUrl({
  competitorId,
  onClose,
  onAdded,
}: {
  competitorId: string;
  onClose: () => void;
  onAdded: (id: string) => void;
}) {
  const add = useAddUrl(competitorId);
  return (
    <UrlDialog
      onSave={async (input) => {
        const url = await add.mutateAsync(input);
        onAdded(url.id);
        onClose();
      }}
      onClose={onClose}
    />
  );
}

function EditInterval({ competitorId, url, onClose }: { competitorId: string; url: MonitoredUrl; onClose: () => void }) {
  const update = useUpdateUrl(competitorId);
  return (
    <IntervalDialog
      current={url.scrape_interval_minutes}
      onSave={async (minutes) => {
        await update.mutateAsync({ id: url.id, scrape_interval_minutes: minutes });
        onClose();
      }}
      onClose={onClose}
    />
  );
}

function DeleteUrl({ competitorId, url, onClose }: { competitorId: string; url: MonitoredUrl; onClose: () => void }) {
  const remove = useDeleteUrl(competitorId);
  return (
    <ConfirmDialog
      title="Stop monitoring this page?"
      confirmLabel="Remove"
      onConfirm={async () => {
        await remove.mutateAsync(url.id);
        onClose();
      }}
      onClose={onClose}
    >
      {url.url} and its scrape history will be removed.
    </ConfirmDialog>
  );
}
