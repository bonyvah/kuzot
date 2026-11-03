import { useEffect, useState } from "react";

import { errorText } from "../api/client";
import type { Avatar as AvatarData, AvatarOwner } from "../api/monitoring";
import { useAvatarActions } from "../api/queries";
import { Avatar } from "./Avatar";
import { Button } from "./Button";
import "./Dialog.css";
import "./AvatarDialog.css";

const EMOJI_GROUPS: { label: string; emoji: string[] }[] = [
  { label: "Work", emoji: ["🚀", "📈", "📊", "🎯", "💼", "🏢", "🧭", "🔭", "🔍", "🧪", "⚙️", "🛠️", "💡", "📣", "🧠", "🗂️"] },
  { label: "Things", emoji: ["🚲", "🛒", "🍕", "☕", "🎧", "📦", "💳", "🏷️", "🎮", "📱", "💻", "🧩", "🎨", "📚", "🏆", "🔑"] },
  { label: "Nature", emoji: ["🔥", "⚡", "🌊", "🌱", "🌵", "🍀", "🌙", "☀️", "❄️", "🌈", "🏔️", "🌋", "🦊", "🐺", "🦅", "🐙"] },
  { label: "Symbols", emoji: ["⭐", "💎", "❤️", "💚", "💙", "💜", "🟠", "🟢", "🔷", "🔺", "✅", "♾️", "🎲", "🧿", "🪐", "👾"] },
];

const MAX_BYTES = 2 * 1024 * 1024;
const ACCEPT = "image/png,image/jpeg,image/webp,image/gif";

interface AvatarDialogProps {
  kind: AvatarOwner;
  id: string;
  name: string;
  avatar: AvatarData;
  onClose: () => void;
}

/** Pick an emoji or upload an image as the avatar of an org or workspace. */
export function AvatarDialog({ kind, id, name, avatar, onClose }: AvatarDialogProps) {
  const { setEmoji, upload, clear } = useAvatarActions(kind, id);
  const [tab, setTab] = useState<"emoji" | "upload">(avatar.avatar_url ? "upload" : "emoji");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const busy = setEmoji.isPending || upload.isPending || clear.isPending;
  const error = setEmoji.error ?? upload.error ?? clear.error;

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const choose = (picked: File | undefined) => {
    setFileError(null);
    setFile(null);
    if (!picked) return;
    if (!ACCEPT.split(",").includes(picked.type)) return setFileError("Choose a PNG, JPEG, WebP or GIF image");
    if (picked.size > MAX_BYTES) return setFileError("Images must be 2 MB or smaller");
    setFile(picked);
  };

  const done = { onSuccess: onClose };
  const current = preview ? { avatar_url: preview, avatar_emoji: null } : avatar;
  const hasAvatar = !!(avatar.avatar_emoji || avatar.avatar_url);

  return (
    <dialog
      className="dialog avatar-dialog"
      aria-labelledby="avatar-dialog-title"
      ref={(el) => {
        if (el && !el.open) el.showModal();
      }}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog__form">
        <div className="avatar-dialog__head">
          <Avatar name={name} avatar={current} size={56} round={kind === "user"} />
          <div>
            <h2 id="avatar-dialog-title" className="dialog__title">
              {kind === "user" ? "Your picture" : `Icon for ${name}`}
            </h2>
            <p className="avatar-dialog__hint">Shown in menus, cards and headers.</p>
          </div>
        </div>

        <div className="dialog-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "emoji"} onClick={() => setTab("emoji")}>
            Emoji
          </button>
          <button type="button" role="tab" aria-selected={tab === "upload"} onClick={() => setTab("upload")}>
            Upload image
          </button>
        </div>

        {tab === "emoji" ? (
          <div role="tabpanel" className="emoji-groups">
            {EMOJI_GROUPS.map((group) => (
              <section key={group.label}>
                <h3 className="emoji-groups__label">{group.label}</h3>
                <div className="emoji-grid">
                  {group.emoji.map((e) => (
                    <button
                      key={e}
                      type="button"
                      className={`emoji-grid__item${avatar.avatar_emoji === e ? " emoji-grid__item--on" : ""}`}
                      aria-label={`Use ${e}`}
                      aria-pressed={avatar.avatar_emoji === e}
                      disabled={busy}
                      onClick={() => setEmoji.mutate(e, done)}
                    >
                      {e}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div role="tabpanel" className="upload">
            <label className={`upload__drop${fileError ? " upload__drop--error" : ""}`}>
              <input type="file" accept={ACCEPT} onChange={(e) => choose(e.target.files?.[0])} disabled={busy} />
              <span className="upload__title">{file ? file.name : "Choose an image"}</span>
              <span className="upload__note">PNG, JPEG, WebP or GIF, up to 2 MB. Square images look best.</span>
            </label>
            {fileError && <p className="dialog__error">{fileError}</p>}
          </div>
        )}

        {error && (
          <p className="dialog__error" role="alert">
            {errorText(error)}
          </p>
        )}
        <div className="dialog__actions">
          {hasAvatar && (
            <Button variant="text" className="btn--danger avatar-dialog__remove" disabled={busy} onClick={() => clear.mutate(undefined, done)}>
              Remove icon
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          {tab === "upload" && (
            <Button variant="text" disabled={!file || busy} onClick={() => file && upload.mutate(file, done)}>
              {upload.isPending ? "Uploading…" : "Save"}
            </Button>
          )}
        </div>
      </div>
    </dialog>
  );
}
