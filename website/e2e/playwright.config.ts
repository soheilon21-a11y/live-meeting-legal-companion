import { defineConfig } from "@playwright/test";

const baseURL = process.env.NIYOSH_E2E_BASE_URL ?? "http://127.0.0.1:4173";

export default defineConfig({
  testDir: ".",
  timeout: 120_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    headless: true,
    channel: "chromium",
    permissions: ["microphone"],
    launchOptions: {
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
      ],
    },
  },
});
