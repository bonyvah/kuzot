import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  intelligenceApi,
  monitoringApi,
  type CompetitorInput,
  type JobStatus,
  type UrlInput,
  type WorkspaceInput,
} from "./monitoring";

export const keys = {
  organizations: ["organizations"] as const,
  workspaces: (orgId: string) => ["organizations", orgId, "workspaces"] as const,
  workspace: (id: string) => ["workspaces", id] as const,
  competitors: (workspaceId: string) => ["workspaces", workspaceId, "competitors"] as const,
  competitor: (id: string) => ["competitors", id] as const,
  jobs: (urlId: string) => ["monitored-urls", urlId, "jobs"] as const,
};

export const isInFlight = (status: JobStatus) => status === "pending" || status === "running";

export function useOrganizations() {
  return useQuery({ queryKey: keys.organizations, queryFn: monitoringApi.organizations });
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
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.competitors(workspaceId) }),
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
  const refresh = useRefreshCompetitor(competitorId);
  return useMutation({
    mutationFn: (body: UrlInput) => monitoringApi.addUrl(competitorId, body),
    onSuccess: refresh,
  });
}

export function useUpdateUrl(competitorId: string) {
  const refresh = useRefreshCompetitor(competitorId);
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; scrape_interval_minutes?: number; is_active?: boolean }) =>
      monitoringApi.updateUrl(id, changes),
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
