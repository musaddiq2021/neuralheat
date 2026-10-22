import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  testDir: './tests', fullyParallel: false, timeout: 45_000,
  expect: { timeout: 15_000 },
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1100 } } }],
  // Start the launcher first. Tests use the live solver and checkpoint API;
  // no generated browser fixtures or invented scientific values.
  reporter: [['list'], ['html', { open: 'never' }]],
  webServer: process.env.NEURALHEAT_E2E_START_SERVERS === '1' ? [
    { command: 'python -m uvicorn neuralheat.studio.app:app --host 127.0.0.1 --port 8000 --workers 1', cwd: fileURLToPath(new URL('..', import.meta.url)), url: 'http://127.0.0.1:8000/api/health', timeout: 45_000, reuseExistingServer: !process.env.CI },
    { command: 'npm run preview', url: 'http://127.0.0.1:5173', timeout: 30_000, reuseExistingServer: !process.env.CI },
  ] : undefined,
});
