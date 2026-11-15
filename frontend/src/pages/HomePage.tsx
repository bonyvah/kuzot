import { Link } from "react-router";

import { errorText } from "../api/client";
import type { InsightTab } from "../api/monitoring";
import { useWorkspaces } from "../api/queries";
import { InsightFeed } from "../components/insights/InsightFeed";
import { useOrg } from "../org/OrgProvider";
import "./Page.css";

/**
 * The organization's insights, one page per view: home is what's unread,
 * /insights/all and /insights/saved are in the sidebar under Insights.
 */
export function HomePage({ tab = "unread" }: { tab?: InsightTab }) {
  const { current, isLoading, error } = useOrg();
  const workspaces = useWorkspaces(current?.id);

  if (isLoading) return <p className="page page__note">Loading…</p>;
  if (error) return <p className="page page__error">{errorText(error)}</p>;
  if (!current) return <p className="page page__note">You don't belong to any organization yet.</p>;

  return (
    <div className="page page--feed">
      <InsightFeed
        key={`${current.id}-${tab}`}
        tab={tab}
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
