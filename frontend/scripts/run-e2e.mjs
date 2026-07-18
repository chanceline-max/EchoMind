import { rm } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const frontendRoot = path.resolve(import.meta.dirname, "..");
const playwrightCli = path.join(frontendRoot, "node_modules", "@playwright", "test", "cli.js");
const result = spawnSync(process.execPath, [playwrightCli, "test"], {
  cwd: frontendRoot,
  env: process.env,
  stdio: "inherit",
});

await rm(path.resolve(frontendRoot, "../backend/data/playwright-stage9.db"), { force: true });
await rm(path.resolve(frontendRoot, "test-results"), { force: true, recursive: true });
await rm(path.resolve(frontendRoot, "playwright-report"), { force: true, recursive: true });

if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
