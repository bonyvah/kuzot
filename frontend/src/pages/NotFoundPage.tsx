import { Link } from "react-router";

import "./DashboardPage.css";

export function NotFoundPage() {
  return (
    <section className="empty">
      <h1 className="empty__title">Page not found</h1>
      <p className="empty__text">
        <Link to="/">Go to Kuzot</Link>
      </p>
    </section>
  );
}
