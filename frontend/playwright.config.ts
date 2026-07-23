import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const backendDirectory = path.resolve(frontendDirectory, "..", "backend");
const backendPort = process.env.E2E_BACKEND_PORT ?? "8000";
const frontendPort = process.env.E2E_FRONTEND_PORT ?? "5173";
const backendUrl = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendCommand =
  process.platform === "win32"
    ? `.\\.venv\\Scripts\\python.exe -c "from pathlib import Path; Path(r'data/playwright-stage10.db').unlink(missing_ok=True)" && .\\.venv\\Scripts\\python.exe -m alembic upgrade head && .\\.venv\\Scripts\\python.exe ..\\scripts\\seed_stage10_e2e.py && .\\.venv\\Scripts\\python.exe -m uvicorn echomind.main:app --host 127.0.0.1 --port ${backendPort}`
    : `./.venv/bin/python -c "from pathlib import Path; Path('data/playwright-stage10.db').unlink(missing_ok=True)" && ./.venv/bin/python -m alembic upgrade head && ./.venv/bin/python ../scripts/seed_stage10_e2e.py && ./.venv/bin/python -m uvicorn echomind.main:app --host 127.0.0.1 --port ${backendPort}`;
const frontendCommand = `"${process.execPath}" ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${frontendPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore: "stage-eleven.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: frontendUrl,
  },
  webServer: [
    {
      command: backendCommand,
      cwd: backendDirectory,
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///./data/playwright-stage10.db",
        FRONTEND_ORIGINS: JSON.stringify([frontendUrl]),
      },
      url: `${backendUrl}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      cwd: frontendDirectory,
      env: {
        ...process.env,
        VITE_API_BASE_URL: backendUrl,
      },
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
