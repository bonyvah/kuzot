import { URL_TYPES, type MonitoredUrl, type UrlType } from "../api/monitoring";

const URL_TYPE_LABELS: Record<UrlType, string> = {
  homepage: "Homepage",
  pricing: "Pricing",
  blog: "Blog",
  docs: "Docs",
  changelog: "Changelog",
  instagram: "Instagram",
  telegram: "Telegram",
  facebook: "Facebook",
  x: "X",
  other: "Other",
};

export const urlTypeLabel = (type: UrlType) => URL_TYPE_LABELS[type];

/** A page's type as shown to people: "Pricing", or an "other" page's own label. */
export const pageTypeName = (url: Pick<MonitoredUrl, "url_type" | "label">) =>
  url.url_type === "other" && url.label ? url.label : URL_TYPE_LABELS[url.url_type];

export const URL_TYPE_OPTIONS = URL_TYPES.map((t) => ({ value: t, label: URL_TYPE_LABELS[t] }));

// Scrape intervals in minutes: anything from 15 minutes to 30 days; daily by default.
export const MIN_INTERVAL = 15;
export const MAX_INTERVAL = 30 * 24 * 60;
export const DEFAULT_INTERVAL = 24 * 60;

export const INTERVAL_PRESETS = [
  { minutes: 60, label: "Hourly" },
  { minutes: 6 * 60, label: "Every 6 hours" },
  { minutes: 24 * 60, label: "Daily" },
  { minutes: 7 * 24 * 60, label: "Weekly" },
];

export const INTERVAL_UNITS = [
  { value: "1", label: "minutes" },
  { value: "60", label: "hours" },
  { value: "1440", label: "days" },
];

/** null is "manual only" and always valid. */
export function intervalError(minutes: number | null): string | null {
  if (minutes === null) return null;
  if (!Number.isFinite(minutes) || minutes < MIN_INTERVAL) return "Check at most every 15 minutes";
  if (minutes > MAX_INTERVAL) return "Check at least every 30 days";
  return null;
}

export function urlError(value: string): string | null {
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return "Use an http or https address";
    return null;
  } catch {
    return "Enter a full address, like https://example.com/pricing";
  }
}
