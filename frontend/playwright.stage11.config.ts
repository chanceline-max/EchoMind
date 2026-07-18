import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const backendDirectory = path.resolve(frontendDirectory, "..", "backend");
const backendCommand =
  process.platform === "win32"
    ? ".\\.venv\\Scripts\\python.exe -c \"from pathlib import Path; Path(r'data/playwright-stage11.db').unlink(missing_ok=True)\" && .\\.venv\\Scripts\\python.exe -m alembic upgrade head && .\\.venv\\Scripts\\python.exe ..\\scripts\\run_stage11_e2e_backend.py"
    : "./.venv/bin/python -c \"from pathlib import Path; Path('data/playwright-stage11.db').unlink(missing_ok=True)\" && ./.venv/bin/python -m alembic upgrade head && ./.venv/bin/python ../scripts/run_stage11_e2e_backend.py";
const frontendCommand = `"${process.execPath}" ./node_modules/vite/bin/vite.js --host 127.0.0.1`;

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "stage-eleven.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: [
    {
      command: backendCommand,
      cwd: backendDirectory,
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///./data/playwright-stage11.db",
        LLM_PROVIDER: "mock",
        LLM_REMOTE_ENABLED: "false",
      },
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      cwd: frontendDirectory,
      env: { ...process.env, VITE_API_BASE_URL: "http://127.0.0.1:8000" },
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
