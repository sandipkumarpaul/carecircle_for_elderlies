import { expect, test, Page } from '@playwright/test';

async function register(page: Page, name: string, email: string) {
  await page.getByRole('tab', { name: 'Create account' }).click();
  await page.getByRole('textbox', { name: 'Your name', exact: true }).fill(name);
  await page.getByRole('textbox', { name: 'Email address', exact: true }).fill(email);
  await page.getByLabel(/^Password/).fill('Browser-demo-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your care circles' })).toBeVisible();
}

test('patient invites caregiver, changes scope, and revokes access', async ({ browser }, testInfo) => {
  const patientContext = await browser.newContext();
  const caregiverContext = await browser.newContext();
  const patient = await patientContext.newPage(); const caregiver = await caregiverContext.newPage();
  const stamp = Date.now();
  const email = `caregiver-${stamp}@example.com`;
  try {
    await patient.goto('/');
    await register(patient, 'Demo Patient', `patient-${stamp}@example.com`);
    await patient.getByRole('button', { name: 'Create patient profile' }).click();
    await patient.getByRole('textbox', { name: 'Patient name', exact: true }).fill('Demo Patient');
    await patient.getByLabel('Consent / authority statement').fill('I consent to this synthetic browser-test profile.');
    await patient.getByRole('checkbox', { name: 'I confirm this consent statement' }).check();
    await patient.getByRole('button', { name: 'Create profile', exact: true }).click();
    await patient.getByRole('button', { name: 'Invite caregiver' }).click();
    await patient.getByLabel('Caregiver email').fill(email);
    await patient.getByRole('checkbox', { name: 'View medicines', exact: true }).check();
    await patient.getByRole('checkbox', { name: 'I authorize sharing' }).check();
    await patient.getByRole('button', { name: 'Create invitation', exact: true }).click();
    const link = await patient.getByLabel('New invitation link').inputValue();
    await caregiver.goto(link);
    await register(caregiver, 'Demo Caregiver', email);
    await caregiver.getByRole('button', { name: 'Review invitation' }).click();
    await expect(caregiver.getByText('Join', { exact: false }).filter({ hasText: 'Demo Patient' })).toBeVisible();
    await caregiver.getByRole('checkbox', { name: 'I accept this caregiver role' }).check();
    await caregiver.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await expect(caregiver.getByRole('heading', { name: 'Your access to Demo Patient' })).toBeVisible();
    await expect(caregiver.getByRole('button', { name: 'Invite caregiver', exact: true })).toHaveCount(0);
    await patient.reload();
    await patient.getByRole('button', { name: 'Edit access', exact: true }).click();
    await patient.getByRole('checkbox', { name: 'View vitals', exact: true }).check();
    await patient.getByRole('button', { name: 'Save access', exact: true }).click();
    await expect(patient.getByRole('dialog')).toHaveCount(0);
    await caregiver.reload();
    await expect(caregiver.getByText('View vitals', { exact: true })).toBeVisible();
    await patient.screenshot({ path: testInfo.outputPath('patient-circle.png'), fullPage: true });
    await caregiver.setViewportSize({ width: 390, height: 844 });
    await caregiver.screenshot({ path: testInfo.outputPath('caregiver-mobile.png'), fullPage: true });
    expect(await caregiver.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await patient.getByRole('button', { name: 'Revoke access', exact: true }).click();
    await patient.getByRole('button', { name: 'Confirm revocation', exact: true }).click();
    await expect(patient.getByRole('dialog')).toHaveCount(0);
    await caregiver.reload();
    await expect(caregiver.getByText('You have no patient profiles on this page.', { exact: false })).toBeVisible();
    await caregiver.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(caregiver.getByRole('tab', { name: 'Sign in' })).toBeVisible();
  } finally { await patientContext.close(); await caregiverContext.close(); }
});

test('login layout fits mobile and desktop', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('login-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('login-mobile.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
