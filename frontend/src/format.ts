const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const absolute = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 30],
  ["month", 12],
  ["year", Infinity],
];

/** Backend timestamps are naive UTC; treat a missing offset as UTC. */
export function parseTimestamp(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

/** "3 minutes ago", "yesterday". */
export function timeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return "Never";
  let value = (parseTimestamp(iso).getTime() - now) / 1000;
  for (const [unit, size] of STEPS) {
    if (Math.abs(value) < size) return relative.format(Math.round(value), unit);
    value /= size;
  }
  return relative.format(Math.round(value), "year");
}

export function formatDate(iso: string | null): string {
  return iso ? absolute.format(parseTimestamp(iso)) : "—";
}

export function formatInterval(minutes: number | null): string {
  if (!minutes) return "Manual only";
  if (minutes % 1440 === 0) return minutes === 1440 ? "Daily" : `Every ${minutes / 1440} days`;
  if (minutes % 60 === 0) return minutes === 60 ? "Hourly" : `Every ${minutes / 60} hours`;
  return `Every ${minutes} min`;
}

/** Duration between two timestamps, e.g. "4.2 s". */
export function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const seconds = (parseTimestamp(end).getTime() - parseTimestamp(start).getTime()) / 1000;
  return seconds < 60 ? `${seconds.toFixed(1)} s` : `${Math.round(seconds / 60)} min`;
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
