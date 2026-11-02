import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { errorText } from "../api/client";
import type { Report, ReportSource } from "../api/monitoring";
import { useReport, useWorkspace } from "../api/queries";
import { Button } from "../components/Button";
import { FilterChip } from "../components/FilterBar";
import { ReportMarkdown } from "../components/ReportMarkdown";
import { SourceCard } from "../components/SourceCard";
import { formatDate } from "../format";
import "./Page.css";
import "./Intelligence.css";

/** A generated report, with each [n] citation linked to the source it came from. */
export function ReportPage() {
  const { reportId = "" } = useParams();
  const report = useReport(reportId);
  const workspace = useWorkspace(report.data?.workspace_id ?? "");

  if (report.isLoading) return <p className="page page__note">Loading…</p>;
  if (report.error || !report.data) {
    return <p className="page page__error">{report.error ? errorText(report.error) : "Report not found"}</p>;
  }
  const r = report.data;
  const base = `/workspaces/${r.workspace_id}`;

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <Link to={base}>{workspace.data?.name ?? "Workspace"}</Link>
        <span aria-hidden="true">›</span>
        <Link to={`${base}/reports`}>Reports</Link>
      </nav>
      <div className="page__head">
        <div className="page__heading">
          <h1 className="page__title">{r.prompt}</h1>
          <p className="page__subtitle">
            {formatDate(r.created_at)} · {r.model}
          </p>
        </div>
      </div>
      <ReportBody report={r} />
    </div>
  );
}

function ReportBody({ report }: { report: Report }) {
  const byNumber = useMemo(() => new Map(report.sources.map((s) => [s.number, s])), [report.sources]);
  const [active, setActive] = useState<number | null>(null);
  const [competitorFilter, setCompetitorFilter] = useState<string | null>(null);
  const [showUncited, setShowUncited] = useState(false);

  const attribution = useMemo(() => attributionOf(report.sources), [report.sources]);
  const cited = report.sources.filter((s) => s.cited);
  const uncited = report.sources.filter((s) => !s.cited);
  const visible = (list: ReportSource[]) =>
    competitorFilter ? list.filter((s) => s.competitor_id === competitorFilter) : list;

  const jumpTo = (n: number) => {
    const source = byNumber.get(n);
    if (!source) return;
    setActive(n);
    setCompetitorFilter(null);
    if (!source.cited) setShowUncited(true);
    // Wait for the list to re-render with the source visible.
    requestAnimationFrame(() =>
      document.getElementById(sourceId(n))?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
  };

  return (
    <div className="report">
      <article className="report__content" aria-label="Report">
        <ReportMarkdown
          content={report.content}
          renderCitation={(n, key) => {
            const source = byNumber.get(n);
            if (!source) {
              return (
                <span key={key} className="cite cite--missing" title="Unknown source">
                  {n}
                </span>
              );
            }
            return (
              <button
                key={key}
                type="button"
                className={`cite${active === n ? " cite--active" : ""}`}
                title={`${source.competitor_name}: ${source.url}`}
                aria-label={`Source ${n}, ${source.competitor_name}`}
                onClick={() => jumpTo(n)}
              >
                {n}
              </button>
            );
          }}
        />
      </article>

      <aside className="report__aside" aria-labelledby="attribution-title">
        <h2 id="attribution-title" className="page__section-title">
          Informed by
        </h2>
        {attribution.length === 0 ? (
          <p className="page__note">The report didn't cite any source.</p>
        ) : (
          <ul className="attribution">
            {attribution.map((a) => (
              <li key={a.competitorId}>
                <button
                  type="button"
                  className={`attribution__item${competitorFilter === a.competitorId ? " attribution__item--on" : ""}`}
                  aria-pressed={competitorFilter === a.competitorId}
                  onClick={() => setCompetitorFilter((c) => (c === a.competitorId ? null : a.competitorId))}
                >
                  <span className="attribution__name">{a.name}</span>
                  <span className="attribution__count">
                    {a.cited} {a.cited === 1 ? "citation" : "citations"}
                  </span>
                  <span className="attribution__bar" aria-hidden="true">
                    <span style={{ width: `${(a.cited / attribution[0].cited) * 100}%` }} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="page__note report__counts">
          {cited.length} of {report.sources.length} retrieved passages cited.
        </p>
      </aside>

      <section className="report__sources" aria-labelledby="sources-title">
        <div className="page__section-head">
          <h2 id="sources-title" className="page__section-title">
            Cited sources
            {competitorFilter && (
              <>
                {" · "}
                <FilterChip active onClick={() => setCompetitorFilter(null)}>
                  {attribution.find((a) => a.competitorId === competitorFilter)?.name}
                </FilterChip>
              </>
            )}
          </h2>
        </div>
        <ol className="hits">
          {visible(cited).map((s) => (
            <li key={s.number}>
              <SourceCard id={sourceId(s.number)} source={s} label={`[${s.number}]`} highlighted={active === s.number} />
            </li>
          ))}
        </ol>
        {visible(cited).length === 0 && <p className="page__note">No cited sources from this competitor.</p>}

        {uncited.length > 0 && (
          <>
            <Button variant="text" aria-expanded={showUncited} onClick={() => setShowUncited((v) => !v)}>
              {showUncited ? "Hide" : "Show"} {uncited.length} retrieved but uncited
            </Button>
            {showUncited && (
              <ol className="hits">
                {visible(uncited).map((s) => (
                  <li key={s.number}>
                    <SourceCard
                      id={sourceId(s.number)}
                      source={s}
                      label={`[${s.number}]`}
                      highlighted={active === s.number}
                    />
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </section>
    </div>
  );
}

const sourceId = (n: number) => `source-${n}`;

/** Cited passages per competitor, most-cited first. */
function attributionOf(sources: ReportSource[]) {
  const counts = new Map<string, { competitorId: string; name: string; cited: number }>();
  for (const s of sources) {
    if (!s.cited) continue;
    const entry = counts.get(s.competitor_id) ?? { competitorId: s.competitor_id, name: s.competitor_name, cited: 0 };
    entry.cited += 1;
    counts.set(s.competitor_id, entry);
  }
  return [...counts.values()].sort((a, b) => b.cited - a.cited);
}
