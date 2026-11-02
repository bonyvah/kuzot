// Logos and portraits for the made-up companies and people in the landing
// illustrations. Drawn here so they stay sharp and need no image files.

/** Brightdesk: a sun rising over a desk. */
export function BrightdeskLogo({ size = 48 }: { size?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
      <defs>
        <linearGradient id="bd-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffb347" />
          <stop offset="1" stopColor="#f0644b" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="14" fill="url(#bd-bg)" />
      <path d="M14 30a10 10 0 0 1 20 0z" fill="#fff" />
      <g stroke="#fff" strokeWidth="2.6" strokeLinecap="round">
        <path d="M24 13.5v3.5M12.3 18.3l2.5 2.5M35.7 18.3l-2.5 2.5M8.5 30h3M36.5 30h3" />
        <path d="M10 35h28" />
      </g>
    </svg>
  );
}

/** Market Research: a magnifier over a bar chart. */
export function ResearchLogo({ size = 48 }: { size?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
      <defs>
        <linearGradient id="mr-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7c8cff" />
          <stop offset="1" stopColor="#4a3fd1" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="14" fill="url(#mr-bg)" />
      <g fill="#fff" opacity="0.6">
        <rect x="9" y="27" width="4.5" height="10" rx="1.5" />
        <rect x="15.5" y="21" width="4.5" height="16" rx="1.5" />
      </g>
      <circle cx="29" cy="21" r="7.5" fill="none" stroke="#fff" strokeWidth="3" />
      <path d="M26 23.5v-3M29 23.5v-5M32 23.5v-2" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M34.6 26.6 39 31" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" />
    </svg>
  );
}

interface Look {
  bg: string;
  skin: string;
  hair: string;
  shirt: string;
  style: "long" | "short" | "curly";
  glasses?: boolean;
  beard?: boolean;
}

export const PEOPLE = {
  aida: { bg: "#1f6f78", skin: "#e8b896", hair: "#2b1d16", shirt: "#f2f2f2", style: "long" },
  timur: { bg: "#b5651d", skin: "#d9a07a", hair: "#3a2a1f", shirt: "#26323d", style: "short", beard: true },
  nurlan: { bg: "#5b4bc4", skin: "#c98e68", hair: "#141414", shirt: "#e8eef5", style: "curly", glasses: true },
} satisfies Record<string, Look>;

export type Person = keyof typeof PEOPLE;

/** A simple head-and-shoulders portrait. */
export function Portrait({ person, size = 40 }: { person: Person; size?: number }) {
  const { bg, skin, hair, shirt, style, glasses, beard }: Look = PEOPLE[person];
  const clip = `portrait-${person}`;
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} aria-hidden="true">
      <clipPath id={clip}>
        <circle cx="20" cy="20" r="20" />
      </clipPath>
      <g clipPath={`url(#${clip})`}>
        <rect width="40" height="40" fill={bg} />
        {style === "long" && <path d="M10 18c0-8 4.5-12 10-12s10 4 10 12v14H10z" fill={hair} />}
        <path d="M5 40c1.5-7.5 7.5-11 15-11s13.5 3.5 15 11z" fill={shirt} />
        <rect x="17" y="24" width="6" height="6" rx="2" fill={skin} />
        <ellipse cx="20" cy="18" rx="7.2" ry="8.2" fill={skin} />
        {style === "long" && <path d="M12.5 17c1-6 4-8.6 7.5-8.6s6.5 2.6 7.5 8.6c-3-3.6-7.5-4.4-10-4.4-2 1.4-3.7 2.8-5 4.4z" fill={hair} />}
        {style === "short" && <path d="M12.6 17.5c-.5-6.6 3.2-9.8 7.4-9.8s8 3 7.4 9.8c-1.4-3.2-4.4-4.6-7.4-4.6s-6 1.4-7.4 4.6z" fill={hair} />}
        {style === "curly" && (
          <g fill={hair}>
            <circle cx="14" cy="13.5" r="3.4" />
            <circle cx="18" cy="10.8" r="3.6" />
            <circle cx="22.5" cy="10.8" r="3.6" />
            <circle cx="26.2" cy="13.8" r="3.3" />
            <circle cx="12.9" cy="17" r="2.2" />
            <circle cx="27.2" cy="17.2" r="2.2" />
          </g>
        )}
        <g fill="#2a1d17">
          <circle cx="16.9" cy="18.6" r="0.95" />
          <circle cx="23.1" cy="18.6" r="0.95" />
        </g>
        <path d="M17.6 22.4c1.4 1.2 3.4 1.2 4.8 0" fill="none" stroke="#8a4b3a" strokeWidth="0.9" strokeLinecap="round" />
        {beard && <path d="M13.2 19.5c.6 5.6 3.4 7.2 6.8 7.2s6.2-1.6 6.8-7.2c-1.6 2.4-3.6 3.2-6.8 3.2s-5.2-.8-6.8-3.2z" fill={hair} />}
        {glasses && (
          <g fill="none" stroke="#1d1d1d" strokeWidth="1.1">
            <circle cx="16.8" cy="18.4" r="2.5" />
            <circle cx="23.2" cy="18.4" r="2.5" />
            <path d="M19.3 18.4h1.4" />
          </g>
        )}
      </g>
    </svg>
  );
}
