import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";

import type { Insight } from "../../api/monitoring";
import { useInsightAction } from "../../api/queries";
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

// A card counts as seen once most of it has been on screen this long.
const SEEN_AFTER_MS = 1_500;
const SEEN_VISIBLE = 0.6;

/** Calls onSeen once the element has been on screen long enough to read its headline. */
function useSeenOnScreen(ref: React.RefObject<HTMLElement | null>, active: boolean, onSeen: () => void) {
  const callback = useRef(onSeen);
  callback.current = onSeen;
  useEffect(() => {
    const el = ref.current;
    if (!el || !active) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        // A card taller than the screen can't reach the ratio; half the screen will do.
        const visible =
          entry.intersectionRatio >= SEEN_VISIBLE || entry.intersectionRect.height >= window.innerHeight / 2;
        if (visible && document.visibilityState === "visible") {
          timer ??= setTimeout(() => callback.current(), SEEN_AFTER_MS);
        } else {
          clearTimeout(timer);
          timer = undefined;
        }
      },
      { threshold: [0, 0.25, 0.5, SEEN_VISIBLE, 0.75, 1] },
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [ref, active]);
}

/** One detected change: AI headline over a short preview; the full diff opens in a dialog. */
export function InsightCard({
  insight: i,
  hide,
  onSeen,
}: InsightCardProps & { onSeen?: (id: string) => void }) {
  const action = useInsightAction();
  const card = useRef<HTMLElement>(null);
  useSeenOnScreen(card, !!onSeen && !i.state.seen && !i.state.dismissed, () => onSeen?.(i.id));

  const [open, setOpenState] = useState(false);
  const setOpen = (next: boolean) => {
    setOpenState(next);
    if (next && !i.state.opened) action.mutate({ ids: [i.id], action: "open" });
  };
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

  if (i.state.dismissed) {
    return (
      <article className="insight insight--dismissed" aria-label={`Dismissed: ${i.headline}`}>
        <span className="insight__dismissed-text">Dismissed · {i.headline}</span>
        <Button variant="text" onClick={() => action.mutate({ ids: [i.id], action: "restore" })}>
          Undo
        </Button>
      </article>
    );
  }

  const unread = !i.state.seen;
  return (
    <article
      ref={card}
      className={`insight${hunks.length ? " insight--openable" : ""}${unread ? " insight--unread" : ""}`}
      onClick={openFromCard}
    >
      {unread && <span className="insight__dot" role="img" aria-label="Unread" />}
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
        <div className="insight__actions">
          <IconButton
            label={i.state.saved ? "Remove from saved" : "Save"}
            pressed={i.state.saved}
            onClick={() => action.mutate({ ids: [i.id], action: i.state.saved ? "unsave" : "save" })}
            path={
              i.state.saved
                ? "M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"
                : "M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15-5-2.18L7 18V5h10v13z"
            }
          />
          <IconButton
            label="Dismiss"
            onClick={() => action.mutate({ ids: [i.id], action: "dismiss" })}
            path="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"
          />
          {hunks.length > 0 && (
            <button type="button" className="insight__more" onClick={() => setOpen(true)}>
              {canOpen ? `View full change${hunks.length > 1 ? ` (${hunks.length} parts)` : ""}` : "Open"}
            </button>
          )}
        </div>
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

function IconButton({
  label,
  path,
  pressed,
  onClick,
}: {
  label: string;
  path: string;
  pressed?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="insight__icon"
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      onClick={onClick}
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path fill="currentColor" d={path} />
      </svg>
    </button>
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
