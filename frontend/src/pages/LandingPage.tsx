import { useState } from "react";
import { Link } from "react-router";

import { Logo } from "../components/Logo";
import {
  CitationIllustration,
  HistoryIllustration,
  MembersIllustration,
  PagesIllustration,
  ReportIllustration,
  SearchIllustration,
} from "./landing/Illustrations";
import "./LandingPage.css";


const PAGE_TYPES = [
  { title: "Pricing pages", text: "Price drops, new tiers and discounts, caught the day they ship." },
  { title: "Changelogs", text: "Every feature a competitor announces, without reading their release notes." },
  { title: "Blogs and docs", text: "Positioning shifts and new content, collected in one searchable place." },
];

const FEATURES = [
  {
    badge: null,
    title: "Scraped on schedule, compared on every run",
    text: "Add the pages you care about and how often to check them. Kuzot fetches each one, renders JavaScript-heavy sites in a real browser when it has to, and keeps only what actually changed.",
    visual: <HistoryIllustration />,
  },
  {
    badge: null,
    title: "Search everything competitors have ever said",
    text: "Semantic search finds passages by meaning, not keywords. Filter by competitor, page type or date, and include text that has since been removed to see what changed.",
    visual: <SearchIllustration />,
  },
  {
    badge: "AI",
    title: "Reports that cite their sources",
    text: "Ask a question in plain words and get a written answer built only from scraped pages. Every claim links to the passage it came from, so you can check it in one click.",
    visual: <CitationIllustration />,
  },
];

const TRUST = [
  {
    title: "Each organization's data stays its own",
    text: "Every organization gets its own search index. Nothing one organization tracks can surface in another's search results or reports.",
  },
  {
    title: "Sessions that scripts can't steal",
    text: "Refresh tokens live in httpOnly, same-site cookies and rotate on every use, so a stolen token works at most once.",
  },
  {
    title: "Grounded, not generated",
    text: "Reports are written only from retrieved passages. If the pages don't answer your question, the report says so instead of guessing.",
  },
  {
    title: "Roles for every member",
    text: "Owners, admins and members. Invite colleagues by email, share workspaces, and hand over ownership safely.",
  },
];

const STEPS = [
  { title: "Add competitors", text: "Name them and paste the pages to watch: pricing, changelog, blog, docs." },
  { title: "Kuzot keeps watch", text: "Pages are checked on your schedule. Changes are detected, chunked and indexed." },
  { title: "Ask and act", text: "Search the history or generate a cited report whenever a question comes up." },
];

const FAQ = [
  {
    q: "Which sites can Kuzot track?",
    a: "Any public web page. Static pages are fetched directly; pages that build their content with JavaScript are rendered in a headless browser first.",
  },
  {
    q: "How often are pages checked?",
    a: "You choose per page: every 15 minutes, hourly, every 6 hours, daily or weekly. You can also trigger a scrape at any time.",
  },
  {
    q: "What counts as a change?",
    a: "Kuzot compares the meaningful text of each page, not its markup, so rotating ads or tracking scripts don't trigger false alarms. Removed text is kept, marked with the date it disappeared.",
  },
  {
    q: "Where do report answers come from?",
    a: "Only from passages scraped from the competitor pages you track. Each report lists its sources and marks which ones it cited.",
  },
  {
    q: "Can I use Kuzot with colleagues?",
    a: "Yes. Create a shared organization from the organization menu, add colleagues by email and give them a role. Everyone in it sees the same workspaces and reports.",
  },
];

/** Public home page for signed-out visitors. */
export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing__bar">
        <div className="landing__wrap landing__bar-inner">
          <Link to="/" aria-label="Kuzot home">
            <Logo />
          </Link>
          <nav className="landing__nav" aria-label="Sections">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="landing__bar-actions">
            <Link to="/signin" className="landing__link">
              Sign in
            </Link>
            <Link to="/signup" className="landing__btn">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main id="main">
        <section className="hero">
          <div className="landing__wrap hero__grid">
            <div>
              <h1 className="hero__title">Know what your competitors changed, before your customers do</h1>
              <p className="hero__lead">
                Kuzot watches competitor websites, detects every change and answers your questions with reports that
                cite their sources.
              </p>
              <div className="hero__cta">
                <Link to="/signup" className="landing__btn landing__btn--lg">
                  Start for free
                </Link>
                <Link to="/signin" className="landing__btn landing__btn--lg landing__btn--tonal">
                  Sign in
                </Link>
              </div>
            </div>
            <ReportIllustration />
          </div>
        </section>

        <section className="landing__section" id="features" aria-labelledby="watch-title">
          <div className="landing__wrap">
            <div className="landing__wide">
              <PagesIllustration />
            </div>
            <div className="intro">
              <h2 id="watch-title" className="landing__h2">
                Every page that matters, watched for you
              </h2>
              <p className="landing__lead">
                Point Kuzot at the pages your competitors update most and stop checking them by hand.
              </p>
            </div>
            <div className="trio">
              {PAGE_TYPES.map((t) => (
                <div key={t.title} className="trio__item">
                  <h3>{t.title}</h3>
                  <p>{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {FEATURES.map((f, i) => (
          <section key={f.title} className="landing__section feature" aria-labelledby={`feature-${i}`}>
            <div className={`landing__wrap feature__row${i % 2 ? " feature__row--flip" : ""}`}>
              <div className="feature__copy">
                {f.badge && <span className="badge">{f.badge}</span>}
                <h2 id={`feature-${i}`} className="landing__h2">
                  {f.title}
                </h2>
                <p className="landing__lead">{f.text}</p>
              </div>
              {f.visual}
            </div>
          </section>
        ))}

        <section className="landing__section landing__section--tint" aria-labelledby="trust-title">
          <div className="landing__wrap">
            <h2 id="trust-title" className="landing__h2 landing__center">
              Built for organizations that share sensitive research
            </h2>
            <div className="cards">
              {TRUST.map((t) => (
                <div key={t.title} className="cards__item">
                  <h3>{t.title}</h3>
                  <p>{t.text}</p>
                </div>
              ))}
            </div>
            <div className="members-visual">
              <MembersIllustration />
            </div>
          </div>
        </section>

        <section className="landing__section" id="how" aria-labelledby="how-title">
          <div className="landing__wrap">
            <h2 id="how-title" className="landing__h2 landing__center">
              Up and running in three steps
            </h2>
            <ol className="steps">
              {STEPS.map((s, i) => (
                <li key={s.title} className="steps__item">
                  <span className="steps__num" aria-hidden="true">
                    {i + 1}
                  </span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="landing__section" id="faq" aria-labelledby="faq-title">
          <div className="landing__wrap landing__narrow">
            <Faq />
          </div>
        </section>

        <section className="landing__section final">
          <div className="landing__wrap landing__center">
            <h2 className="landing__h2">Stop refreshing competitor websites</h2>
            <p className="landing__lead">Set up your first workspace in a couple of minutes.</p>
            <div className="hero__cta hero__cta--center">
              <Link to="/signup" className="landing__btn landing__btn--lg">
                Start for free
              </Link>
              <Link to="/signin" className="landing__btn landing__btn--lg landing__btn--tonal">
                Sign in
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing__footer">
        <div className="landing__wrap landing__footer-inner">
          <Logo />
          <nav aria-label="Footer">
            <Link to="/help">Help</Link>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
          </nav>
          <span>© {new Date().getFullYear()} Kuzot</span>
        </div>
      </footer>
    </div>
  );
}

function Faq() {
  const [open, setOpen] = useState<boolean[]>(() => FAQ.map(() => false));
  const allOpen = open.every(Boolean);

  return (
    <>
      <div className="faq__head">
        <h2 id="faq-title" className="landing__h2">
          Frequently asked questions
        </h2>
        <button type="button" className="landing__link" onClick={() => setOpen(FAQ.map(() => !allOpen))}>
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <div className="faq">
        {FAQ.map((item, i) => (
          <details
            key={item.q}
            className="faq__item"
            open={open[i]}
            onToggle={(e) => {
              const isOpen = e.currentTarget.open;
              setOpen((prev) => (prev[i] === isOpen ? prev : prev.map((v, j) => (j === i ? isOpen : v))));
            }}
          >
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
    </>
  );
}
