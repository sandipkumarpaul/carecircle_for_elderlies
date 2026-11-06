import { defineConfig } from '@playwright/test';

const python = process.env.E2E_PYTHON ? `"${process.env.E2E_PYTHON}"` : process.platform === 'win32' ? '".venv\\Scripts\\python.exe"' : '.venv/bin/python';
export default defineConfig({
  testDir: './tests', timeout: 60000, workers: 1, retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://localhost:5173', channel: process.env.E2E_BROWSER || undefined,
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: [
    { command: `${python} -m tests.run_browser_server`, cwd: '../backend', url: 'http://127.0.0.1:8000/api/v1/health', reuseExistingServer: false, timeout: 30000 },
    { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: false, timeout: 30000 },
  ],
});
