import type { SearchHit } from "../api/monitoring";
import { formatDate, hostname } from "../format";
import { Chip } from "./Chip";
import { urlTypeLabel } from "./urlForm";

/** One retrieved passage and where it came from. */
interface SourceCardProps {
  source: SearchHit;
  /** Leading marker, e.g. the citation number. */
  label?: string;
  highlighted?: boolean;
  id?: string;
}

export function SourceCard({ source, label, highlighted, id }: SourceCardProps) {
  return (
    <article id={id} className={`hit${highlighted ? " hit--highlighted" : ""}`}>
      <header className="hit__head">
        {label && <span className="hit__label">{label}</span>}
        <span className="hit__competitor">{source.competitor_name}</span>
        <Chip>{urlTypeLabel(source.url_type)}</Chip>
        {source.removed_at ? (
          <Chip tone="warning">Removed {formatDate(source.removed_at)}</Chip>
        ) : (
          <span className="hit__meta">Since {formatDate(source.first_seen_at)}</span>
        )}
        <span className="hit__score" title="Similarity to your query">
          {Math.round(source.score * 100)}% match
        </span>
      </header>
      <p className={`hit__text${source.removed_at ? " hit__text--removed" : ""}`}>{source.text}</p>
      <a className="hit__url" href={source.url} target="_blank" rel="noreferrer noopener" title={source.url}>
        {hostname(source.url)}
        {safePath(source.url)}
      </a>
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
