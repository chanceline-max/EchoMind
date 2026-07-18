import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ConversationDetailPage } from "./pages/ConversationDetailPage";
import { ConversationsPage } from "./pages/ConversationsPage";
import { HomePage } from "./pages/HomePage";
import { ImportDetailPage } from "./pages/ImportDetailPage";
import { ImportPage } from "./pages/ImportPage";
import { InsightDetailPage } from "./pages/InsightDetailPage";
import { InsightsPage } from "./pages/InsightsPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "import", element: <ImportPage /> },
      { path: "imports/:sourceFileId", element: <ImportDetailPage /> },
      { path: "conversations", element: <ConversationsPage /> },
      { path: "conversations/:conversationId", element: <ConversationDetailPage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "insights/:insightId", element: <InsightDetailPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
