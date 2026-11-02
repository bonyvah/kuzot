import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { errorText } from "../api/client";
import { useCompetitors, useCreateReport, useReports } from "../api/queries";
import { Button } from "../components/Button";
import { EMPTY_FILTERS, FilterBar, toApiFilters, type FilterState } from "../components/FilterBar";
import { TextArea } from "../components/TextArea";
import { formatDate, timeAgo } from "../format";
import { useCurrentWorkspace } from "./WorkspacePage";
import "./Intelligence.css";

const EXAMPLES = [
  "What changed in competitor pricing this month?",
  "Summarize new features announced in changelogs",
  "How do competitors position themselves on their homepages?",
];

/** Reports tab: ask for a new AI report, and browse earlier ones. */
export function ReportsPage() {
  const ws = useCurrentWorkspace();
  const navigate = useNavigate();
  const competitors = useCompetitors(ws.id);
  const create = useCreateReport(ws.id);
  const [prompt, setPrompt] = useState("");
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [promptError, setPromptError] = useState<string | null>(null);

  const generate = () => {
    const p = prompt.trim();
    if (!p) return setPromptError("Describe what the report should answer");
    setPromptError(null);
    create.mutate({ prompt: p, ...toApiFilters(filters) }, { onSuccess: (report) => navigate(`/reports/${report.id}`) });
  };

  return (
    <>
      <section className="page__section" aria-labelledby="new-report-title">
        <h2 id="new-report-title" className="page__section-title">
          New report
        </h2>
        <form
          className="intel-form"
          onSubmit={(e) => {
            e.preventDefault();
            generate();
          }}
        >
          <TextArea
            label="What should the report answer?"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) generate();
            }}
            error={promptError}
            maxLength={2000}
            rows={3}
          />
          <div className="intel-examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="intel-examples__item" onClick={() => setPrompt(ex)}>
                {ex}
              </button>
            ))}
          </div>
          <FilterBar competitors={competitors.data?.items ?? []} value={filters} onChange={setFilters} />
          <div className="intel-form__submit">
            {create.isPending && (
              <span className="page__note" role="status">
                Reading competitor pages and writing the report. This can take up to a minute.
              </span>
            )}
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Generating…" : "Generate report"}
            </Button>
          </div>
          {create.error && <p className="page__error">{errorText(create.error)}</p>}
        </form>
      </section>

      <PastReports workspaceId={ws.id} />
    </>
  );
}

function PastReports({ workspaceId }: { workspaceId: string }) {
  const [page, setPage] = useState(1);
  const reports = useReports(workspaceId, page);

  return (
    <section className="page__section" aria-labelledby="past-reports-title">
      <h2 id="past-reports-title" className="page__section-title">
        Past reports{reports.data ? ` (${reports.data.total})` : ""}
      </h2>
      {reports.isLoading && <p className="page__note">Loading reports…</p>}
      {reports.error && <p className="page__error">{errorText(reports.error)}</p>}
      {reports.data?.items.length === 0 && <p className="page__note">No reports yet.</p>}
      {!!reports.data?.items.length && (
        <ul className="report-list">
          {reports.data.items.map((r) => (
            <li key={r.id}>
              <Link to={`/reports/${r.id}`} className="report-list__item">
                <span className="report-list__prompt">{r.prompt}</span>
                <span className="report-list__meta" title={formatDate(r.created_at)}>
                  {timeAgo(r.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {reports.data && reports.data.pages > 1 && (
        <div className="pager">
          <Button variant="text" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Newer
          </Button>
          <span>
            Page {page} of {reports.data.pages}
          </span>
          <Button variant="text" disabled={page >= reports.data.pages} onClick={() => setPage((p) => p + 1)}>
            Older
          </Button>
        </div>
      )}
    </section>
  );
}
