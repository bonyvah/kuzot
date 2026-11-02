import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

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
import { InsightFeed } from "../components/insights/InsightFeed";
import { AddPageDialog } from "../components/discovery/AddPageDialog";
import { IntervalDialog } from "../components/IntervalDialog";
import { pageTypeName } from "../components/urlForm";
import { formatDate, formatInterval, timeAgo } from "../format";
import "./Page.css";

type Modal =
  | { kind: "edit" }
  | { kind: "delete" }
  | { kind: "add-url" }
  | { kind: "interval"; url: MonitoredUrl }
  | { kind: "delete-url"; url: MonitoredUrl }
  | { kind: "scrape"; url: MonitoredUrl }
  | { kind: "toggle"; url: MonitoredUrl }
  | null;

/** One competitor: what changed on its pages, and the pages being monitored. */
export function CompetitorPage() {
  const { competitorId = "" } = useParams();
  const navigate = useNavigate();
  const competitor = useCompetitor(competitorId);
  const workspace = useWorkspace(competitor.data?.workspace_id ?? "");
  const update = useUpdateCompetitor(competitorId);
  const [modal, setModal] = useState<Modal>(null);
  const [queued, setQueued] = useState<MonitoredUrl | null>(null);

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
        <div className="page__section-head">
          <h2 id="insights-title" className="page__section-title">
            Insights
          </h2>
        </div>
        <InsightFeed scope={{ kind: "competitor", id: c.id }} />
      </section>

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
            urls={c.urls}
            onScrape={(url) => setModal({ kind: "scrape", url })}
            onToggle={(url) => setModal({ kind: "toggle", url })}
            onEditInterval={(url) => setModal({ kind: "interval", url })}
            onDelete={(url) => setModal({ kind: "delete-url", url })}
          />
        )}
        {queued && (
          <p className="page__note" role="status">
            Scrape of {queued.url} queued.{" "}
            <Link to={`/competitors/${c.id}/history?url=${queued.id}`}>Follow it in History</Link>
          </p>
        )}
      </section>

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
      {modal?.kind === "add-url" && <AddUrl competitorId={c.id} competitorName={c.name} onClose={close} />}
      {modal?.kind === "scrape" && (
        <ConfirmScrape
          competitorId={c.id}
          url={modal.url}
          onClose={close}
          onQueued={(url) => {
            setQueued(url);
            close();
          }}
        />
      )}
      {modal?.kind === "toggle" && <ConfirmToggle competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "interval" && <EditInterval competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "delete-url" && <DeleteUrl competitorId={c.id} url={modal.url} onClose={close} />}
    </div>
  );
}

interface UrlTableProps {
  urls: MonitoredUrl[];
  onScrape: (url: MonitoredUrl) => void;
  onToggle: (url: MonitoredUrl) => void;
  onEditInterval: (url: MonitoredUrl) => void;
  onDelete: (url: MonitoredUrl) => void;
}

function UrlTable({ urls, onScrape, onToggle, onEditInterval, onDelete }: UrlTableProps) {
  return (
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
            <tr key={url.id}>
              <td className="table__url" title={url.url}>
                <a href={url.url} target="_blank" rel="noreferrer noopener">
                  {url.url}
                </a>
              </td>
              <td>{pageTypeName(url)}</td>
              <td>
                <Button variant="text" onClick={() => onEditInterval(url)} aria-label={`Change check frequency for ${url.url}`}>
                  {formatInterval(url.scrape_interval_minutes)}
                </Button>
              </td>
              <td title={formatDate(url.last_scraped_at)}>{timeAgo(url.last_scraped_at)}</td>
              <td>
                <label className="switch">
                  {/* Controlled: the change only happens after confirming. */}
                  <input type="checkbox" checked={url.is_active} onChange={() => onToggle(url)} />
                  <span className="visually-hidden">Monitor {url.url}</span>
                </label>
              </td>
              <td>
                <div className="table__actions">
                  <Button variant="text" onClick={() => onScrape(url)}>
                    Scrape now
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
  );
}

function ConfirmScrape({
  competitorId,
  url,
  onClose,
  onQueued,
}: {
  competitorId: string;
  url: MonitoredUrl;
  onClose: () => void;
  onQueued: (url: MonitoredUrl) => void;
}) {
  const trigger = useTriggerScrape(competitorId);
  return (
    <ConfirmDialog
      danger={false}
      title="Scrape this page now?"
      confirmLabel="Scrape now"
      onConfirm={async () => {
        await trigger.mutateAsync(url.id);
        onQueued(url);
      }}
      onClose={onClose}
    >
      Kuzot will check {url.url} right away instead of waiting for its next scheduled check.
    </ConfirmDialog>
  );
}

function ConfirmToggle({ competitorId, url, onClose }: { competitorId: string; url: MonitoredUrl; onClose: () => void }) {
  const update = useUpdateUrl(competitorId);
  const pausing = url.is_active;
  return (
    <ConfirmDialog
      danger={false}
      title={pausing ? "Pause monitoring?" : "Resume monitoring?"}
      confirmLabel={pausing ? "Pause" : "Resume"}
      onConfirm={async () => {
        await update.mutateAsync({ id: url.id, is_active: !pausing });
        onClose();
      }}
      onClose={onClose}
    >
      {pausing
        ? `${url.url} won't be checked until you resume it. Its history and insights are kept.`
        : `${url.url} will be checked on its schedule again.`}
    </ConfirmDialog>
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

function AddUrl({ competitorId, competitorName, onClose }: { competitorId: string; competitorName: string; onClose: () => void }) {
  const add = useAddUrl(competitorId);
  return (
    <AddPageDialog
      competitorId={competitorId}
      competitorName={competitorName}
      onSave={async (pages) => {
        for (const page of pages) await add.mutateAsync(page);
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
