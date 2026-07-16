import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  test: {
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    clearMocks: true,
    css: true,
  },
});
