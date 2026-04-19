import { defineConfig, devices } from '@playwright/test';

// E2E runs against an ingress that serves the SPA at `/` and proxies `/api`
// to the backend. Locally that's typically Vite-dev (:5173) with its `/api`
// proxy pointed at the backend (:8080); in CI it's the same Vite-dev pattern
// after `backend/docker-compose.yml` brings up Postgres/Redis and we run
// uvicorn on :8080.
export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
});
