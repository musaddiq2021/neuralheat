// Real production UI and a live saved checkpoint. No network mocking or training.
/* global process, console, document, fetch, location */
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const entry = process.env.NEURALHEAT_CAPTURE_ENTRY;
if (!entry) throw new Error('Run scripts/capture_release_screenshots.py to start the managed engine');
const output = resolve(process.env.NEURALHEAT_CAPTURE_OUTPUT ?? 'docs/screenshots');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: process.env.NEURALHEAT_CAPTURE_BROWSER ?? 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(entry, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelectorAll('.heat-panel canvas').length === 4);
  const health = await page.evaluate(async () => (await fetch('/api/health')).json());
  const model = await page.evaluate(async () => (await fetch('/api/model')).json());
  if (health.active_experiment !== null || !health.model_available) throw new Error('Capture requires an idle real checkpoint');
  const captures = [
    ['physics', 'Physics Lab', '.heat-panel canvas', 4],
    ['overview', 'System Overview', null, 0],
    ['network', 'Neural Network Explorer', '.react-flow__node', 17],
    ['training', 'Training Control Room', null, 0],
    ['latency', 'Latency Lab', '.latency-table tbody tr', 15],
  ];
  for (const [route, heading, selector, count] of captures) {
    await page.evaluate(value => { location.hash = value; }, route);
    await page.getByRole('heading', { name: heading, exact: true }).waitFor();
    if (selector) await page.waitForFunction(({ selector, count }) => document.querySelectorAll(selector).length === count, { selector, count });
    if (route === 'network') await page.waitForSelector('.activation-panel canvas');
    if (route === 'latency') await page.getByRole('button', { name: 'B16', exact: true }).click();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(800);
    if (errors.length) throw new Error(JSON.stringify(errors));
    await page.screenshot({ path: resolve(output, `${route}.png`), fullPage: true, animations: 'disabled' });
    console.log(`Captured ${route}`);
  }
  await writeFile(resolve(output, 'capture.json'), JSON.stringify({
    captured_at_utc: new Date().toISOString(), renderer: 'Chromium browser, existing production React assets',
    viewport: { width: 1600, height: 1100 }, checkpoint_sha256: model.checkpoint_sha256,
    device: health.device, graph_nodes: model.graph.nodes.length, training_started: false,
    mocked_responses: false, frontend_rebuilt: false, pages: captures.map(row => row[0]),
  }, null, 2) + '\n');
} finally {
  await context.close();
  await browser.close();
}
