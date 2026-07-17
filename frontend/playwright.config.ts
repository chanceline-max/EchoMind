import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const backendDirectory = path.resolve(frontendDirectory, "..", "backend");
const backendCommand =
  process.platform === "win32"
    ? ".\\.venv\\Scripts\\python.exe -c \"from pathlib import Path; Path(r'data/playwright-stage5.db').unlink(missing_ok=True)\" && .\\.venv\\Scripts\\python.exe -m alembic upgrade head && .\\.venv\\Scripts\\python.exe -m uvicorn echomind.main:app --host 127.0.0.1 --port 8000"
    : "./.venv/bin/python -c \"from pathlib import Path; Path('data/playwright-stage5.db').unlink(missing_ok=True)\" && ./.venv/bin/python -m alembic upgrade head && ./.venv/bin/python -m uvicorn echomind.main:app --host 127.0.0.1 --port 8000";
const frontendCommand = `"${process.execPath}" ./node_modules/vite/bin/vite.js --host 127.0.0.1`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
  },
  webServer: [
    {
      command: backendCommand,
      cwd: backendDirectory,
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///./data/playwright-stage5.db",
      },
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      cwd: frontendDirectory,
      env: {
        ...process.env,
        VITE_API_BASE_URL: "http://127.0.0.1:8000",
      },
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
