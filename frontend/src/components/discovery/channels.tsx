import type { Dispatch, ReactNode, SetStateAction } from "react";

import type { ChannelHint, UrlType } from "../../api/monitoring";

export type ChannelKey = "instagram" | "telegram" | "facebook" | "x" | "web";

export const CHANNELS: { key: ChannelKey; label: string; type: UrlType; placeholder: string; icon: ReactNode }[] = [
  { key: "instagram", label: "Instagram", type: "instagram", placeholder: "@handle or link", icon: <IconInstagram /> },
  { key: "telegram", label: "Telegram", type: "telegram", placeholder: "@channel or t.me link", icon: <IconTelegram /> },
  { key: "facebook", label: "Facebook", type: "facebook", placeholder: "Page name or link", icon: <IconFacebook /> },
  { key: "x", label: "X", type: "x", placeholder: "@handle or link", icon: <IconX /> },
  { key: "web", label: "Web", type: "homepage", placeholder: "Another web page, e.g. a marketplace listing", icon: <IconWeb /> },
];

export interface Custom {
  key: number;
  label: string;
  value: string;
}

export type Picked = Partial<Record<ChannelKey, string>>;

interface ChannelPickerProps {
  picked: Picked;
  onPick: Dispatch<SetStateAction<Picked>>;
  customs: Custom[];
  onCustoms: Dispatch<SetStateAction<Custom[]>>;
}

/** Channel chips; each ticked one gets an optional handle field, plus custom links under "More…". */
export function ChannelPicker({ picked, onPick: setPicked, customs, onCustoms: setCustoms }: ChannelPickerProps) {
  return (
    <>
        <div className="channels" role="group" aria-label="Channels">
          {CHANNELS.map((c) => {
            const on = picked[c.key] !== undefined;
            return (
              <button
                key={c.key}
                type="button"
                className={`channel${on ? " channel--on" : ""}`}
                aria-pressed={on}
                onClick={() =>
                  setPicked((p) => {
                    const next = { ...p };
                    if (on) delete next[c.key];
                    else next[c.key] = "";
                    return next;
                  })
                }
              >
                {c.icon}
                {c.label}
              </button>
            );
          })}
          <button
            type="button"
            className="channel"
            onClick={() => setCustoms((cs) => [...cs, { key: Date.now(), label: "", value: "" }])}
          >
            <IconPlus />
            More…
          </button>
        </div>
        <div className="channel-fields">
          {CHANNELS.filter((c) => picked[c.key] !== undefined).map((c) => (
            <label key={c.key} className="channel-field">
              <span className="channel-field__name">
                {c.icon}
                {c.label}
              </span>
              <input
                value={picked[c.key]}
                placeholder={c.key === "web" ? c.placeholder : `${c.placeholder} (optional)`}
                onChange={(e) => setPicked((p) => ({ ...p, [c.key]: e.target.value }))}
              />
            </label>
          ))}
          {customs.map((c) => (
            <div key={c.key} className="channel-field channel-field--custom">
              <input
                className="channel-field__label"
                placeholder="Channel, e.g. LinkedIn"
                aria-label="Channel name"
                value={c.label}
                onChange={(e) => setCustoms((cs) => cs.map((x) => (x.key === c.key ? { ...x, label: e.target.value } : x)))}
              />
              <input
                placeholder="Link"
                aria-label="Channel link"
                value={c.value}
                onChange={(e) => setCustoms((cs) => cs.map((x) => (x.key === c.key ? { ...x, value: e.target.value } : x)))}
              />
              <button
                type="button"
                className="channel-field__remove"
                aria-label="Remove this channel"
                onClick={() => setCustoms((cs) => cs.filter((x) => x.key !== c.key))}
              >
                ×
              </button>
            </div>
          ))}
        </div>
    </>
  );
}

/** What the user picked, as hints for discovery; empty values ask Kuzot to look. */
export function channelHints(picked: Picked, customs: Custom[]): ChannelHint[] {
  return [
    ...CHANNELS.filter((c) => picked[c.key] !== undefined && !(c.key === "web" && !picked[c.key]?.trim())).map((c) => ({
      url_type: c.type,
      value: picked[c.key]?.trim() ?? "",
    })),
    ...customs
      .filter((c) => c.value.trim())
      .map((c) => ({ url_type: "other" as const, value: c.value.trim(), label: c.label.trim() || null })),
  ];
}

// Simple channel glyphs (not brand logos).
function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}
export function IconInstagram() {
  return (
    <Glyph>
      <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.2" cy="6.8" r="0.6" fill="currentColor" />
    </Glyph>
  );
}
export function IconTelegram() {
  return (
    <Glyph>
      <path d="M21 4 3 11l6 2.5L19 7l-8 8.2V20l3.2-3.4L18 19z" />
    </Glyph>
  );
}
export function IconFacebook() {
  return (
    <Glyph>
      <path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z" />
    </Glyph>
  );
}
export function IconX() {
  return (
    <Glyph>
      <path d="M4 4h4.6L20 20h-4.6z" strokeWidth="1.5" />
      <path d="M19.5 4 13.4 11M10.6 13 4.5 20" strokeWidth="1.5" />
    </Glyph>
  );
}
export function IconWeb() {
  return (
    <Glyph>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.5 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.5-3.5-8.5s1-5.9 3.5-8.5z" />
    </Glyph>
  );
}
export function IconPlus() {
  return (
    <Glyph>
      <path d="M12 5v14M5 12h14" />
    </Glyph>
  );
}
