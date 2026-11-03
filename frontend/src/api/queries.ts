import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../auth/AuthProvider";

import {
  insightsApi,
  intelligenceApi,
  monitoringApi,
  type InsightFilters,
  type InsightScope,
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
  return useQuery({ queryKey: keys.competitor(id), queryFn: () => monitoringApi.competitor(id) });
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

export function useInsightFeed(scope: InsightScope, filters: InsightFilters) {
  return useInfiniteQuery({
    queryKey: ["insights", scope.kind, scope.id, filters],
    queryFn: ({ pageParam }) => insightsApi.feed(scope, filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: FEED_POLL_MS,
  });
}
