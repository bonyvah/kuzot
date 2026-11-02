import { createBrowserRouter } from "react-router";

import { RedirectIfAuthed, RequireAuth } from "./auth/guards";
import { AppShell } from "./components/AppShell";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { CompetitorPage } from "./pages/CompetitorPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OrganizationPage } from "./pages/OrganizationPage";
import { SignInPage } from "./pages/SignInPage";
import { SignUpPage } from "./pages/SignUpPage";
import { WorkspaceCompetitors, WorkspaceInsights, WorkspaceLayout } from "./pages/WorkspacePage";
import { WorkspacesPage } from "./pages/WorkspacesPage";
import { ReportPage } from "./pages/ReportPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SearchPage } from "./pages/SearchPage";

export const router = createBrowserRouter([
  {
    element: <RedirectIfAuthed />,
    children: [
      { path: "/signin", element: <SignInPage /> },
      { path: "/signup", element: <SignUpPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "workspaces", element: <WorkspacesPage /> },
          {
            path: "workspaces/:workspaceId",
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <WorkspaceInsights /> },
              { path: "competitors", element: <WorkspaceCompetitors /> },
              { path: "search", element: <SearchPage /> },
              { path: "reports", element: <ReportsPage /> },
            ],
          },
          { path: "reports/:reportId", element: <ReportPage /> },
          { path: "organization", element: <OrganizationPage /> },
          { path: "competitors/:competitorId", element: <CompetitorPage /> },
        ],
      },
    ],
  },
  // Placeholders, reachable signed in or not, until the real pages exist.
  { path: "/recovery/email", element: <ComingSoonPage title="Find your email" /> },
  { path: "/recovery/password", element: <ComingSoonPage title="Account recovery" /> },
  { path: "/help", element: <ComingSoonPage title="Help" /> },
  { path: "/privacy", element: <ComingSoonPage title="Privacy Policy" /> },
  { path: "/terms", element: <ComingSoonPage title="Terms of Service" /> },
  { path: "*", element: <NotFoundPage /> },
]);
