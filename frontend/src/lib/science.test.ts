import { test } from 'node:test';
import assert from 'node:assert/strict';
import { color, format, predictionVisible, range, sourcePreview } from './science.ts';

test('CNN output is revealed exclusively at the trained final step', () => {
  for (let step = 0; step < 120; step++) assert.equal(predictionVisible(step, 120), false);
  assert.equal(predictionVisible(120, 120), true);
  assert.equal(predictionVisible(121, 120), false);
});
test('heatmap color range includes negative predictions and has a finite zero-field scale', () => {
  assert.deepEqual(range([[[0, -0.2], [0.7, 1.3]], null]), [-0.2, 1.3]);
  assert.deepEqual(range([[[0, 0], [0, 0]]]), [0, 1]);
});
test('source preview uses physical coordinates and enforces zero edges', () => {
  const field = sourcePreview([{ x: 0.5, y: 0.5, sigma: 0.1, amplitude: 2 }], 65);
  assert.equal(field[32][32], 2);
  assert.equal(field[0].reduce((a, b) => a+b, 0), 0);
  assert.equal(field[32][0], 0);
  assert.equal(field[32][64], 0);
  assert.ok(field[32][31] < field[32][32]);
});
test('colormap clamps to its declared colorbar bounds', () => {
  assert.deepEqual(color(-1, 0, 1), color(0, 0, 1));
  assert.deepEqual(color(2, 0, 1), color(1, 0, 1));
  assert.deepEqual(color(1, 1, 1), [0, 0, 4]);
});
test('missing metrics remain unavailable rather than being displayed as zero', () => {
  assert.equal(format(undefined), '—');
  assert.equal(format(null), '—');
  assert.equal(format(NaN), '—');
  assert.equal(format(0), '0');
});
