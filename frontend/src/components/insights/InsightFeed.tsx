import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { errorText } from "../../api/client";
import type {
  Insight,
  InsightCounts,
  InsightFilters,
  InsightScope,
  InsightTab,
  MinSeverity,
  Workspace,
} from "../../api/monitoring";
import { useCompetitors, useInsightCounts, useInsightFeed, useMarkAllRead, useSeenQueue } from "../../api/queries";
import { useOrg } from "../../org/OrgProvider";
import { Button } from "../Button";
import { InsightCard } from "./InsightCard";
import { groupBursts, InsightGroup } from "./InsightGroup";
import "./Insights.css";

interface InsightFeedProps {
  scope: InsightScope;
  /** Offer a workspace filter (organization feed). */
  workspaces?: Workspace[];
  emptyAction?: React.ReactNode;
  /** Show only this tab, without the tab bar (the organization's pages, one per tab). */
  tab?: InsightTab;
}

const TITLES: Record<InsightTab, string> = { unread: "Unread", all: "All insights", saved: "Saved" };

// where a single-tab feed sends "See all insights"
const ALL_INSIGHTS_PATH = "/insights/all";

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

export function InsightFeed({ scope, workspaces, emptyAction, tab: fixedTab }: InsightFeedProps) {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<InsightFilters>({});
  const { current: org } = useOrg();
  // The Unread tab and its badge cover every unread insight, whatever importance is picked
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
  const tab = fixedTab ?? chosenTab ?? firstTab.current;
  const showAll = () => (fixedTab ? navigate(ALL_INSIGHTS_PATH) : setTab("all"));
  // importance applies to All and Saved only; it's remembered while on Unread
  const applied: InsightFilters = tab === "unread" ? { ...filters, minSeverity: undefined } : filters;

  const feed = useInsightFeed(scope, applied, tab ?? "all", !!tab);
  const filtered = !!(applied.workspaceId || applied.competitorId || applied.minSeverity);
  // Competitors to filter by: the workspace's own, or the picked workspace's in an org feed.
  const competitorSource = scope.kind === "workspace" ? scope.id : (filters.workspaceId ?? "");
  const competitors = useCompetitors(scope.kind === "competitor" ? "" : competitorSource);
  const visibleCompetitors = competitors.data?.items;

  // Keep every card shown since the tab opened, so reading the Unread tab, or
  // a refetch, doesn't pull cards out from under the reader. New ones still arrive.
  const view = JSON.stringify([scope, applied, tab]);
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

  // Bursts from one competitor fold into one card; saved cards are each kept on purpose.
  const entries = useMemo(
    () => (tab === "saved" ? items.map((i) => ({ key: i.id, items: [i] })) : groupBursts(items)),
    [items, tab],
  );
  const hide = { competitor: scope.kind === "competitor", workspace: scope.kind !== "organization" };

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
      min_severity: applied.minSeverity,
    });

  const importance = (
    <select
      aria-label="Importance"
      className="feed__select"
      value={filters.minSeverity ?? ""}
      onChange={(e) => setFilters({ ...filters, minSeverity: (e.target.value || undefined) as MinSeverity | undefined })}
    >
      <option value="">Any importance</option>
      <option value="medium">Notable and up</option>
      <option value="high">High impact only</option>
    </select>
  );

  return (
    <section className="feed" aria-label="Insights">
      <div className="feed__bar">
        {fixedTab ? (
          // Unread is the home page: no title. All and Saved name themselves, importance beside it.
          fixedTab !== "unread" && (
            <>
              <h1 className="feed__title">{TITLES[fixedTab]}</h1>
              {importance}
            </>
          )
        ) : (
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
        )}
        {!!unread && tab !== "saved" && (
          <Button variant="text" className="feed__read-all" onClick={readAll} disabled={markAllRead.isPending}>
            Mark all read
          </Button>
        )}
      </div>

      <div className="feed__filters">
        {!fixedTab && tab !== "unread" && importance}
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
        <EmptyFeed tab={tab} filtered={filtered} emptyAction={emptyAction} onShowAll={showAll} />
      )}

      <ol className="feed__list">
        {entries.map(({ key, items: group }) => (
          <li key={key}>
            {group.length > 1 ? (
              <InsightGroup insights={group} hide={hide} onSeen={markSeen} />
            ) : (
              <InsightCard insight={group[0]} hide={hide} onSeen={markSeen} />
            )}
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
              <button type="button" className="feed__link" onClick={showAll}>
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
          ? "Try other filters."
          : "Every time a monitored page changes, Kuzot puts what changed here. Add competitors and their pages to start."}
      </p>
      {!filtered && emptyAction}
    </div>
  );
}
