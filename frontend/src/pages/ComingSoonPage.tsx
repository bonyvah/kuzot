import { Link } from "react-router";

import { AuthFooter } from "../components/AuthFooter";
import { LogoMark } from "../components/Logo";
import "../components/AuthCard.css";
import "../components/Button.css";

/** Stand-in for help, legal and account-recovery pages that aren't built yet. */
export function ComingSoonPage({ title }: { title: string }) {
  return (
    <main className="auth-page">
      <div className="auth-page__inner">
        <section className="auth-card auth-card--single">
          <div className="auth-card__head">
            <LogoMark size={48} />
            <h1 className="auth-card__title">{title}</h1>
            <p className="auth-card__subtitle">This page isn't available yet.</p>
          </div>
          <div className="auth-card__actions">
            <Link to="/" className="btn btn--filled auth-card__btn-link">
              Back to Kuzot
            </Link>
          </div>
        </section>
        <AuthFooter />
      </div>
    </main>
  );
}
