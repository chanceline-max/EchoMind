import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ConversationDetailPage } from "./pages/ConversationDetailPage";
import { ConversationsPage } from "./pages/ConversationsPage";
import { HomePage } from "./pages/HomePage";
import { ImportDetailPage } from "./pages/ImportDetailPage";
import { ImportPage } from "./pages/ImportPage";

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
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
