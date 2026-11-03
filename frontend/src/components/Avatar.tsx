import type { Avatar as AvatarData } from "../api/monitoring";
import "./Avatar.css";

interface AvatarProps {
  name: string;
  avatar?: Partial<AvatarData>;
  size?: number;
  className?: string;
  /** Circle instead of rounded square: people, not organizations. */
  round?: boolean;
}

/** An org's or workspace's picture: uploaded image, else emoji, else its initial. */
export function Avatar({ name, avatar, size = 28, className, round }: AvatarProps) {
  const style = { width: size, height: size, fontSize: size * (avatar?.avatar_emoji ? 0.6 : 0.45) };
  const cls = `avatar-tile${round ? " avatar-tile--round" : ""}${className ? ` ${className}` : ""}`;

  if (avatar?.avatar_url) {
    return <img className={`${cls} avatar-tile--image`} src={avatar.avatar_url} alt="" style={style} />;
  }
  return (
    <span className={`${cls}${avatar?.avatar_emoji ? " avatar-tile--emoji" : ""}`} style={style} aria-hidden="true">
      {avatar?.avatar_emoji ?? name[0]?.toUpperCase()}
    </span>
  );
}
