import { useUser } from "../auth/AuthProvider";
import { LogoMark } from "../components/Logo";
import "./DashboardPage.css";

/** Placeholder until the week 9 dashboard lands. */
export function DashboardPage() {
  const user = useUser();

  return (
    <section className="empty">
      <LogoMark size={72} />
      <h1 className="empty__title">Welcome, {user.full_name || user.email}</h1>
      <p className="empty__text">Your competitor dashboard will show up here.</p>
    </section>
  );
}
