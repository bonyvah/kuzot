import { Link } from "react-router";

import "./AuthFooter.css";

export function AuthFooter() {
  return (
    <footer className="auth-footer">
      <nav className="auth-footer__links" aria-label="Legal and help">
        <Link to="/help">Help</Link>
        <Link to="/privacy">Privacy</Link>
        <Link to="/terms">Terms</Link>
      </nav>
    </footer>
  );
}
