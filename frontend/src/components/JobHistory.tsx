import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { errorText } from "../api/client";
import { monitoringApi, type JobStatus, type MonitoredUrl } from "../api/monitoring";
import { isInFlight, keys } from "../api/queries";
import { formatDate, formatDuration, timeAgo } from "../format";
import { Button } from "./Button";
import { Chip, type ChipTone } from "./Chip";
import { pageTypeName } from "./urlForm";

const ACTIVE_POLL_MS = 2_000;
const IDLE_POLL_MS = 30_000;

const STATUS: Record<JobStatus, { label: string; tone: ChipTone }> = {
  pending: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  success: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "error" },
};

export function JobStatusChip({ status }: { status: JobStatus }) {
  const { label, tone } = STATUS[status];
  return (
    <Chip tone={tone} pulse={isInFlight(status)}>
      {label}
    </Chip>
  );
}

interface JobHistoryProps {
  competitorId: string;
  urls: MonitoredUrl[];
  /** Only this page's jobs; null for all of the competitor's pages. */
  urlId: string | null;
}

/**
 * Scrape history for a competitor's pages. Polls every 2 s while a job is
 * queued or running, otherwise every 30 s to pick up scheduled runs.
 */
export function JobHistory({ competitorId, urls, urlId }: JobHistoryProps) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const jobs = useQuery({
    queryKey: [...keys.competitorJobs(competitorId), urlId, page],
    queryFn: () => monitoringApi.competitorJobs(competitorId, urlId, page),
    placeholderData: (prev) => prev,
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => isInFlight(job.status)) ? ACTIVE_POLL_MS : IDLE_POLL_MS,
  });

  // When the last in-flight job settles, pages' "last checked" times changed.
  const inFlight = jobs.data?.items.some((job) => isInFlight(job.status)) ?? false;
  const wasInFlight = useRef(inFlight);
  useEffect(() => {
    if (wasInFlight.current && !inFlight) qc.invalidateQueries({ queryKey: keys.competitor(competitorId) });
    wasInFlight.current = inFlight;
  }, [inFlight, competitorId, qc]);

  if (jobs.isLoading) return <p className="page__note">Loading history…</p>;
  if (jobs.error) return <p className="page__error">{errorText(jobs.error)}</p>;
  if (!jobs.data?.items.length) {
    return <p className="page__note">No scrapes yet. Use “Scrape now” or wait for the next scheduled check.</p>;
  }

  const byId = new Map(urls.map((u) => [u.id, u]));
  const { items, pages } = jobs.data;
  return (
    <>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              {!urlId && <th scope="col">Page</th>}
              <th scope="col">Status</th>
              <th scope="col">Queued</th>
              <th scope="col">Trigger</th>
              <th scope="col">Duration</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {items.map((job) => {
              const url = byId.get(job.monitored_url_id);
              return (
                <tr key={job.id}>
                  {!urlId && (
                    <td className="table__url" title={url?.url}>
                      {url ? `${pageTypeName(url)} · ${url.url}` : "Removed page"}
                    </td>
                  )}
                  <td>
                    <JobStatusChip status={job.status} />
                  </td>
                  <td title={formatDate(job.created_at)}>{timeAgo(job.created_at)}</td>
                  <td>{job.triggered_by === "manual" ? "Manual" : "Scheduled"}</td>
                  <td>{formatDuration(job.started_at, job.finished_at)}</td>
                  <td className="table__url" title={job.error_message ?? undefined}>
                    {job.status === "failed"
                      ? (job.error_message ?? "Failed")
                      : job.status === "success"
                        ? job.content_changed
                          ? "Content changed"
                          : "No change"
                        : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <Button variant="text" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Newer
          </Button>
          <span>
            Page {page} of {pages}
          </span>
          <Button variant="text" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            Older
          </Button>
        </div>
      )}
    </>
  );
}
