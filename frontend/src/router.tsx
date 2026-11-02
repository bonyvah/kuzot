import { createBrowserRouter } from "react-router";

import { RedirectIfAuthed, RequireAuth } from "./auth/guards";
import { AppShell } from "./components/AppShell";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { CompetitorPage } from "./pages/CompetitorPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SignInPage } from "./pages/SignInPage";
import { SignUpPage } from "./pages/SignUpPage";
import { WorkspaceCompetitors, WorkspaceLayout } from "./pages/WorkspacePage";
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
          { index: true, element: <DashboardPage /> },
          {
            path: "workspaces/:workspaceId",
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <WorkspaceCompetitors /> },
              { path: "search", element: <SearchPage /> },
              { path: "reports", element: <ReportsPage /> },
            ],
          },
          { path: "reports/:reportId", element: <ReportPage /> },
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
