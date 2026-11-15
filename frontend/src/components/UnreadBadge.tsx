import "./UnreadBadge.css";

/** Count of unread insights next to a nav item; nothing when there are none. */
export function UnreadBadge({ count }: { count: number | undefined }) {
  if (!count) return null;
  return (
    <span className="nav-badge" aria-label={`${count} unread`}>
      {count > 99 ? "99+" : count}
    </span>
  );
}
