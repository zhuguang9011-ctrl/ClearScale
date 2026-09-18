const { test } = require('node:test');
const assert = require('node:assert/strict');
const sharp = require('sharp');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { surface } = require('../src/surface');
test('surface cleanup reduces chroma noise, preserves luminance, alpha and material boundary', async () => {
  const w = 40, h = 40, pixels = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const p = (y * w + x) * 4, n = (x + y) % 2 ? 6 : -6;
    pixels[p] = x < 20 ? 100 + n : 220;
    pixels[p + 1] = x < 20 ? 100 - Math.round(n * 0.2126 / 0.7152) : 40;
    pixels[p + 2] = x < 20 ? 100 : 40;
    pixels[p + 3] = y === 0 ? 0 : 255;
  }
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'surface-test-'));
  try {
    const input = await sharp(pixels, { raw: { width: w, height: h, channels: 4 } }).png().toBuffer();
    await surface(input, path.join(dir, 'out.png'));
    const { data, info } = await sharp(path.join(dir, 'out.png')).raw().toBuffer({ resolveWithObject: true });
    assert.equal(info.width, w); assert.equal(info.height, h);
    let before = 0, after = 0;
    for (let p = 0; p < data.length; p += 4) {
      assert.equal(data[p + 3], pixels[p + 3]);
      const drift = [0.2126, 0.7152, 0.0722].reduce((sum, weight, c) => sum + weight * (data[p + c] - pixels[p + c]), 0);
      assert.ok(Math.abs(drift) <= 0.501);
      const x = (p / 4) % w;
      if (x >= 20 || pixels[p + 3] === 0) assert.deepEqual(data.subarray(p, p + 4), pixels.subarray(p, p + 4));
      if (x > 2 && x < 17) { before += Math.abs(pixels[p] - pixels[p + 1]); after += Math.abs(data[p] - data[p + 1]); }
    }
    assert.ok(after < before);
    await surface(input, path.join(dir, 'zero.png'), { strength: 0 });
    assert.deepEqual(await sharp(path.join(dir, 'zero.png')).raw().toBuffer(), pixels);
    await assert.rejects(surface(input, path.join(dir, 'bad.png'), { strength: NaN }));
  } finally { await fs.rm(dir, { recursive: true, force: true }); }
});
