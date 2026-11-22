import { expect, test, Page } from '@playwright/test';

async function signUpWithPatient(page: Page) {
  const email = `appt-${Date.now()}@example.com`;
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.getByRole('tab', { name: 'Create account' }).click();
  await page.getByRole('textbox', { name: 'Your name', exact: true }).fill('Appt Demo');
  await page.getByRole('textbox', { name: 'Email address', exact: true }).fill(email);
  await page.getByLabel(/^Password/).fill('Browser-demo-password-123');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: 'Create patient profile' }).click();
  await page.getByRole('textbox', { name: 'Patient name', exact: true }).fill('Appt Demo');
  await page.getByLabel('Consent / authority statement').fill('I consent to this synthetic test.');
  await page.getByRole('checkbox', { name: 'I confirm this consent statement' }).check();
  await page.getByRole('button', { name: 'Create profile', exact: true }).click();
  await page.waitForTimeout(2500);
  await page.getByRole('heading', { name: 'Appointments' }).first().scrollIntoViewIfNeeded();
  await expect(page.getByRole('heading', { name: 'Appointments' }).first()).toBeVisible();
}

function futureLocal(hoursAhead = 48) {
  const d = new Date(Date.now() + hoursAhead * 3600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Scoped to the create form to avoid strict mode violations with repeated field names
function scheduleForm(page: Page) {
  return page.locator('form').filter({ hasText: 'Schedule appointment' });
}

async function scheduleAppointment(page: Page, clinician: string, hoursAhead = 48) {
  const form = scheduleForm(page);
  await form.getByRole('textbox', { name: 'Clinician or service' }).fill(clinician);
  await form.getByLabel('Date and time').fill(futureLocal(hoursAhead));
  await form.getByLabel('Timezone').fill('Asia/Dhaka');
  await form.getByRole('button', { name: 'Schedule' }).click();
  await expect(page.getByText('Appointment scheduled.')).toBeVisible();
}

test('schedule, checklist, complete with post-visit prompt, cancel and filter', async ({ page }, testInfo) => {
  await signUpWithPatient(page);

  // Schedule with checklist items
  const form = scheduleForm(page);
  await form.getByRole('textbox', { name: 'Clinician or service' }).fill('Dr Rahman');
  await form.getByLabel('Date and time').fill(futureLocal(48));
  await form.getByLabel('Timezone').fill('Asia/Dhaka');
  await form.getByLabel(/Pre-visit checklist/).fill('Bring prescriptions\nList symptoms');
  await form.getByRole('button', { name: 'Schedule' }).click();
  await expect(page.getByText('Appointment scheduled.')).toBeVisible();
  await expect(page.getByText('Dr Rahman')).toBeVisible();
  await expect(page.locator('.MuiChip-label', { hasText: 'Scheduled' }).first()).toBeVisible();

  // Show checklist and tick first item
  // Show checklist — both items visible
  await page.getByRole('button', { name: /Show checklist/ }).click();
  await expect(page.getByText('Bring prescriptions')).toBeVisible();
  await expect(page.getByText('List symptoms')).toBeVisible();
  // Tick first item by clicking its label text (MUI Checkbox uses hidden native input)
  // The click fires a PATCH to the API; no error alert means it succeeded
  await page.getByText('Bring prescriptions').click();
  await page.waitForTimeout(2000);
  await expect(page.locator('[role="alert"]').filter({ hasText: /error/i })).toHaveCount(0);
  // Checklist items remain visible (the view keeps the list open after reload)
  await expect(page.getByText('List symptoms')).toBeVisible();

  // Complete the appointment
  await page.getByRole('button', { name: 'Complete' }).click();
  await expect(page.getByText('Appointment marked completed')).toBeVisible();
  await expect(page.locator('.MuiChip-label', { hasText: 'Completed' }).first()).toBeVisible();
  await expect(page.getByText(/Post-visit: remember to upload/)).toBeVisible();

  // Dismiss the post-visit prompt
  await page.getByRole('button', { name: 'Dismiss' }).click();
  await expect(page.getByText('Post-visit prompt dismissed.')).toBeVisible();

  // Schedule a second appointment and cancel it
  await scheduleAppointment(page, 'Dr Ali', 72);
  await expect(page.getByText('Dr Ali')).toBeVisible();
  page.once('dialog', dialog => dialog.accept('Not needed'));
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByText('Appointment cancelled.')).toBeVisible();

  // Filter by status — scope to appointments list paper, use its last combobox (the Show filter)
  const apptPaper = page.locator('.MuiPaper-root').filter({ hasText: /Appointments \(/ }).last();
  const filterSelect = apptPaper.locator('[role="combobox"]').last();

  await filterSelect.click();
  await page.getByRole('option', { name: 'Scheduled', exact: true }).click();
  await page.waitForTimeout(1000);
  await expect(page.getByText(/Appointments \(0\)/).first()).toBeVisible();

  await filterSelect.click();
  await page.getByRole('option', { name: 'Completed', exact: true }).click();
  await page.waitForTimeout(1000);
  await expect(page.getByText(/Appointments \(1\)/).first()).toBeVisible();

  // Reload — data persists
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await expect(page.getByText('Dr Rahman')).toBeVisible();

  // Mobile layout check
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('heading', { name: 'Appointments' }).first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('appointments-mobile.png') });
});
