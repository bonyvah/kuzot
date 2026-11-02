import { api } from "./client";

// Mirrors of the backend's *Public schemas. Timestamps are ISO strings.

/** An emoji or an uploaded image; both null means "use the initial". */
export interface Avatar {
  avatar_emoji: string | null;
  avatar_url: string | null;
}

export interface Organization extends Avatar {
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

export interface Workspace extends Avatar {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export const URL_TYPES = [
  "homepage",
  "pricing",
  "blog",
  "docs",
  "changelog",
  "instagram",
  "telegram",
  "facebook",
  "x",
  "other",
] as const;
export type UrlType = (typeof URL_TYPES)[number];

export interface MonitoredUrl {
  id: string;
  competitor_id: string;
  url: string;
  url_type: UrlType;
  /** What an "other" page is, e.g. "LinkedIn". */
  label: string | null;
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
  label: string | null;
  /** null: manual scrapes only. */
  scrape_interval_minutes: number | null;
}

export type UrlChanges = Partial<Pick<UrlInput, "url_type" | "label" | "scrape_interval_minutes">> & { is_active?: boolean };

export type AvatarOwner = "organization" | "workspace";

const avatarPath = (kind: AvatarOwner, id: string) =>
  kind === "organization" ? `/organizations/${id}/avatar` : `/workspaces/${id}/avatar`;

export const monitoringApi = {
  // The organizations router is mounted with a trailing slash.
  organizations: () => api<Organization[]>("/organizations/"),
  createOrganization: (name: string) =>
    api<Organization>("/organizations/", { method: "POST", body: { name, org_type: "team" } }),
  renameOrganization: (id: string, name: string) =>
    api<Organization>(`/organizations/${id}`, { method: "PUT", body: { name } }),
  deleteOrganization: (id: string) => api<{ message: string }>(`/organizations/${id}`, { method: "DELETE" }),

  setAvatarEmoji: (kind: AvatarOwner, id: string, emoji: string) =>
    api<Organization | Workspace>(`${avatarPath(kind, id)}`, { method: "PUT", body: { emoji } }),
  uploadAvatar: (kind: AvatarOwner, id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Organization | Workspace>(`${avatarPath(kind, id)}/image`, { method: "POST", body: form });
  },
  clearAvatar: (kind: AvatarOwner, id: string) =>
    api<Organization | Workspace>(avatarPath(kind, id), { method: "DELETE" }),

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
  // Only the fields sent change; scrape_interval_minutes: null means manual only.
  updateUrl: (id: string, changes: UrlChanges) =>
    api<MonitoredUrl>(`/monitored-urls/${id}`, { method: "PATCH", body: changes }),
  deleteUrl: (id: string) => api<{ message: string }>(`/monitored-urls/${id}`, { method: "DELETE" }),

  triggerScrape: (urlId: string) => api<ScrapeJob>(`/monitored-urls/${urlId}/trigger`, { method: "POST" }),
  competitorJobs: (competitorId: string, urlId: string | null, page = 1) =>
    api<Page<ScrapeJob>>(
      `/competitors/${competitorId}/jobs?page=${page}&size=20${urlId ? `&url_id=${urlId}` : ""}`,
    ),
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

// ── Insights ─────────────────────────────────────────────────────────────────

export interface Insight {
  id: string;
  org_id: string;
  workspace_id: string;
  workspace_name: string;
  competitor_id: string;
  competitor_name: string;
  monitored_url_id: string;
  url: string;
  url_type: UrlType;
  label: string | null;
  detected_at: string;
  headline: string;
  /** "pending": the AI headline isn't written yet and `headline` is a fallback. */
  headline_status: "pending" | "done" | "failed";
  /** Changed lines with a little context, in hunks; empty for older insights. */
  diff: { op: "context" | "removed" | "added"; text: string }[][];
  added: string[];
  removed: string[];
  added_count: number;
  removed_count: number;
}

export interface InsightFeedPage {
  items: Insight[];
  next_cursor: string | null;
}

/** Whose insights: a whole organization, one workspace or one competitor. */
export type InsightScope =
  | { kind: "organization"; id: string }
  | { kind: "workspace"; id: string }
  | { kind: "competitor"; id: string };

export interface InsightFilters {
  workspaceId?: string;
  competitorId?: string;
  urlType?: UrlType;
}

const SCOPE_PATH: Record<InsightScope["kind"], string> = {
  organization: "organizations",
  workspace: "workspaces",
  competitor: "competitors",
};

export const insightsApi = {
  feed: (scope: InsightScope, filters: InsightFilters, cursor: string | null) => {
    const params = new URLSearchParams({ limit: "20" });
    if (cursor) params.set("cursor", cursor);
    if (filters.workspaceId) params.set("workspace_id", filters.workspaceId);
    if (filters.competitorId) params.set("competitor_id", filters.competitorId);
    if (filters.urlType) params.set("url_type", filters.urlType);
    return api<InsightFeedPage>(`/${SCOPE_PATH[scope.kind]}/${scope.id}/insights?${params}`);
  },
};

// ── Page discovery ───────────────────────────────────────────────────────────

export interface ChannelHint {
  url_type: UrlType;
  /** A handle (@acme) or URL; empty asks Kuzot to look for one. */
  value: string;
  label?: string | null;
}

export interface DiscoveredPage {
  url: string;
  url_type: UrlType;
  label: string | null;
  reason: string;
  source: "site" | "hint" | "search";
}

export interface Discovery {
  pages: DiscoveredPage[];
  /** Things to tell the user, e.g. that web search is off. */
  notes: string[];
  search_enabled: boolean;
}

export const discoveryApi = {
  forNewCompetitor: (
    workspaceId: string,
    body: { name: string; website: string | null; description: string | null; notes: string | null; hints: ChannelHint[] },
    signal?: AbortSignal,
  ) => api<Discovery>(`/workspaces/${workspaceId}/discover`, { method: "POST", body, signal }),

  findPage: (competitorId: string, lookingFor: string, signal?: AbortSignal) =>
    api<Discovery>(`/competitors/${competitorId}/discover`, { method: "POST", body: { looking_for: lookingFor }, signal }),
};
