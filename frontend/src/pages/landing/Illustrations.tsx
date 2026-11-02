import type { ReactNode } from "react";

import "./Illustrations.css";

// Simplified product views for the landing page: just the elements a
// section talks about, at a size where every word stays readable. The data
// is made up; the shapes mirror the real screens.

function Frame({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`ill${className ? ` ${className}` : ""}`} role="img" aria-label={label}>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

function Cite({ n, active }: { n: number; active?: boolean }) {
  return <span className={`ill-cite${active ? " ill-cite--on" : ""}`}>{n}</span>;
}

function Pill({ tone = "neutral", children }: { tone?: "neutral" | "info" | "success" | "warning"; children: ReactNode }) {
  return <span className={`ill-pill ill-pill--${tone}`}>{children}</span>;
}

/** A cited answer, with the competitors it drew on. */
export function ReportIllustration() {
  return (
    <Frame label="A report answering a pricing question, with numbered citations and the competitors it drew on" className="ill--report">
      <p className="ill-eyebrow">Report</p>
      <p className="ill-question">What changed in competitor pricing this month?</p>
      <div className="ill-answer">
        <p>
          <b>Brightdesk</b> cut its Pro plan from <s>$49</s> to <b>$39</b> a month <Cite n={1} active />
        </p>
        <p>
          <b>Orbit</b> added a free tier for up to 3 users <Cite n={3} />
        </p>
        <p>
          <b>Lumen</b> kept its prices but dropped the annual discount <Cite n={2} /> <Cite n={4} />
        </p>
      </div>
      <div className="ill-split">
        <div className="ill-source">
          <span className="ill-source__n">1</span>
          <div>
            <p className="ill-source__meta">
              Brightdesk · Pricing <Pill tone="warning">Changed Nov 2</Pill>
            </p>
            <p className="ill-source__text">
              Pro — <b>$39</b> per user / month, billed monthly
            </p>
          </div>
        </div>
        <div className="ill-bars">
          <p className="ill-bars__title">Informed by</p>
          {[
            ["Brightdesk", 100],
            ["Lumen", 66],
            ["Orbit", 33],
          ].map(([name, pct]) => (
            <div key={name} className="ill-bars__row">
              <span>{name}</span>
              <span className="ill-bars__track">
                <span style={{ width: `${pct}%` }} />
              </span>
            </div>
          ))}
        </div>
      </div>
    </Frame>
  );
}

/** Monitored pages of one competitor, some changed. */
export function PagesIllustration() {
  const rows: [string, string, string, boolean][] = [
    ["Pricing", "brightdesk.com/pricing", "Hourly", true],
    ["Changelog", "brightdesk.com/changelog", "Every 6 hours", true],
    ["Blog", "brightdesk.com/blog", "Daily", false],
    ["Docs", "docs.brightdesk.com", "Weekly", false],
  ];
  return (
    <Frame label="A competitor with four monitored pages, two of them changed" className="ill--pages">
      <div className="ill-head">
        <span className="ill-logo">B</span>
        <div>
          <p className="ill-title">Brightdesk</p>
          <p className="ill-muted">4 pages monitored</p>
        </div>
        <span className="ill-btn">Add page</span>
      </div>
      <ul className="ill-rows">
        {rows.map(([type, url, every, changed]) => (
          <li key={url} className="ill-row">
            <Pill tone="info">{type}</Pill>
            <span className="ill-row__url">{url}</span>
            <span className="ill-muted">{every}</span>
            {changed ? <Pill tone="warning">Changed</Pill> : <Pill>No change</Pill>}
          </li>
        ))}
      </ul>
    </Frame>
  );
}

/** Scrape runs for a page, newest first. */
export function HistoryIllustration() {
  return (
    <Frame label="Scrape history: one run in progress, one that found changes, one with no change" className="ill--history">
      <p className="ill-eyebrow">brightdesk.com/pricing</p>
      <ol className="ill-timeline">
        <li>
          <Pill tone="info">
            <span className="ill-pulse" />
            Running
          </Pill>
          <span>Scheduled · just now</span>
        </li>
        <li>
          <Pill tone="success">Done</Pill>
          <span>
            <b>Content changed</b> · 1 hour ago
          </span>
          <span className="ill-diff">
            <s>$49 / month</s> <b>$39 / month</b>
          </span>
        </li>
        <li>
          <Pill tone="success">Done</Pill>
          <span>No change · 2 hours ago</span>
        </li>
      </ol>
    </Frame>
  );
}

/** Search including removed text: the old price and the new one. */
export function SearchIllustration() {
  return (
    <Frame label="Search for a plan's price, showing the removed old price and the current price" className="ill--search">
      <div className="ill-search">
        <svg viewBox="0 0 24 24" width="20" height="20">
          <path
            fill="currentColor"
            d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
          />
        </svg>
        <span>Brightdesk Pro plan price</span>
      </div>
      <div className="ill-chips">
        <Pill tone="info">Pricing</Pill>
        <Pill tone="info">✓ Include removed text</Pill>
      </div>
      <div className="ill-hit ill-hit--removed">
        <p className="ill-source__meta">
          Brightdesk · Pricing <Pill tone="warning">Removed Nov 2</Pill>
        </p>
        <p>
          <s>Pro — $49 per user / month</s>
        </p>
      </div>
      <div className="ill-hit">
        <p className="ill-source__meta">
          Brightdesk · Pricing <span className="ill-muted">· Since Nov 2</span>
        </p>
        <p>
          Pro — <b>$39</b> per user / month
        </p>
      </div>
    </Frame>
  );
}

/** Members of a shared organization and their roles. */
export function MembersIllustration() {
  const people: [string, string, "Owner" | "Admin" | "Member"][] = [
    ["Aida Sultanova", "aida@company.com", "Owner"],
    ["Timur Asanov", "timur@company.com", "Admin"],
    ["Nurlan Bekov", "nurlan@company.com", "Member"],
  ];
  return (
    <Frame label="Three organization members with owner, admin and member roles" className="ill--members">
      <div className="ill-head">
        <span className="ill-logo ill-logo--emoji">🚀</span>
        <div>
          <p className="ill-title">Market Research</p>
          <p className="ill-muted">Shared organization · 3 members</p>
        </div>
        <span className="ill-btn">Add member</span>
      </div>
      <ul className="ill-rows">
        {people.map(([name, email, role]) => (
          <li key={email} className="ill-row ill-row--person">
            <span className="ill-avatar">{name[0]}</span>
            <span>
              <b>{name}</b>
              <span className="ill-muted ill-block">{email}</span>
            </span>
            <Pill tone={role === "Owner" ? "info" : "neutral"}>{role}</Pill>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

/** One claim, its citation, and the passage it points to. */
export function CitationIllustration() {
  return (
    <Frame label="A sentence in a report whose citation links to the source passage it came from" className="ill--cite">
      <p className="ill-claim">
        Orbit now has a free plan for up to 3 users <Cite n={3} active />
      </p>
      <div className="ill-link" />
      <div className="ill-source">
        <span className="ill-source__n">3</span>
        <div>
          <p className="ill-source__meta">
            Orbit · Changelog <span className="ill-muted">· Since Oct 28</span>
          </p>
          <p className="ill-source__text">
            “New: <b>Free plan</b> — up to 3 users, unlimited projects. No card needed.”
          </p>
          <p className="ill-source__url">orbit.app/changelog</p>
        </div>
      </div>
    </Frame>
  );
}
