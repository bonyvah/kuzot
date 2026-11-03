import { useMemo, useState } from "react";

import { errorText } from "../../api/client";
import type { InsightFilters, InsightScope, Workspace } from "../../api/monitoring";
import { useCompetitors, useInsightFeed } from "../../api/queries";
import { Button } from "../Button";
import { InsightCard } from "./InsightCard";
import "./Insights.css";

interface InsightFeedProps {
  scope: InsightScope;
  /** Offer a workspace filter (organization feed). */
  workspaces?: Workspace[];
  emptyAction?: React.ReactNode;
}

export function InsightFeed({ scope, workspaces, emptyAction }: InsightFeedProps) {
  const [filters, setFilters] = useState<InsightFilters>({});
  const feed = useInsightFeed(scope, filters);
  const items = useMemo(() => feed.data?.pages.flatMap((p) => p.items) ?? [], [feed.data]);
  const filtered = !!(filters.workspaceId || filters.competitorId);
  // Competitors to filter by: the workspace's own, or the picked workspace's in an org feed.
  const competitorSource = scope.kind === "workspace" ? scope.id : (filters.workspaceId ?? "");
  const competitors = useCompetitors(scope.kind === "competitor" ? "" : competitorSource);
  const visibleCompetitors = competitors.data?.items;

  return (
    <section className="feed" aria-label="Insights">
      <div className="feed__filters">
        {workspaces && workspaces.length > 1 && (
          <select
            aria-label="Workspace"
            value={filters.workspaceId ?? ""}
            onChange={(e) => setFilters({ ...filters, workspaceId: e.target.value || undefined, competitorId: undefined })}
          >
            <option value="">All workspaces</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        )}
        {visibleCompetitors && visibleCompetitors.length > 1 && (
          <select
            aria-label="Competitor"
            value={filters.competitorId ?? ""}
            onChange={(e) => setFilters({ ...filters, competitorId: e.target.value || undefined })}
          >
            <option value="">All competitors</option>
            {visibleCompetitors.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {feed.isLoading && <p className="page__note">Loading insights…</p>}
      {feed.error && <p className="page__error">{errorText(feed.error)}</p>}

      {feed.data && items.length === 0 && (
        <div className="blank">
          <h2 className="blank__title">{filtered ? "No insights match these filters" : "No insights yet"}</h2>
          <p>
            {filtered
              ? "Try another workspace or competitor."
              : "Every time a monitored page changes, Kuzot puts what changed here. Add competitors and their pages to start."}
          </p>
          {!filtered && emptyAction}
        </div>
      )}

      <ol className="feed__list">
        {items.map((insight) => (
          <li key={insight.id}>
            <InsightCard
              insight={insight}
              hide={{ competitor: scope.kind === "competitor", workspace: scope.kind !== "organization" }}
            />
          </li>
        ))}
      </ol>

      {feed.hasNextPage && (
        <div className="feed__more">
          <Button variant="text" disabled={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()}>
            {feed.isFetchingNextPage ? "Loading…" : "Load older insights"}
          </Button>
        </div>
      )}
    </section>
  );
}
