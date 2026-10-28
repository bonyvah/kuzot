import { LogoMark } from "./Logo";
import "./Splash.css";

/** Shown while the stored session is being restored. */
export function Splash() {
  return (
    <div className="splash" role="status">
      <LogoMark size={56} />
      <span className="visually-hidden">Loading</span>
    </div>
  );
}
