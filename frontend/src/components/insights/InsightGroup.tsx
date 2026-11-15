import { useState } from "react";

import type { Insight } from "../../api/monitoring";
import { useInsightAction } from "../../api/queries";
import { Button } from "../Button";
import { InsightCard } from "./InsightCard";

// Changes from one competitor this close together read as one burst.
export const BURST_WINDOW_MS = 6 * 60 * 60 * 1000;

export type FeedEntry = { key: string; items: Insight[] };

/** Runs of change insights from the same competitor within the window, newest first. */
export function groupBursts(items: Insight[]): FeedEntry[] {
  const out: FeedEntry[] = [];
  for (const i of items) {
    const group = out.at(-1);
    const newest = group?.items[0];
    if (
      group &&
      newest &&
      i.kind === "change" &&
      newest.kind === "change" &&
      newest.competitor_id === i.competitor_id &&
      Date.parse(newest.detected_at) - Date.parse(i.detected_at) <= BURST_WINDOW_MS
    ) {
      group.items.push(i);
      // keyed by the oldest card: newer arrivals join at the top without remounting it
      group.key = i.id;
    } else {
      out.push({ key: i.id, items: [i] });
    }
  }
  return out;
}

const RANK = { high: 3, medium: 2, low: 1, none: 0 } as const;
const rank = (i: Insight) => (i.severity ? RANK[i.severity] : 1);

interface InsightGroupProps {
  insights: Insight[];
  hide?: { competitor?: boolean; workspace?: boolean };
  onSeen?: (id: string) => void;
}

/**
 * A burst of changes from one competitor: the most important one stands for the
 * rest until expanded. Seeing or dismissing it covers the whole group.
 */
export function InsightGroup({ insights, hide, onSeen }: InsightGroupProps) {
  const [open, setOpen] = useState(false);
  const action = useInsightAction();
  const live = insights.filter((i) => !i.state.dismissed);
  const ids = insights.map((i) => i.id);
  const name = insights[0].competitor_name;

  if (!live.length) {
    return (
      <article className="insight insight--dismissed">
        <span className="insight__dismissed-text">
          Dismissed · {insights.length} changes from {name}
        </span>
        <Button variant="text" onClick={() => action.mutate({ ids, action: "restore" })}>
          Undo
        </Button>
      </article>
    );
  }

  if (open) {
    return (
      <div className="insight-group insight-group--open">
        <div className="insight-group__bar">
          <span>
            {insights.length} changes from {name}
          </span>
          <Button variant="text" onClick={() => setOpen(false)}>
            Collapse
          </Button>
        </div>
        <ol className="feed__list">
          {insights.map((i) => (
            <li key={i.id}>
              <InsightCard insight={i} hide={hide} onSeen={onSeen} />
            </li>
          ))}
        </ol>
      </div>
    );
  }

  // the most important card leads; on a tie, the newest
  const lead = live.reduce((best, i) => (rank(i) > rank(best) ? i : best));
  const unseen = live.filter((i) => !i.state.seen);
  const others = insights.length - 1;
  return (
    <div className="insight-group">
      <InsightCard
        insight={lead}
        hide={hide}
        unread={unseen.length > 0}
        onSeen={onSeen && (() => unseen.forEach((i) => onSeen(i.id)))}
      >
        <div className="insight-group__more">
          <button type="button" className="insight__more" onClick={() => setOpen(true)}>
            +{others} more {others === 1 ? "change" : "changes"} from {name}
          </button>
          <Button variant="text" onClick={() => action.mutate({ ids, action: "dismiss" })}>
            Dismiss all
          </Button>
        </div>
      </InsightCard>
    </div>
  );
}
