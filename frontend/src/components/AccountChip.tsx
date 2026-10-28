import "./AccountChip.css";

/** Email pill shown on later steps; clicking it goes back to change the email. */
export function AccountChip({ email, onClick }: { email: string; onClick: () => void }) {
  return (
    <button type="button" className="account-chip" onClick={onClick} aria-label={`${email}. Use a different email`}>
      <span className="account-chip__avatar" aria-hidden="true">
        {email[0]?.toUpperCase()}
      </span>
      <span className="account-chip__email">{email}</span>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path fill="currentColor" d="M7 10l5 5 5-5z" />
      </svg>
    </button>
  );
}
