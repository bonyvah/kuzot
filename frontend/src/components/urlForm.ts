import { URL_TYPES } from "../api/monitoring";

const URL_TYPE_LABELS: Record<(typeof URL_TYPES)[number], string> = {
  homepage: "Homepage",
  pricing: "Pricing",
  blog: "Blog",
  docs: "Docs",
  changelog: "Changelog",
};

export const urlTypeLabel = (type: (typeof URL_TYPES)[number]) => URL_TYPE_LABELS[type];

export const URL_TYPE_OPTIONS = URL_TYPES.map((t) => ({ value: t, label: URL_TYPE_LABELS[t] }));

/** Scrape intervals in minutes; "0" means manual scrapes only. */
export const INTERVAL_OPTIONS = [
  { value: "15", label: "Every 15 min" },
  { value: "60", label: "Hourly" },
  { value: "360", label: "Every 6 hours" },
  { value: "1440", label: "Daily" },
  { value: "10080", label: "Weekly" },
];

export function urlError(value: string): string | null {
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return "Use an http or https address";
    return null;
  } catch {
    return "Enter a full address, like https://example.com/pricing";
  }
}
