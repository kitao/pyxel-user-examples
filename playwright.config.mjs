import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.PLAYWRIGHT_PORT ?? 4185);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid test port.');
const baseURL = `http://127.0.0.1:${port}`;
const chromiumChannel = process.env.PLAYWRIGHT_CHROMIUM_CHANNEL || 'chrome';

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  // A stray test.only must never let the pre-deploy check pass with skipped tests.
  forbidOnly: true,
  workers: 2,
  reporter: 'list',
  // Waits end as soon as their condition holds; the ceiling only absorbs slow, loaded machines.
  expect: { timeout: 10_000, toPass: { timeout: 10_000 } },
  use: {
    baseURL,
    locale: 'en-US',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // wrangler dev builds dist/ and serves it as Cloudflare would, with _headers.
  webServer: {
    command: `node scripts/wrangler.mjs dev --port ${port}`,
    url: `${baseURL}/pyxel/user-examples/`,
    timeout: 120_000,
    // SIGTERM lets Wrangler stop workerd and remove its temporary files.
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
  },
  projects: [
    {
      name: 'chrome',
      use: { browserName: 'chromium', channel: chromiumChannel },
    },
    { name: 'webkit', use: { browserName: 'webkit' } },
    // Phone profiles: mobile user agent, touch-only input, and high pixel density.
    { name: 'iphone', use: { ...devices['iPhone 17'] } },
    {
      name: 'android',
      use: { ...devices['Pixel 9'], channel: chromiumChannel },
    },
  ],
});
