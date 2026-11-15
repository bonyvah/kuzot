import { useEffect, useMemo, useRef, useState } from "react";

import { errorText } from "../../api/client";
import type { Insight, InsightCounts, InsightFilters, InsightScope, InsightTab, Workspace } from "../../api/monitoring";
import { useCompetitors, useInsightCounts, useInsightFeed, useMarkAllRead, useSeenQueue } from "../../api/queries";
import { useOrg } from "../../org/OrgProvider";
import { Button } from "../Button";
import { InsightCard } from "./InsightCard";
import "./Insights.css";

interface InsightFeedProps {
  scope: InsightScope;
  /** Offer a workspace filter (organization feed). */
  workspaces?: Workspace[];
  emptyAction?: React.ReactNode;
}

const TABS: { id: InsightTab; label: string }[] = [
  { id: "unread", label: "Unread" },
  { id: "all", label: "All" },
  { id: "saved", label: "Saved" },
];

/** Unread insights within the scope and filters shown. */
function unreadIn(counts: InsightCounts | undefined, scope: InsightScope, filters: InsightFilters): number | undefined {
  if (!counts) return undefined;
  const competitor = scope.kind === "competitor" ? scope.id : filters.competitorId;
  const workspace = scope.kind === "workspace" ? scope.id : filters.workspaceId;
  if (competitor) return counts.competitors[competitor] ?? 0;
  if (workspace) return counts.workspaces[workspace] ?? 0;
  return counts.total;
}

const newestFirst = (a: Insight, b: Insight) =>
  b.detected_at.localeCompare(a.detected_at) || b.id.localeCompare(a.id);

export function InsightFeed({ scope, workspaces, emptyAction }: InsightFeedProps) {
  const [filters, setFilters] = useState<InsightFilters>({});
  const { current: org } = useOrg();
  const counts = useInsightCounts(org?.id);
  const unread = unreadIn(counts.data, scope, filters);
  const markAllRead = useMarkAllRead(org?.id);
  const markSeen = useSeenQueue();

  // Open on Unread when there's something unread, otherwise on All. Decided
  // once, so a new insight arriving later doesn't switch tabs under the reader.
  const [chosenTab, setTab] = useState<InsightTab | null>(null);
  const countsSettled = !org?.id || counts.isSuccess || counts.isError;
  const firstTab = useRef<InsightTab>(undefined);
  if (!firstTab.current && countsSettled) firstTab.current = unread ? "unread" : "all";
  const tab = chosenTab ?? firstTab.current;

  const feed = useInsightFeed(scope, filters, tab ?? "all", !!tab);
  const filtered = !!(filters.workspaceId || filters.competitorId);
  // Competitors to filter by: the workspace's own, or the picked workspace's in an org feed.
  const competitorSource = scope.kind === "workspace" ? scope.id : (filters.workspaceId ?? "");
  const competitors = useCompetitors(scope.kind === "competitor" ? "" : competitorSource);
  const visibleCompetitors = competitors.data?.items;

  // Keep every card shown since the tab opened, so reading the Unread tab, or
  // a refetch, doesn't pull cards out from under the reader. New ones still arrive.
  const view = JSON.stringify([scope, filters, tab]);
  const shown = useRef({ view, openedAt: Date.now(), cards: new Map<string, Insight>() });
  if (shown.current.view !== view) shown.current = { view, openedAt: Date.now(), cards: new Map() };
  const { data, dataUpdatedAt } = feed;
  const items = useMemo(() => {
    const fresh = data?.pages.flatMap((p) => p.items) ?? [];
    // Cached data from an earlier visit shows until the refetch lands, but doesn't
    // stick: on Unread it holds cards read since.
    if (dataUpdatedAt < shown.current.openedAt) return fresh;
    const cards = shown.current.cards;
    fresh.forEach((i) => cards.set(i.id, i));
    return [...cards.values()].sort(newestFirst);
  }, [data, dataUpdatedAt, view]);

  // Infinite scroll: load older insights when the end of the list comes near.
  const sentinel = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage } = feed;
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage || isFetchingNextPage || isFetchNextPageError) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) fetchNextPage();
      },
      { rootMargin: "800px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage]);

  const readAll = () =>
    markAllRead.mutate({
      workspace_id: scope.kind === "workspace" ? scope.id : filters.workspaceId,
      competitor_id: scope.kind === "competitor" ? scope.id : filters.competitorId,
    });

  return (
    <section className="feed" aria-label="Insights">
      <div className="feed__bar">
        <div className="feed__tabs" role="tablist" aria-label="Show">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className="feed__tab"
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.id === "unread" && !!unread && <span className="feed__count">{unread > 99 ? "99+" : unread}</span>}
            </button>
          ))}
        </div>
        {!!unread && (
          <Button variant="text" className="feed__read-all" onClick={readAll} disabled={markAllRead.isPending}>
            Mark all read
          </Button>
        )}
      </div>

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

      {(!tab || feed.isLoading) && <p className="page__note">Loading insights…</p>}
      {feed.error && <p className="page__error">{errorText(feed.error)}</p>}
      {markAllRead.error && <p className="page__error">{errorText(markAllRead.error)}</p>}

      {tab && feed.data && items.length === 0 && (
        <EmptyFeed tab={tab}filtered={filtered} emptyAction={emptyAction} onShowAll={() => setTab("all")} />
      )}

      <ol className="feed__list">
        {items.map((insight) => (
          <li key={insight.id}>
            <InsightCard
              insight={insight}
              hide={{ competitor: scope.kind === "competitor", workspace: scope.kind !== "organization" }}
              onSeen={markSeen}
            />
          </li>
        ))}
      </ol>

      {hasNextPage && (
        <div ref={sentinel} className="feed__more" role="status">
          {isFetchNextPageError ? (
            // Stop auto-loading after a failure; let the user retry.
            <Button variant="text" onClick={() => fetchNextPage()}>
              Couldn't load more. Try again
            </Button>
          ) : (
            <span className="page__note">{isFetchingNextPage ? "Loading older insights…" : ""}</span>
          )}
        </div>
      )}
      {feed.data && items.length > 0 && !hasNextPage && (
        <p className="feed__end page__note">
          {tab === "unread" ? (
            <>
              You're all caught up.{" "}
              <button type="button" className="feed__link" onClick={() => setTab("all")}>
                See all insights
              </button>
            </>
          ) : (
            "That's everything."
          )}
        </p>
      )}
    </section>
  );
}

function EmptyFeed({
  tab,
  filtered,
  emptyAction,
  onShowAll,
}: {
  tab: InsightTab;
  filtered: boolean;
  emptyAction?: React.ReactNode;
  onShowAll: () => void;
}) {
  if (tab === "unread") {
    return (
      <div className="blank">
        <h2 className="blank__title">You're all caught up</h2>
        <p>New changes on your competitors' pages show up here until you've seen them.</p>
        <Button variant="text" onClick={onShowAll}>
          See all insights
        </Button>
      </div>
    );
  }
  if (tab === "saved") {
    return (
      <div className="blank">
        <h2 className="blank__title">Nothing saved yet</h2>
        <p>Save an insight to keep it here for later.</p>
      </div>
    );
  }
  return (
    <div className="blank">
      <h2 className="blank__title">{filtered ? "No insights match these filters" : "No insights yet"}</h2>
      <p>
        {filtered
          ? "Try another workspace or competitor."
          : "Every time a monitored page changes, Kuzot puts what changed here. Add competitors and their pages to start."}
      </p>
      {!filtered && emptyAction}
    </div>
  );
}
