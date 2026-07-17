import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import "./styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Application root element was not found");
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 0, gcTime: 60_000, retry: 1 } },
});

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}><App /></QueryClientProvider>
  </StrictMode>,
);
