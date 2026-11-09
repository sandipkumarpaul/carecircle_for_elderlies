import { expect, test, Page } from '@playwright/test';

// CC-12 browser workflow: limits, in-range and out-of-range readings, alerts, trend rule, validation, persistence.
async function signUpWithPatient(page: Page) {
  const email = `alerts-${Date.now()}@example.com`;
  await page.goto('/');
  await page.getByRole('tab', { name: 'Create account' }).click();
  await page.getByRole('textbox', { name: 'Your name', exact: true }).fill('Vitals Demo');
  await page.getByRole('textbox', { name: 'Email address', exact: true }).fill(email);
  await page.getByLabel(/^Password/).fill('Browser-demo-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your care circles' })).toBeVisible();
  await page.getByRole('button', { name: 'Create patient profile' }).click();
  await page.getByRole('textbox', { name: 'Patient name', exact: true }).fill('Vitals Demo');
  await page.getByLabel('Consent / authority statement').fill('I consent to this synthetic browser-test profile.');
  await page.getByRole('checkbox', { name: 'I confirm this consent statement' }).check();
  await page.getByRole('button', { name: 'Create profile', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Vitals & trend alerts' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save reading' })).toBeVisible();
}

async function choose(page: Page, currentValue: string, option: string) {
  // MUI Select: click the visible element showing the current value, then pick from the popup.
  await page.locator('[role="combobox"]', { hasText: currentValue }).first().click();
  await page.getByRole('option', { name: option, exact: true }).click();
}

function localInput(hoursAgo: number) {
  const d = new Date(Date.now() - hoursAgo * 3600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

test('alert centre read, acknowledge, resolve and quiet hours persist', async ({ page }, testInfo) => {
  await signUpWithPatient(page);
  await page.getByRole('button', { name: 'Fill demonstration values' }).click();
  await page.getByRole('button', { name: 'Save limits' }).click();
  await expect(page.getByText('Limits for blood pressure saved.', { exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Systolic (top number)', exact: true }).fill('150');
  await page.getByRole('textbox', { name: 'Diastolic (bottom number)', exact: true }).fill('85');
  await page.getByRole('button', { name: 'Save reading' }).click();
  await expect(page.getByText('Reading saved. A limit alert was raised for the care circle.')).toBeVisible();
  await page.getByRole('button', { name: 'Refresh alerts', exact: true }).click();
  const alert = page.getByTestId('alert-entry');
  await expect(alert).toHaveCount(1);
  await expect(alert.getByText('Unread', { exact: true })).toBeVisible();
  await alert.getByRole('button', { name: 'Mark read', exact: true }).click();
  await expect(alert.getByText('Read', { exact: true })).toBeVisible();
  await page.getByLabel('Unread alerts only').check();
  await page.getByRole('button', { name: 'Refresh alerts', exact: true }).click();
  await expect(alert).toHaveCount(0);
  await page.getByLabel('Unread alerts only').uncheck();
  await page.getByRole('button', { name: 'Refresh alerts', exact: true }).click();
  await alert.getByRole('button', { name: 'Acknowledge alert', exact: true }).click();
  await expect(alert.getByText('acknowledged', { exact: true })).toBeVisible();
  await alert.getByRole('button', { name: 'Resolve alert', exact: true }).click();
  await expect(alert.getByText('resolved', { exact: true })).toBeVisible();
  await page.getByLabel('Quiet hours start', { exact: true }).fill('22:00');
  await page.getByLabel('Quiet hours end', { exact: true }).fill('07:00');
  await page.getByRole('button', { name: 'Save quiet hours', exact: true }).click();
  await expect(page.getByText('Quiet hours saved.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId('alert-entry').getByText('resolved', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Quiet hours start', { exact: true })).toHaveValue('22:00');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('heading', { name: 'Health alert centre', exact: true }).locator('..').screenshot({ path: testInfo.outputPath('alert-center-mobile.png') });
});
