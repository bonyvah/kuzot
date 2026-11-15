import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";

import { useAuth } from "../auth/AuthProvider";

import {
  insightsApi,
  intelligenceApi,
  monitoringApi,
  type Insight,
  type InsightAction,
  type InsightFeedPage,
  type InsightFilters,
  type InsightScope,
  type InsightState,
  type InsightTab,
  type MarkReadScope,
  type MinSeverity,
  type CompetitorInput,
  type AvatarOwner,
  type JobStatus,
  type MemberRole,
  type UrlChanges,
  type UrlInput,
  type WorkspaceInput,
} from "./monitoring";

export const keys = {
  organizations: ["organizations"] as const,
  members: (orgId: string) => ["organizations", orgId, "members"] as const,
  workspaces: (orgId: string) => ["organizations", orgId, "workspaces"] as const,
  workspace: (id: string) => ["workspaces", id] as const,
  competitors: (workspaceId: string) => ["workspaces", workspaceId, "competitors"] as const,
  competitor: (id: string) => ["competitors", id] as const,
  jobs: (urlId: string) => ["monitored-urls", urlId, "jobs"] as const,
  competitorJobs: (competitorId: string) => ["competitors", competitorId, "jobs"] as const,
};

export const isInFlight = (status: JobStatus) => status === "pending" || status === "running";

export function useOrganizations() {
  return useQuery({ queryKey: keys.organizations, queryFn: monitoringApi.organizations });
}

export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => monitoringApi.createOrganization(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.organizations, exact: true }),
  });
}

export function useRenameOrganization(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => monitoringApi.renameOrganization(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.organizations, exact: true }),
  });
}

/** Deleting an org, or leaving it, drops it from the list. */
function useForgetOrganization() {
  const qc = useQueryClient();
  return (id: string) => {
    qc.removeQueries({ queryKey: ["organizations", id] });
    return qc.invalidateQueries({ queryKey: keys.organizations, exact: true });
  };
}

export function useDeleteOrganization(id: string) {
  const forget = useForgetOrganization();
  return useMutation({ mutationFn: () => monitoringApi.deleteOrganization(id), onSuccess: () => forget(id) });
}

/** Emoji, upload and clear for an org's or a workspace's avatar. */
export function useAvatarActions(kind: AvatarOwner, id: string) {
  const qc = useQueryClient();
  const { refreshUser } = useAuth();
  // Avatars show in menus, nav, cards, headers, member lists and the feed: refresh them all.
  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: keys.organizations }),
      qc.invalidateQueries({ queryKey: ["workspaces"] }),
      qc.invalidateQueries({ queryKey: ["competitors"] }),
      qc.invalidateQueries({ queryKey: ["insights"] }),
      kind === "user" ? refreshUser() : null,
    ]);
  return {
    setEmoji: useMutation({ mutationFn: (emoji: string) => monitoringApi.setAvatarEmoji(kind, id, emoji), onSuccess: refresh }),
    upload: useMutation({ mutationFn: (file: File) => monitoringApi.uploadAvatar(kind, id, file), onSuccess: refresh }),
    clear: useMutation({ mutationFn: () => monitoringApi.clearAvatar(kind, id), onSuccess: refresh }),
  };
}

export function useMembers(orgId: string) {
  return useQuery({ queryKey: keys.members(orgId), queryFn: () => monitoringApi.members(orgId), enabled: !!orgId });
}

export function useAddMember(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: MemberRole }) => monitoringApi.addMember(orgId, email, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.members(orgId) }),
  });
}

export function useSetMemberRole(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: MemberRole }) =>
      monitoringApi.setMemberRole(orgId, userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.members(orgId) }),
  });
}

export function useRemoveMember(orgId: string, currentUserId: string) {
  const qc = useQueryClient();
  const forget = useForgetOrganization();
  return useMutation({
    mutationFn: (userId: string) => monitoringApi.removeMember(orgId, userId),
    // Leaving an org removes it from your list; removing someone else only changes members.
    onSuccess: (_, userId) =>
      userId === currentUserId ? forget(orgId) : qc.invalidateQueries({ queryKey: keys.members(orgId) }),
  });
}

export function useWorkspaces(orgId: string | undefined) {
  return useQuery({
    queryKey: keys.workspaces(orgId ?? ""),
    queryFn: () => monitoringApi.workspaces(orgId!),
    enabled: !!orgId,
  });
}

export function useWorkspace(id: string) {
  return useQuery({ queryKey: keys.workspace(id), queryFn: () => monitoringApi.workspace(id), enabled: !!id });
}

export function useCompetitors(workspaceId: string) {
  return useQuery({
    queryKey: keys.competitors(workspaceId),
    queryFn: () => monitoringApi.competitors(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useCompetitor(id: string) {
  // "" means no competitor (e.g. the sidebar off a competitor page): nothing to fetch.
  return useQuery({ queryKey: keys.competitor(id), queryFn: () => monitoringApi.competitor(id), enabled: !!id });
}

export function useCreateWorkspace(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: WorkspaceInput) => monitoringApi.createWorkspace(orgId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.workspaces(orgId) }),
  });
}

export function useUpdateWorkspace(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: WorkspaceInput) => monitoringApi.updateWorkspace(id, body),
    onSuccess: (ws) => {
      qc.setQueryData(keys.workspace(id), ws);
      return qc.invalidateQueries({ queryKey: keys.workspaces(ws.org_id) });
    },
  });
}

export function useDeleteWorkspace(id: string, orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => monitoringApi.deleteWorkspace(id),
    onSuccess: () => {
      qc.removeQueries({ queryKey: keys.workspace(id) });
      return qc.invalidateQueries({ queryKey: keys.workspaces(orgId) });
    },
  });
}

export function useCreateCompetitor(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CompetitorInput & { initial_urls: UrlInput[] }) =>
      monitoringApi.createCompetitor(workspaceId, body),
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: keys.competitors(workspaceId) }),
        // New pages each get a "now monitoring" insight.
        qc.invalidateQueries({ queryKey: ["insights"] }),
      ]),
  });
}

export function useUpdateCompetitor(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<CompetitorInput> & { is_active?: boolean }) => monitoringApi.updateCompetitor(id, body),
    onSuccess: (c) => {
      qc.setQueryData(keys.competitor(id), c);
      return qc.invalidateQueries({ queryKey: keys.competitors(c.workspace_id) });
    },
  });
}

export function useDeleteCompetitor(id: string, workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => monitoringApi.deleteCompetitor(id),
    onSuccess: () => {
      qc.removeQueries({ queryKey: keys.competitor(id) });
      return qc.invalidateQueries({ queryKey: keys.competitors(workspaceId) });
    },
  });
}

/** URL mutations all refresh the owning competitor, which carries the URL list. */
function useRefreshCompetitor(competitorId: string) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: keys.competitor(competitorId) }),
      // The workspace list shows URL counts.
      qc.invalidateQueries({ queryKey: ["workspaces"], predicate: (q) => q.queryKey[2] === "competitors" }),
    ]);
}

export function useAddUrl(competitorId: string) {
  const qc = useQueryClient();
  const refresh = useRefreshCompetitor(competitorId);
  return useMutation({
    mutationFn: (body: UrlInput) => monitoringApi.addUrl(competitorId, body),
    // The new page gets a "now monitoring" insight.
    onSuccess: () => Promise.all([refresh(), qc.invalidateQueries({ queryKey: ["insights"] })]),
  });
}

export function useUpdateUrl(competitorId: string) {
  const refresh = useRefreshCompetitor(competitorId);
  return useMutation({
    mutationFn: ({ id, ...changes }: UrlChanges & { id: string }) => monitoringApi.updateUrl(id, changes),
    onSuccess: refresh,
  });
}

export function useDeleteUrl(competitorId: string) {
  const refresh = useRefreshCompetitor(competitorId);
  return useMutation({
    mutationFn: (id: string) => monitoringApi.deleteUrl(id),
    onSuccess: refresh,
  });
}

export function useTriggerScrape(competitorId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (urlId: string) => monitoringApi.triggerScrape(urlId),
    onSuccess: (job) =>
      Promise.all([
        qc.invalidateQueries({ queryKey: keys.jobs(job.monitored_url_id) }),
        qc.invalidateQueries({ queryKey: keys.competitorJobs(competitorId) }),
        qc.invalidateQueries({ queryKey: keys.competitor(competitorId) }),
      ]),
  });
}

export const intelKeys = {
  reports: (workspaceId: string) => ["workspaces", workspaceId, "reports"] as const,
  report: (id: string) => ["reports", id] as const,
};

export function useSearch(workspaceId: string) {
  return useMutation({
    mutationFn: (body: Parameters<typeof intelligenceApi.search>[1]) => intelligenceApi.search(workspaceId, body),
  });
}

export function useReports(workspaceId: string, page: number) {
  return useQuery({
    queryKey: [...intelKeys.reports(workspaceId), page],
    queryFn: () => intelligenceApi.reports(workspaceId, page),
    placeholderData: (prev) => prev,
  });
}

export function useReport(id: string) {
  // Reports never change once written.
  return useQuery({ queryKey: intelKeys.report(id), queryFn: () => intelligenceApi.report(id), staleTime: Infinity });
}

export function useCreateReport(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof intelligenceApi.createReport>[1]) =>
      intelligenceApi.createReport(workspaceId, body),
    onSuccess: (report) => {
      qc.setQueryData(intelKeys.report(report.id), report);
      return qc.invalidateQueries({ queryKey: intelKeys.reports(workspaceId) });
    },
  });
}

// New changes are found by scheduled scrapes at any time; a minute is fresh enough.
const FEED_POLL_MS = 60_000;

// Feeds: ["insights", scope kind, scope id, filters, tab]. Counts live under "insights" too,
// so every existing ["insights"] invalidation refreshes the unread badges as well.
const insightKeys = {
  feed: (scope: InsightScope, filters: InsightFilters, tab: InsightTab) =>
    ["insights", scope.kind, scope.id, filters, tab] as const,
  counts: (orgId: string, minSeverity?: MinSeverity) => ["insights", "counts", orgId, minSeverity ?? "any"] as const,
};

export function useInsightFeed(scope: InsightScope, filters: InsightFilters, tab: InsightTab, enabled = true) {
  return useInfiniteQuery({
    queryKey: insightKeys.feed(scope, filters, tab),
    queryFn: ({ pageParam }) => insightsApi.feed(scope, filters, tab, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: FEED_POLL_MS,
    // Read state changes as the user scrolls: going back to a tab always refetches it.
    staleTime: 0,
    enabled,
  });
}

export function useInsightCounts(orgId: string | undefined, minSeverity?: MinSeverity) {
  return useQuery({
    queryKey: insightKeys.counts(orgId ?? "", minSeverity),
    queryFn: () => insightsApi.counts(orgId!, minSeverity),
    enabled: !!orgId,
    refetchInterval: FEED_POLL_MS,
  });
}

type FeedData = InfiniteData<InsightFeedPage, string | null>;

/** Change the user's state on cached insights, in every feed that holds them. */
function patchStates(qc: QueryClient, states: Map<string, Partial<InsightState>>) {
  qc.setQueriesData<FeedData>({ queryKey: ["insights"], predicate: (q) => q.queryKey[1] !== "counts" }, (data) =>
    data?.pages
      ? {
          ...data,
          pages: data.pages.map((p) => ({
            ...p,
            items: p.items.map((i) => (states.has(i.id) ? { ...i, state: { ...i.state, ...states.get(i.id) } } : i)),
          })),
        }
      : data,
  );
}

// What each action does to the state, applied before the server answers.
const OPTIMISTIC: Record<InsightAction, Partial<InsightState>> = {
  seen: { seen: true },
  open: { seen: true, opened: true },
  save: { saved: true, dismissed: false },
  unsave: { saved: false },
  dismiss: { seen: true, dismissed: true, saved: false },
  restore: { dismissed: false },
};

/** Save, dismiss, open and friends. Lists don't drop or gain cards until their next fetch. */
export function useInsightAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, action }: { ids: string[]; action: InsightAction }) => insightsApi.setStates(ids, action),
    onMutate: ({ ids, action }) => patchStates(qc, new Map(ids.map((id) => [id, OPTIMISTIC[action]]))),
    onSuccess: (updated) => patchStates(qc, new Map(updated.map((u) => [u.id, u.state]))),
    onSettled: (_data, error, { action }) =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ["insights", "counts"] }),
        // The saved tab (and on failure, everything) catches up next time it's shown.
        qc.invalidateQueries({
          queryKey: ["insights"],
          predicate: (q) => !!error || (action !== "seen" && action !== "open" && q.queryKey[4] === "saved"),
          refetchType: error ? "active" : "none",
        }),
      ]),
  });
}

/** Mark everything read: the whole organization, or one workspace or competitor. */
export function useMarkAllRead(orgId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (within: MarkReadScope) => insightsApi.markRead(orgId!, within),
    onSuccess: (counts, within) => {
      qc.setQueryData(insightKeys.counts(orgId!, within.min_severity), counts);
      // the other badges (sidebar, other filters) change too
      void qc.invalidateQueries({ queryKey: ["insights", "counts"] });
      // Mark the cached cards in scope read without refetching, so the open list doesn't jump.
      const inScope = (i: Insight) =>
        i.org_id === orgId &&
        (!within.workspace_id || i.workspace_id === within.workspace_id) &&
        (!within.competitor_id || i.competitor_id === within.competitor_id) &&
        (!within.min_severity || i.severity === "high" || (within.min_severity === "medium" && i.severity === "medium"));
      const read = new Map<string, Partial<InsightState>>();
      for (const [, data] of qc.getQueriesData<FeedData>({ queryKey: ["insights"] })) {
        data?.pages?.forEach((p) => p.items.filter(inScope).forEach((i) => read.set(i.id, { seen: true })));
      }
      patchStates(qc, read);
    },
  });
}

const SEEN_FLUSH_MS = 2_000;

/**
 * Queue of insights the user has looked at; sent in batches, and once more as the
 * page closes. Returns a function to call with an insight id when it was seen.
 */
export function useSeenQueue() {
  const qc = useQueryClient();
  const queue = useRef(new Set<string>());
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const flush = useCallback(
    (closing = false) => {
      clearTimeout(timer.current);
      timer.current = undefined;
      const ids = [...queue.current].slice(0, 100);
      ids.forEach((id) => queue.current.delete(id));
      if (!ids.length) return;
      patchStates(qc, new Map(ids.map((id) => [id, { seen: true }])));
      insightsApi
        .setStates(ids, "seen", { keepalive: closing })
        .then(() => qc.invalidateQueries({ queryKey: ["insights", "counts"] }))
        .catch(() => {
          // not saved: they stay unread and get another chance next visit
        });
      if (queue.current.size) timer.current = setTimeout(flush, SEEN_FLUSH_MS);
    },
    [qc],
  );

  useEffect(() => {
    const onHide = () => flush(true);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      flush();
    };
  }, [flush]);

  return useCallback(
    (id: string) => {
      queue.current.add(id);
      timer.current ??= setTimeout(flush, SEEN_FLUSH_MS);
    },
    [flush],
  );
}
