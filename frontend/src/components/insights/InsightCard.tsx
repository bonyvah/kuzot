import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";

import type { Insight } from "../../api/monitoring";
import { formatDate, hostname, timeAgo } from "../../format";
import { Avatar } from "../Avatar";
import { Button } from "../Button";
import { Chip } from "../Chip";
import { pageTypeName } from "../urlForm";
import "../Dialog.css";
import "./Insights.css";

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

/** One detected change: AI headline over a short preview; the full diff opens in a dialog. */
export function InsightCard({ insight: i, hide }: InsightCardProps) {
  const [open, setOpen] = useState(false);
  const hunks = hunksOf(i);
  const preview = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);

  // The preview is height-capped; offer the dialog only when something is cut off.
  useLayoutEffect(() => {
    const el = preview.current;
    if (!el) return;
    const check = () => setClipped(el.scrollHeight > el.clientHeight + 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [hunks.length]);

  const canOpen = hunks.length > 1 || clipped;

  // Clicking anywhere on the card opens the change, except on its links and
  // buttons, inside the open dialog, or when the click ends a text selection.
  const openFromCard = (e: React.MouseEvent) => {
    if (!hunks.length || (e.target as Element).closest("a, button, dialog")) return;
    if (window.getSelection()?.toString()) return;
    setOpen(true);
  };

  return (
    <article className={`insight${hunks.length ? " insight--openable" : ""}`} onClick={openFromCard}>
      <InsightHead insight={i} hide={hide} />

      <h3 className={`insight__headline${i.headline_status === "pending" ? " insight__headline--pending" : ""}`}>
        {i.headline}
      </h3>

      {hunks.length > 0 && (
        <div ref={preview} className={`insight__preview${canOpen ? " insight__preview--clipped" : ""}`}>
          <Diff hunks={hunks.slice(0, 1)} />
        </div>
      )}

      <footer className="insight__foot">
        <PageLink url={i.url} />
        {hunks.length > 0 && (
          <button type="button" className="insight__more" onClick={() => setOpen(true)}>
            {canOpen ? `View full change${hunks.length > 1 ? ` (${hunks.length} parts)` : ""}` : "Open"}
          </button>
        )}
      </footer>

      {open && <InsightDialog insight={i} hunks={hunks} hide={hide} onClose={() => setOpen(false)} />}
    </article>
  );
}

function InsightHead({ insight: i, hide }: InsightCardProps) {
  return (
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
  );
}

function Diff({ hunks }: { hunks: Line[][] }) {
  return (
    <div className="insight__diff">
      {hunks.map((hunk, h) => (
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
  );
}

function PageLink({ url }: { url: string }) {
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" className="insight__url">
      {hostname(url)}
      {safePath(url)}
    </a>
  );
}

function InsightDialog({
  insight: i,
  hunks,
  hide,
  onClose,
}: InsightCardProps & { hunks: Line[][]; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      className="dialog insight-dialog"
      aria-labelledby={`insight-${i.id}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      // A click on the backdrop lands on the <dialog> itself.
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="insight-dialog__inner">
        <InsightHead insight={i} hide={hide} />
        <h2 id={`insight-${i.id}`} className="insight__headline">
          {i.headline}
        </h2>
        <div className="insight-dialog__body">
          <Diff hunks={hunks} />
        </div>
        <footer className="insight__foot">
          <PageLink url={i.url} />
          <Button variant="text" className="insight-dialog__close" onClick={onClose}>
            Close
          </Button>
        </footer>
      </div>
    </dialog>
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
