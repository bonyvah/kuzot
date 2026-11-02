import { Link, useParams, useSearchParams } from "react-router";

import { errorText } from "../api/client";
import { useCompetitor } from "../api/queries";
import { JobHistory } from "../components/JobHistory";
import { pageTypeName } from "../components/urlForm";
import "./Page.css";

/** Every scrape of a competitor's pages; ?url= narrows it to one page. */
export function CompetitorHistoryPage() {
  const { competitorId = "" } = useParams();
  const [search, setSearch] = useSearchParams();
  const competitor = useCompetitor(competitorId);

  if (competitor.isLoading) return <p className="page page__note">Loading…</p>;
  if (competitor.error || !competitor.data) {
    return <p className="page page__error">{competitor.error ? errorText(competitor.error) : "Competitor not found"}</p>;
  }
  const c = competitor.data;
  const urlId = c.urls.some((u) => u.id === search.get("url")) ? search.get("url") : null;

  return (
    <div className="page">
      <nav className="page__crumbs" aria-label="Breadcrumb">
        <Link to="/workspaces">Workspaces</Link>
        <span aria-hidden="true">›</span>
        <Link to={`/competitors/${c.id}`}>{c.name}</Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page">History</span>
      </nav>
      <div className="page__head">
        <div className="page__heading">
          <h1 className="page__title">Scrape history</h1>
          <p className="page__subtitle">Every check of {c.name}'s pages, newest first.</p>
        </div>
        <div className="page__actions">
          <select
            className="role-select"
            aria-label="Page"
            value={urlId ?? ""}
            onChange={(e) => setSearch(e.target.value ? { url: e.target.value } : {}, { replace: true })}
          >
            <option value="">All pages</option>
            {c.urls.map((u) => (
              <option key={u.id} value={u.id}>
                {pageTypeName(u)} · {u.url}
              </option>
            ))}
          </select>
        </div>
      </div>
      <JobHistory key={urlId ?? "all"} competitorId={c.id} urls={c.urls} urlId={urlId} />
    </div>
  );
}
