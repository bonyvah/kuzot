import { useState } from "react";
import { Link } from "react-router";

import type { Insight } from "../../api/monitoring";
import { formatDate, hostname, timeAgo } from "../../format";
import { Avatar } from "../Avatar";
import { Chip } from "../Chip";
import { pageTypeName } from "../urlForm";
import "./Insights.css";

// Hunks shown before "Show all changes"
const PREVIEW = 2;

type Line = Insight["diff"][number][number];

/** Hunks to show; older insights only have whole passages, shown as removed then added. */
function hunksOf(i: Insight): Line[][] {
  if (i.diff.length) return i.diff;
  if (!i.removed.length && !i.added.length) return [];
  return [[...i.removed.map((text) => ({ op: "removed" as const, text })), ...i.added.map((text) => ({ op: "added" as const, text }))]];
}

const SIGN: Record<Line["op"], string> = { context: "", removed: "−", added: "+" };
const SIGN_LABEL: Record<Line["op"], string | undefined> = { context: undefined, removed: "Removed", added: "Added" };

interface InsightCardProps {
  insight: Insight;
  /** Hide what the surrounding page already says (e.g. the competitor on its own page). */
  hide?: { competitor?: boolean; workspace?: boolean };
}

/** One detected change: AI headline over the lines that changed. */
export function InsightCard({ insight: i, hide }: InsightCardProps) {
  const [open, setOpen] = useState(false);
  const hunks = hunksOf(i);
  const shown = open ? hunks : hunks.slice(0, PREVIEW);
  const more = hunks.length - PREVIEW;

  return (
    <article className="insight">
      <header className="insight__head">
        {!hide?.competitor && (
          <Link to={`/competitors/${i.competitor_id}`} className="insight__who">
            <Avatar
              name={i.competitor_name}
              avatar={{ avatar_emoji: i.competitor_avatar_emoji, avatar_url: i.competitor_avatar_url }}
              size={28}
            />
            {i.competitor_name}
          </Link>
        )}
        <Chip tone={i.kind === "monitoring_started" ? "success" : "info"}>{pageTypeName(i)}</Chip>
        {!hide?.workspace && (
          <Link to={`/workspaces/${i.workspace_id}`} className="insight__ws">
            {i.workspace_name}
          </Link>
        )}
        <time className="insight__time" dateTime={i.detected_at} title={formatDate(i.detected_at)}>
          {timeAgo(i.detected_at)}
        </time>
      </header>

      <h3 className={`insight__headline${i.headline_status === "pending" ? " insight__headline--pending" : ""}`}>
        {i.headline}
      </h3>

      {shown.length > 0 && (
        <div className="insight__diff">
          {shown.map((hunk, h) => (
            <div key={h} className="insight__hunk">
              {hunk.map((line, n) => (
                <p key={n} className={`insight__line insight__line--${line.op}`}>
                  <span className="insight__sign" aria-label={SIGN_LABEL[line.op]}>
                    {SIGN[line.op]}
                  </span>
                  <span>{line.text}</span>
                </p>
              ))}
            </div>
          ))}
        </div>
      )}

      <footer className="insight__foot">
        <a href={i.url} target="_blank" rel="noreferrer noopener" className="insight__url">
          {hostname(i.url)}
          {safePath(i.url)}
        </a>
        {more > 0 && (
          <button type="button" className="insight__more" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? "Show less" : `Show all changes (${more} more)`}
          </button>
        )}
      </footer>
    </article>
  );
}

function safePath(url: string): string {
  try {
    const { pathname } = new URL(url);
    return pathname === "/" ? "" : pathname;
  } catch {
    return "";
  }
}
