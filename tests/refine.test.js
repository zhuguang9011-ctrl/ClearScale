const { test } = require('node:test');
const assert = require('node:assert/strict');
const sharp = require('sharp');
const { region, graph, composite } = require('../src/refine');
test('reject invalid selection and clamp floating point edge', () => {
  assert.throws(() => region({ x: -1, y: 0, w: 1, h: 1 }, 100, 100));
  assert.throws(() => region({ x: 0, y: 0, w: NaN, h: 1 }, 100, 100));
  assert.deepEqual(region({ x: 0.5, y: 0, w: 0.5, h: 1 }, 100, 100), { left: 50, top: 0, width: 50, height: 100 });
});
test('graph uses single 512 tile batch and bounded user strength', () => {
  const g = graph('crop.png', 'sd15.safetensors', 'silk', 0.15, 123);
  assert.equal(g['5'].inputs.batch_size, 1);
  assert.equal(g['5'].inputs.tile_width, 512);
  assert.equal(g['5'].inputs.denoise, 0.15);
  assert.deepEqual(g['6'].inputs.images, ['5', 0]);
});
test('compositing preserves every outside pixel and alpha, feathers region edges', async () => {
  const original = Buffer.alloc(100 * 100 * 4);
  for (let i = 0; i < original.length; i += 4) { original[i] = 30; original[i + 1] = 50; original[i + 2] = 70; original[i + 3] = 123; }
  const base = await sharp(original, { raw: { width: 100, height: 100, channels: 4 } }).png().toBuffer();
  const generated = await sharp({ create: { width: 40, height: 40, channels: 3, background: '#ffffff' } }).png().toBuffer();
  const result = await sharp(await composite(base, generated, { left: 30, top: 30, width: 40, height: 40 })).raw().toBuffer();
  for (let y = 0; y < 100; y++) for (let x = 0; x < 100; x++) {
    const i = (y * 100 + x) * 4;
    assert.equal(result[i + 3], 123);
    if (x <= 30 || x >= 69 || y <= 30 || y >= 69) assert.deepEqual(result.subarray(i, i + 4), original.subarray(i, i + 4));
  }
  assert.equal(result[(50 * 100 + 50) * 4], 255);
});
