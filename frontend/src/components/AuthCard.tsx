import type { FormEvent, ReactNode } from "react";

import { AuthFooter } from "./AuthFooter";
import { LogoMark } from "./Logo";
import "./AuthCard.css";

interface AuthCardProps {
  title: string;
  /** Text or controls under the title, in the left column. */
  subtitle?: ReactNode;
  /** Fields, in the right column. */
  children: ReactNode;
  /** Buttons, bottom-right. */
  actions: ReactNode;
  busy?: boolean;
  onSubmit: () => void;
}

/** Two-column sign-in card in the style of Google Accounts; stacks on narrow screens. */
export function AuthCard({ title, subtitle, children, actions, busy = false, onSubmit }: AuthCardProps) {
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!busy) onSubmit();
  };

  return (
    <main className="auth-page">
      <div className="auth-page__inner">
        <form className="auth-card" onSubmit={submit} noValidate aria-busy={busy}>
          <div className={`auth-card__progress${busy ? " auth-card__progress--on" : ""}`} aria-hidden="true" />
          <div className="auth-card__head">
            <LogoMark size={48} />
            <h1 className="auth-card__title">{title}</h1>
            {subtitle && <div className="auth-card__subtitle">{subtitle}</div>}
          </div>
          <div className="auth-card__body">
            {/* Disabled fieldset blocks edits while a request is in flight. */}
            <fieldset className="auth-card__fields" disabled={busy}>
              {children}
            </fieldset>
            <div className="auth-card__actions">{actions}</div>
          </div>
        </form>
        <AuthFooter />
      </div>
    </main>
  );
}
