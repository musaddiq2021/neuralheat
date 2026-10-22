import { expect, test } from '@playwright/test';

test('physics uses actual fields and hides CNN output during numerical animation', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#physics');
  await expect(page.getByText('Simulation ready', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Physics Lab', exact: true })).toBeVisible();
  const prediction = page.locator('.heat-panel').filter({ has: page.getByRole('heading', { name: 'Surrogate prediction' }) });
  await expect(prediction.locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Reset simulation to step zero' }).click();
  await expect(prediction.locator('canvas')).toHaveCount(0);
  await page.getByRole('button', { name: 'Play simulation' }).click();
  await expect(prediction.locator('canvas')).toBeVisible({ timeout: 15_000 });
  await page.getByLabel('Temperature field. Click to place a source, or press Enter for a central source.').click({ position: { x: 90, y: 90 } });
  await expect(page.getByText('03', { exact: true }).last()).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  await expect(page.getByText('Simulation ready', { exact: true })).toBeVisible();
  await expect(page.locator('.source-row')).toHaveCount(3);
  expect(errors).toEqual([]);
});

test('model explorer shows real hooked activations and interactive skip edges', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/#network');
  await expect(page.getByRole('heading', { name: 'Neural Network Explorer' })).toBeVisible();
  await expect(page.locator('.react-flow__node')).toHaveCount(17);
  await expect(page.locator('.activation-panel canvas')).toBeVisible();
  await page.locator('.react-flow__node[data-id="bottleneck"]').click();
  await expect(page.locator('.inspector-name h2')).toHaveText('Bottleneck');
  await expect(page.getByLabel('Activation channel').locator('option')).toHaveCount(32);
  await page.getByLabel('Activation channel').selectOption('4');
  await expect(page.locator('.activation-panel canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Physics Lab', exact: true }).click();
  await page.getByRole('button', { name: 'Network Explorer', exact: true }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(17);
  await expect(page.locator('.activation-panel canvas')).toBeVisible();
  expect(errors).toEqual([]);
});

test('latency view reads saved metrics and switches batch scopes without retraining', async ({ page, request }) => {
  const before = await request.get('/api/health');
  expect((await before.json()).active_experiment).toBeNull();
  const saved = await (await request.get('/api/runs/primary')).json();
  await page.goto('/#latency');
  await expect(page.getByRole('heading', { name: 'Latency Lab', exact: true })).toBeVisible();
  await expect(page.getByText('HISTORICAL · NO RECOMPUTATION')).toBeVisible();
  await page.getByRole('button', { name: 'B16', exact: true }).click();
  await expect(page.locator('.latency-table tbody tr')).toHaveCount(saved.benchmark.latency.length);
  await expect(page.getByText(/CPU-versus-CPU · (slower|faster)/)).toBeVisible();
  await page.getByRole('button', { name: 'Throughput', exact: true }).click();
  await expect(page.getByText('Samples / second · recorded batch size ÷ mean batch duration')).toBeVisible();
  const after = await request.get('/api/health');
  expect((await after.json()).active_experiment).toBeNull();
});

test('training controls are idle on open and existing logs and losses are readable', async ({ page }) => {
  await page.goto('/#training');
  await expect(page.getByRole('heading', { name: 'Training Control Room' })).toBeVisible();
  await expect(page.getByText('Worker idle', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Start smoke/ })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled();
  await expect(page.getByRole('log')).toContainText('epoch');
  await expect(page.getByRole('img', { name: 'Recorded training and validation loss by epoch' })).toBeVisible();
});

test('mobile navigation and scientific panels stay within the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#physics');
  await expect(page.getByText('Simulation ready', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('button', { name: 'Latency Lab' }).click();
  await expect(page.getByRole('heading', { name: 'Latency Lab', exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1);
  expect(overflow).toBe(false);
});
