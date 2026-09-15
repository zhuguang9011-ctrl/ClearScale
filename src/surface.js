// Conservative colour-noise cleanup. No generative model, sharpening or relighting.
const sharp = require('sharp');
async function surface(input, output, options = {}) {
  const strength = Number(options.strength ?? 0.35);
  if (!Number.isFinite(strength) || strength < 0 || strength > 1) throw new Error('强度必须在 0–1 之间');
  const { data, info } = await sharp(input, { limitInputPixels: 20000000 }).rotate().toColourspace('srgb').ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const raw = { width: info.width, height: info.height, channels: 4 };
  const result = Buffer.from(data);
  // Change colour differences only; preserve the source luminance and alpha.
  const luminance = p => 0.2126 * data[p] + 0.7152 * data[p + 1] + 0.0722 * data[p + 2];
  for (let y = 1; y < info.height - 1; y++) for (let x = 1; x < info.width - 1; x++) {
    const p = (y * info.width + x) * 4;
    if (data[p + 3] !== 255 || strength === 0) continue;
    const l = luminance(p);
    let total = 0; const chroma = [0, 0, 0];
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const q = ((y + dy) * info.width + x + dx) * 4;
      if (data[q + 3] !== 255) continue;
      const ql = luminance(q);
      const distance = Math.max(...[0, 1, 2].map(c => Math.abs(data[q + c] - data[p + c])));
      if (distance > 24 || Math.abs(ql - l) > 12) continue;
      const weight = Math.exp(-distance * distance / 200) / (1 + dx * dx + dy * dy);
      total += weight;
      for (let c = 0; c < 3; c++) chroma[c] += (data[q + c] - ql) * weight;
    }
    const delta = chroma.map((v, c) => strength * (v / total - (data[p + c] - l)));
    // Reduce the entire adjustment together rather than clipping channels independently.
    let amount = 1;
    for (let c = 0; c < 3; c++) {
      if (delta[c] > 0) amount = Math.min(amount, (255 - data[p + c]) / delta[c]);
      if (delta[c] < 0) amount = Math.min(amount, -data[p + c] / delta[c]);
    }
    for (let c = 0; c < 3; c++) result[p + c] = Math.round(data[p + c] + delta[c] * amount);
  }
  await sharp(result, { raw }).png().toFile(output);
  return { width: info.width, height: info.height };
}
module.exports = { surface };
