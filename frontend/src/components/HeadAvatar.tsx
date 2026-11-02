import type { Avatar as AvatarData } from "../api/monitoring";
import { Avatar } from "./Avatar";

/** The page-header avatar; opens the icon picker for those allowed to change it. */
export function HeadAvatar({
  name,
  avatar,
  editable,
  onEdit,
}: {
  name: string;
  avatar: AvatarData;
  editable: boolean;
  onEdit: () => void;
}) {
  if (!editable) return <Avatar name={name} avatar={avatar} size={56} className="head-avatar" />;
  return (
    <button type="button" className="head-avatar" aria-label={`Change icon for ${name}`} onClick={onEdit}>
      <Avatar name={name} avatar={avatar} size={56} />
    </button>
  );
}
