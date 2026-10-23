import { expect, test } from "@playwright/test";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";

const dataDir = process.env.NIYOSH_E2E_DATA_DIR ?? "";
const baseURL = process.env.NIYOSH_E2E_BASE_URL ?? "http://127.0.0.1:4173";
const LIVE_PATH = "/live-meeting-legal-companion/live/";
const API = "http://127.0.0.1:8002";

function chunkFiles(sessionId: string): string[] {
  const dir = join(dataDir, "audio", sessionId);
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.startsWith("chunk_") && f.endsWith(".webm"));
}

async function gotoLive(page: Page) {
  await page.goto(baseURL + LIVE_PATH);
  await page.locator("#meeting-start").waitFor();
}

async function startRecording(page: Page): Promise<string> {
  const respPromise = page.waitForResponse(
    (r) => r.url().endsWith("/api/live/session") && r.request().method() === "POST",
  );
  await page.click("#meeting-start");
  const resp = await respPromise;
  return (await resp.json()).session_id as string;
}

test("crosses 15s boundary into 2+ chunk files", async ({ page }) => {
  await gotoLive(page);
  const sessionId = await startRecording(page);
  await expect(page.locator("#meeting-status-text")).toHaveText("Recording");
  await expect
    .poll(() => chunkFiles(sessionId).length, { timeout: 45000, intervals: [2000] })
    .toBeGreaterThanOrEqual(2);
});

test("disable-audio stops recorder and server 409s a straggler chunk", async ({ page, request }) => {
  await gotoLive(page);
  const sessionId = await startRecording(page);
  await expect(page.locator("#meeting-status-text")).toHaveText("Recording");

  const captureResp = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/live/session/${sessionId}/capture`) &&
      r.request().method() === "POST",
  );
  await page.check("#live-disable-audio");
  await captureResp;

  await expect(page.locator("#meeting-start")).toBeDisabled();
  await expect(page.locator('input[name="meeting-mode"]').first()).toBeDisabled();

  const resp = await request.post(`${API}/api/live/session/${sessionId}/chunk`, {
    multipart: {
      chunk_index: "999",
      mode: "dictation",
      file: { name: "straggler.webm", mimeType: "audio/webm", buffer: Buffer.from("straggler") },
    },
  });
  expect(resp.status()).toBe(409);
});

test("renders empty-segment placeholder", async ({ page }) => {
  await gotoLive(page);
  await startRecording(page);
  await expect(page.locator("#meeting-status-text")).toHaveText("Recording");
  await expect(page.locator("#meeting-transcript .transcript-text").first()).toHaveText(
    "[no speech detected]",
    { timeout: 45000 },
  );
});

test("ending tracks mid-session shows micDenied without hanging", async ({ page }) => {
  await gotoLive(page);
  await startRecording(page);
  await expect(page.locator("#meeting-status-text")).toHaveText("Recording");
  await page.evaluate(() => {
    // @ts-ignore - mediaStream is a top-level `let` closure in live.js, reachable via global lexical scope
    const stream = mediaStream as MediaStream;
    stream.getTracks().forEach((t) => t.stop());
  });
  await expect(page.locator("#meeting-status-text")).toHaveText(
    "Microphone permission denied. Please allow microphone access.",
    { timeout: 45000 },
  );
  await expect(page.locator("#meeting-start")).toBeVisible();
});

test("stop handshake writes final chunk and loses no in-flight chunk", async ({ page }) => {
  await gotoLive(page);
  const sessionId = await startRecording(page);
  await expect(page.locator("#meeting-status-text")).toHaveText("Recording");
  await page.waitForTimeout(2000);
  await page.click("#meeting-stop");
  await expect
    .poll(() => chunkFiles(sessionId).length, { timeout: 20000, intervals: [1000] })
    .toBeGreaterThanOrEqual(1);
  await expect(page.locator("#meeting-status-text")).toHaveText("Idle", { timeout: 20000 });
});

test("backend down shows banner on load", async ({ page }) => {
  await page.route("http://127.0.0.1:8002/**", (route) => route.abort());
  await page.route("http://localhost:8002/**", (route) => route.abort());
  await gotoLive(page);
  await expect(page.locator("#backend-banner")).toBeVisible();
});
