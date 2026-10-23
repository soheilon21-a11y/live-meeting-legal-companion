import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const websiteDir = resolve(__dirname, "..");
const repoRoot = resolve(websiteDir, "..");
const backendDir = join(repoRoot, "backend");

const STATIC_PORT = 4173;
const API_PORT = 8002;
const baseURL = `http://127.0.0.1:${STATIC_PORT}`;

const node = process.execPath;
const astroCli = join(websiteDir, "node_modules", "astro", "astro.js");
const playwrightCli = join(websiteDir, "node_modules", "@playwright", "test", "cli.js");

const dataDir = join(tmpdir(), `niyosh-e2e-${Date.now()}`);
rmSync(dataDir, { recursive: true, force: true });
mkdirSync(dataDir, { recursive: true });

function findPython() {
  for (const p of [
    join(repoRoot, ".venv", "Scripts", "python.exe"),
    join(backendDir, ".venv", "Scripts", "python.exe"),
  ]) {
    if (existsSync(p)) return p;
  }
  return process.env.NIYOSH_E2E_PYTHON ?? "python";
}

const python = findPython();
const children = [];

function runSync(cmd, args, opts) {
  return spawnSync(cmd, args, { stdio: "inherit", ...opts }).status;
}

function start(cmd, args, opts) {
  const child = spawn(cmd, args, { stdio: "inherit", ...opts });
  children.push(child);
  return child;
}

async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function cleanup(code) {
  for (const c of children) {
    try {
      c.kill();
    } catch {
      /* already gone */
    }
  }
  if (process.platform === "win32") {
    for (const c of children) {
      try {
        spawnSync("taskkill", ["/pid", String(c.pid), "/T", "/F"], { stdio: "ignore" });
      } catch {
        /* already gone */
      }
    }
  }
  rmSync(dataDir, { recursive: true, force: true });
  process.exit(code);
}

process.on("SIGINT", () => cleanup(130));
process.on("SIGTERM", () => cleanup(143));

try {
  const install = runSync(node, [playwrightCli, "install", "chromium"], { cwd: websiteDir });
  if (install !== 0) {
    console.error("[e2e] failed to ensure Playwright chromium is installed");
    cleanup(1);
  }

  const build = runSync(node, [astroCli, "build"], { cwd: websiteDir });
  if (build !== 0) {
    console.error("[e2e] website build failed");
    cleanup(1);
  }

  start(
    python,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(API_PORT)],
    {
      cwd: backendDir,
      env: { ...process.env, DATA_DIR: dataDir, NIYOSH_E2E_FAKE_ASR: "1" },
    },
  );

  start(
    node,
    [astroCli, "preview", "--host", "127.0.0.1", "--port", String(STATIC_PORT)],
    { cwd: websiteDir },
  );

  const apiUp = await waitFor(`http://127.0.0.1:${API_PORT}/health`, 30000);
  const webUp = await waitFor(`${baseURL}/live-meeting-legal-companion/live/`, 30000);
  if (!apiUp || !webUp) {
    console.error(`[e2e] servers failed to start (api=${apiUp} web=${webUp})`);
    cleanup(1);
  }

  const testCode = runSync(
    node,
    [playwrightCli, "test", "--config", "e2e/playwright.config.ts"],
    {
      cwd: websiteDir,
      env: {
        ...process.env,
        NIYOSH_E2E_DATA_DIR: dataDir,
        NIYOSH_E2E_BASE_URL: baseURL,
      },
    },
  );

  cleanup(testCode ?? 1);
} catch (err) {
  console.error("[e2e] harness error:", err);
  cleanup(1);
}
