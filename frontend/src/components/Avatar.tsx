import type { Avatar as AvatarData } from "../api/monitoring";
import "./Avatar.css";

interface AvatarProps {
  name: string;
  avatar?: Partial<AvatarData>;
  size?: number;
  className?: string;
}

/** An org's or workspace's picture: uploaded image, else emoji, else its initial. */
export function Avatar({ name, avatar, size = 28, className }: AvatarProps) {
  const style = { width: size, height: size, fontSize: size * (avatar?.avatar_emoji ? 0.6 : 0.45) };
  const cls = `avatar-tile${className ? ` ${className}` : ""}`;

  if (avatar?.avatar_url) {
    return <img className={`${cls} avatar-tile--image`} src={avatar.avatar_url} alt="" style={style} />;
  }
  return (
    <span className={`${cls}${avatar?.avatar_emoji ? " avatar-tile--emoji" : ""}`} style={style} aria-hidden="true">
      {avatar?.avatar_emoji ?? name[0]?.toUpperCase()}
    </span>
  );
}
