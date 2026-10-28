import "./Logo.css";

/** Kuzot mark, inlined from public/kuzot-logo-pack/kuzot-logo.svg. */
export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg viewBox="12 9 136 136" width={size} height={size} aria-hidden="true" focusable="false">
      <rect x="22" y="24" width="38" height="42" rx="11" fill="#3B7DF6" />
      <rect x="100" y="24" width="38" height="42" rx="11" fill="#F0524B" />
      <rect x="62" y="80" width="36" height="26" rx="8" fill="#3B7DF6" />
      <circle cx="48" cy="100" r="30" fill="#FBBC2E" />
      <circle cx="112" cy="100" r="30" fill="#2FB66B" />
      <circle cx="48" cy="100" r="15" fill="var(--logo-hole, #fff)" />
      <circle cx="112" cy="100" r="15" fill="var(--logo-hole, #fff)" />
    </svg>
  );
}

/** Mark plus wordmark, as in the app bar. */
export function Logo() {
  return (
    <span className="logo">
      <LogoMark size={32} />
      <span className="logo__word">Kuzot</span>
    </span>
  );
}
