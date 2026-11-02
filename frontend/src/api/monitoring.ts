import { api } from "./client";

// Mirrors of the backend's *Public schemas. Timestamps are ISO strings.

export interface Organization {
  id: string;
  name: string;
  slug: string;
  org_type: "personal" | "team";
  plan: string;
  created_at: string;
  updated_at: string;
}

export type MemberRole = "owner" | "admin" | "member";

export interface OrgMember {
  id: string;
  org_id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  role: MemberRole;
  joined_at: string;
}

export interface Workspace {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export const URL_TYPES = ["homepage", "pricing", "blog", "docs", "changelog"] as const;
export type UrlType = (typeof URL_TYPES)[number];

export interface MonitoredUrl {
  id: string;
  competitor_id: string;
  url: string;
  url_type: UrlType;
  scrape_interval_minutes: number | null;
  last_scraped_at: string | null;
  last_content_hash: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Competitor {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  website_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  urls: MonitoredUrl[];
}

export type JobStatus = "pending" | "running" | "success" | "failed";

export interface ScrapeJob {
  id: string;
  monitored_url_id: string;
  celery_task_id: string | null;
  status: JobStatus;
  triggered_by: "scheduler" | "manual";
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  content_changed: boolean | null;
  mongo_snapshot_id: string | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface WorkspaceInput {
  name: string;
  description: string | null;
}

export interface CompetitorInput {
  name: string;
  description: string | null;
  website_url: string | null;
}

export interface UrlInput {
  url: string;
  url_type: UrlType;
  scrape_interval_minutes: number | null;
}

export const monitoringApi = {
  // The organizations router is mounted with a trailing slash.
  organizations: () => api<Organization[]>("/organizations/"),
  createOrganization: (name: string) =>
    api<Organization>("/organizations/", { method: "POST", body: { name, org_type: "team" } }),
  renameOrganization: (id: string, name: string) =>
    api<Organization>(`/organizations/${id}`, { method: "PUT", body: { name } }),
  deleteOrganization: (id: string) => api<{ message: string }>(`/organizations/${id}`, { method: "DELETE" }),

  members: (orgId: string) => api<OrgMember[]>(`/organizations/${orgId}/members`),
  addMember: (orgId: string, email: string, role: MemberRole) =>
    api<OrgMember>(`/organizations/${orgId}/members`, { method: "POST", body: { email, role } }),
  setMemberRole: (orgId: string, userId: string, role: MemberRole) =>
    api<OrgMember>(`/organizations/${orgId}/members/${userId}`, { method: "PUT", body: { role } }),
  removeMember: (orgId: string, userId: string) =>
    api<{ message: string }>(`/organizations/${orgId}/members/${userId}`, { method: "DELETE" }),

  workspaces: (orgId: string) => api<Workspace[]>(`/organizations/${orgId}/workspaces`),
  workspace: (id: string) => api<Workspace>(`/workspaces/${id}`),
  createWorkspace: (orgId: string, body: WorkspaceInput) =>
    api<Workspace>(`/organizations/${orgId}/workspaces`, { method: "POST", body }),
  updateWorkspace: (id: string, body: WorkspaceInput) => api<Workspace>(`/workspaces/${id}`, { method: "PUT", body }),
  deleteWorkspace: (id: string) => api<{ message: string }>(`/workspaces/${id}`, { method: "DELETE" }),

  competitors: (workspaceId: string) => api<Page<Competitor>>(`/workspaces/${workspaceId}/competitors?size=100`),
  // Includes the competitor's URLs, read straight from the database.
  competitor: (id: string) => api<Competitor>(`/competitors/${id}`),
  createCompetitor: (workspaceId: string, body: CompetitorInput & { initial_urls: UrlInput[] }) =>
    api<Competitor>(`/workspaces/${workspaceId}/competitors`, { method: "POST", body }),
  updateCompetitor: (id: string, body: Partial<CompetitorInput> & { is_active?: boolean }) =>
    api<Competitor>(`/competitors/${id}`, { method: "PUT", body }),
  deleteCompetitor: (id: string) => api<{ message: string }>(`/competitors/${id}`, { method: "DELETE" }),

  addUrl: (competitorId: string, body: UrlInput) =>
    api<MonitoredUrl>(`/competitors/${competitorId}/urls`, { method: "POST", body }),
  // The backend takes these as query parameters, not a JSON body.
  updateUrl: (id: string, changes: { scrape_interval_minutes?: number; is_active?: boolean }) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(changes)) params.set(key, String(value));
    return api<MonitoredUrl>(`/monitored-urls/${id}?${params}`, { method: "PATCH" });
  },
  deleteUrl: (id: string) => api<{ message: string }>(`/monitored-urls/${id}`, { method: "DELETE" }),

  triggerScrape: (urlId: string) => api<ScrapeJob>(`/monitored-urls/${urlId}/trigger`, { method: "POST" }),
  jobs: (urlId: string, page = 1) => api<Page<ScrapeJob>>(`/monitored-urls/${urlId}/jobs?page=${page}&size=20`),
};

// ── Search & reports ─────────────────────────────────────────────────────────

export interface SearchFilters {
  competitor_ids: string[] | null;
  url_types: UrlType[] | null;
  changed_since: string | null;
}

export interface SearchHit {
  chunk_id: string;
  score: number;
  text: string;
  competitor_id: string;
  competitor_name: string;
  monitored_url_id: string;
  url: string;
  url_type: UrlType;
  snapshot_id: string;
  first_seen_at: string;
  removed_at: string | null;
  is_current: boolean;
}

export interface ReportSource extends SearchHit {
  /** The [n] the report text cites. */
  number: number;
  cited: boolean;
}

export interface Report {
  id: string;
  workspace_id: string;
  prompt: string;
  content: string;
  model: string;
  sources: ReportSource[];
  filters: Partial<SearchFilters> & { top_k?: number };
  created_by_user_id: string;
  created_at: string;
}

export type ReportSummary = Pick<Report, "id" | "prompt" | "model" | "created_by_user_id" | "created_at">;

export const intelligenceApi = {
  search: (workspaceId: string, body: SearchFilters & { query: string; scope: "current" | "all"; top_k?: number }) =>
    api<{ query: string; hits: SearchHit[] }>(`/workspaces/${workspaceId}/search`, { method: "POST", body }),

  createReport: (workspaceId: string, body: SearchFilters & { prompt: string }) =>
    api<Report>(`/workspaces/${workspaceId}/reports`, { method: "POST", body }),
  reports: (workspaceId: string, page = 1) =>
    api<Page<ReportSummary>>(`/workspaces/${workspaceId}/reports?page=${page}&size=20`),
  report: (id: string) => api<Report>(`/reports/${id}`),
};
