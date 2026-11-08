import { expect, test, Page } from '@playwright/test';

// CC-12 browser workflow: limits, in-range and out-of-range readings, alerts, trend rule, validation, persistence.
async function signUpWithPatient(page: Page) {
  const email = `vitals-${Date.now()}@example.com`;
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

test('vitals limits, alerts, trend rule and validation persist through the UI', async ({ page }, testInfo) => {
  await signUpWithPatient(page);

  // Demonstration limits for blood pressure.
  await page.getByRole('button', { name: 'Fill demonstration values' }).click();
  await page.getByRole('button', { name: 'Save limits' }).click();
  await expect(page.getByText('Limits for DEMO'.replace('DEMO', 'blood pressure') + ' saved.', { exact: true })).toBeVisible();

  // In range: no alert.
  await page.getByRole('textbox', { name: /^Systolic \(top number\)/ }).fill('120');
  await page.getByRole('textbox', { name: /^Diastolic \(bottom number\)/ }).fill('80');
  await page.getByRole('button', { name: 'Save reading' }).click();
  await expect(page.getByText('Reading saved.', { exact: true })).toBeVisible();
  await expect(page.getByText('Within your limits')).toBeVisible();

  // Out of range: one limit alert is reported.
  await page.getByRole('textbox', { name: /^Systolic \(top number\)/ }).fill('150');
  await page.getByRole('textbox', { name: /^Diastolic \(bottom number\)/ }).fill('85');
  await page.getByRole('button', { name: 'Save reading' }).click();
  await expect(page.getByText('Reading saved. A limit alert was raised for the care circle.')).toBeVisible();
  await expect(page.getByText('Outside your limits')).toBeVisible();

  // Invalid pair is rejected and nothing is added.
  await page.getByRole('textbox', { name: /^Systolic \(top number\)/ }).fill('80');
  await page.getByRole('textbox', { name: /^Diastolic \(bottom number\)/ }).fill('120');
  await page.getByRole('button', { name: 'Save reading' }).click();
  await expect(page.getByText('Invalid request')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Readings (2)' })).toBeVisible();

  // Weight rising 70 -> 71 -> 72.5 over three readings triggers the documented trend rule.
  await choose(page, 'Blood pressure', 'Weight');
  for (const [hours, kg] of [[48, '70'], [24, '71'], [0, '72.5']] as const) {
    await page.getByRole('textbox', { name: /^Value/ }).fill(kg);
    if (hours) await page.getByLabel(/Measured at/).fill(localInput(hours));
    await page.getByRole('button', { name: 'Save reading' }).click();
    await expect(page.getByRole('heading', { name: new RegExp(`Readings \\(${2 + [48, 24, 0].indexOf(hours) + 1}\\)`) })).toBeVisible();
    await page.getByLabel(/Measured at/).fill('');
  }
  await expect(page.getByText('Reading saved. A trend alert was raised for the care circle.')).toBeVisible();
  await expect(page.getByText(/Worsening trend: rose by 2\.5 kg across the last 3 readings/)).toBeVisible();

  // Persistence, layout and a screenshot.
  await page.reload();
  await expect(page.getByText('Weight: 72.5 kg')).toBeVisible();
  await expect(page.getByText('Blood pressure: 150/85 mmHg')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('heading', { name: 'Vitals & trend alerts' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('vitals-mobile.png') });
});
