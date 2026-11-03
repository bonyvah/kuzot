import { Link } from "react-router";

import { errorText } from "../api/client";
import { useWorkspaces } from "../api/queries";
import { InsightFeed } from "../components/insights/InsightFeed";
import { useOrg } from "../org/OrgProvider";
import "./Page.css";

/** Home: everything that changed across the current organization's workspaces. */
export function HomePage() {
  const { current, isLoading, error } = useOrg();
  const workspaces = useWorkspaces(current?.id);

  if (isLoading) return <p className="page page__note">Loading…</p>;
  if (error) return <p className="page page__error">{errorText(error)}</p>;
  if (!current) return <p className="page page__note">You don't belong to any organization yet.</p>;

  return (
    <div className="page page--feed">
      
      <InsightFeed
        key={current.id}
        scope={{ kind: "organization", id: current.id }}
        workspaces={workspaces.data}
        emptyAction={
          <Link to="/workspaces" className="btn btn--filled btn-link">
            Go to workspaces
          </Link>
        }
      />
    </div>
  );
}
