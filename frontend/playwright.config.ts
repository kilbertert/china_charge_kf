import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: {
    timeout: 90_000,
  },
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'https://ai.trendpower.cc/chat/',
    headless: true,
    ignoreHTTPSErrors: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || '/usr/bin/google-chrome',
    },
  },
})
