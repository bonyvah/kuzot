import { useState } from "react";
import { Link, useParams } from "react-router";

import { ApiError, errorText } from "../api/client";
import type { MonitoredUrl } from "../api/monitoring";
import { useAddUrl, useCompetitor, useDeleteUrl, useTriggerScrape, useUpdateUrl } from "../api/queries";
import { Button } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { AddPageDialog } from "../components/discovery/AddPageDialog";
import { IntervalDialog } from "../components/IntervalDialog";
import { JobHistory } from "../components/JobHistory";
import { PageTypeDialog } from "../components/PageTypeDialog";
import { pageTypeName } from "../components/urlForm";
import { formatDate, formatInterval, timeAgo } from "../format";
import "./Page.css";

type Modal =
  | { kind: "add-url" }
  | { kind: "interval"; url: MonitoredUrl }
  | { kind: "type"; url: MonitoredUrl }
  | { kind: "delete-url"; url: MonitoredUrl }
  | { kind: "scrape"; url: MonitoredUrl }
  | { kind: "scrape-all"; urls: MonitoredUrl[] }
  | { kind: "toggle"; url: MonitoredUrl }
  | null;

/** A competitor's monitored pages and their latest scrapes. */
export function CompetitorPagesPage() {
  const { competitorId = "" } = useParams();
  const competitor = useCompetitor(competitorId);
  const [modal, setModal] = useState<Modal>(null);
  const [queued, setQueued] = useState<MonitoredUrl | null>(null);
  // Pages scraped from this visit; their button stays disabled until you leave the page.
  const [scraped, setScraped] = useState<ReadonlySet<string>>(() => new Set());

  if (competitor.isLoading) return <p className="page page__note">Loading…</p>;
  if (competitor.error || !competitor.data) {
    return (
      <p className="page page__error">{competitor.error ? errorText(competitor.error) : "Competitor not found"}</p>
    );
  }
  const c = competitor.data;
  const close = () => setModal(null);
  // Active pages not already scraped from this visit.
  const toScrape = c.urls.filter((u) => u.is_active && !scraped.has(u.id));

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/workspaces">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <Link to={`/competitors/${c.id}`}>{c.name}</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">Pages</span>
      </nav>
      <div className="page__head">
        <div className="page__heading">
          <h1 className="page__title">Monitored pages</h1>
          <p className="page__subtitle">What Kuzot checks on {c.name}, and how the latest checks went.</p>
        </div>
        <div className="page__actions">
          <Button
            variant="text"
            disabled={!toScrape.length}
            onClick={() => setModal({ kind: "scrape-all", urls: toScrape })}
          >
            Scrape all
          </Button>
          <Button onClick={() => setModal({ kind: "add-url" })}>Add page</Button>
        </div>
      </div>

      <section className="page__section" aria-label="Pages">
        {c.urls.length === 0 ? (
          <div className="blank">
            <h2 className="blank__title">No pages monitored</h2>
            <p>Add a pricing page, changelog or blog to start tracking changes.</p>
            <Button onClick={() => setModal({ kind: "add-url" })}>Add page</Button>
          </div>
        ) : (
          <UrlTable
            urls={c.urls}
            scraped={scraped}
            onScrape={(url) => setModal({ kind: "scrape", url })}
            onToggle={(url) => setModal({ kind: "toggle", url })}
            onEditInterval={(url) => setModal({ kind: "interval", url })}
            onEditType={(url) => setModal({ kind: "type", url })}
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

      <section className="page__section" aria-labelledby="jobs-title">
        <div className="page__section-head">
          <h2 id="jobs-title" className="page__section-title">
            Last scrape jobs
          </h2>
          <Link to={`/competitors/${c.id}/history`} className="btn btn--text btn-link">
            View all
          </Link>
        </div>
        <JobHistory competitorId={c.id} urls={c.urls} urlId={null} limit={3} />
      </section>

      {modal?.kind === "add-url" && <AddUrl competitorId={c.id} competitorName={c.name} onClose={close} />}
      {modal?.kind === "scrape" && (
        <ConfirmScrape
          competitorId={c.id}
          url={modal.url}
          onClose={close}
          onQueued={(url) => {
            setQueued(url);
            setScraped((s) => new Set(s).add(url.id));
            close();
          }}
        />
      )}
      {modal?.kind === "scrape-all" && (
        <ConfirmScrapeAll
          competitorId={c.id}
          urls={modal.urls}
          onClose={close}
          onQueued={(ids) => {
            setQueued(null);
            setScraped((s) => new Set([...s, ...ids]));
          }}
        />
      )}
      {modal?.kind === "toggle" && <ConfirmToggle competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "interval" && <EditInterval competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "type" && <EditType competitorId={c.id} url={modal.url} onClose={close} />}
      {modal?.kind === "delete-url" && <DeleteUrl competitorId={c.id} url={modal.url} onClose={close} />}
    </div>
  );
}

interface UrlTableProps {
  urls: MonitoredUrl[];
  scraped: ReadonlySet<string>;
  onScrape: (url: MonitoredUrl) => void;
  onToggle: (url: MonitoredUrl) => void;
  onEditInterval: (url: MonitoredUrl) => void;
  onEditType: (url: MonitoredUrl) => void;
  onDelete: (url: MonitoredUrl) => void;
}

function UrlTable({ urls, scraped, onScrape, onToggle, onEditInterval, onEditType, onDelete }: UrlTableProps) {
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
              <td>
                <Button variant="text" onClick={() => onEditType(url)} aria-label={`Change page type for ${url.url}`}>
                  {pageTypeName(url)}
                </Button>
              </td>
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
                  <Button variant="text" onClick={() => onScrape(url)} disabled={scraped.has(url.id)}>
                    {scraped.has(url.id) ? "Queued" : "Scrape now"}
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

function ConfirmScrapeAll({
  competitorId,
  urls,
  onClose,
  onQueued,
}: {
  competitorId: string;
  urls: MonitoredUrl[];
  onClose: () => void;
  onQueued: (ids: string[]) => void;
}) {
  const trigger = useTriggerScrape(competitorId);
  return (
    <ConfirmDialog
      danger={false}
      title={`Scrape ${urls.length} ${urls.length === 1 ? "page" : "pages"} now?`}
      confirmLabel="Scrape all"
      onConfirm={async () => {
        const results = await Promise.allSettled(urls.map((u) => trigger.mutateAsync(u.id)));
        // 409: already being scraped, which is what we wanted anyway.
        const done = urls.filter((_, i) => {
          const r = results[i];
          return r.status === "fulfilled" || (r.reason instanceof ApiError && r.reason.status === 409);
        });
        onQueued(done.map((u) => u.id));
        const failed = urls.length - done.length;
        if (!failed) return onClose();
        // Keep the dialog open to show what went wrong; queued pages are already marked.
        const first = results.find((r) => r.status === "rejected") as PromiseRejectedResult;
        throw new Error(`${failed} of ${urls.length} couldn't be queued: ${errorText(first.reason)}`);
      }}
      onClose={onClose}
    >
      Kuzot will check every active page of this competitor right away. Paused pages are skipped.
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

function EditType({ competitorId, url, onClose }: { competitorId: string; url: MonitoredUrl; onClose: () => void }) {
  const update = useUpdateUrl(competitorId);
  return (
    <PageTypeDialog
      current={url.url_type}
      currentLabel={url.label}
      onSave={async (change) => {
        await update.mutateAsync({ id: url.id, ...change });
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
