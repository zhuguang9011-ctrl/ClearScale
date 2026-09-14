const sharp = require('sharp');

// Blend only similar neighbouring colours. Large boundaries, highlights and
// different materials are protected by a colour-distance gate.
async function prepare(input, output, options) {
  const { data, info } = await sharp(input).rotate().toColourspace('srgb').ensureAlpha()
    .raw().toBuffer({ resolveWithObject: true });
  const raw = { width: info.width, height: info.height, channels: 4 };
  let current = Buffer.from(data);
  const passes = [];
  if (options.denoise) passes.push({ sigma: 0.8, threshold: 18, amount: 0.8 });
  if (options.evenness !== 'off') passes.push({
    sigma: options.evenness === 'standard' ? 3 : 1.6,
    threshold: options.evenness === 'standard' ? 20 : 12,
    amount: options.evenness === 'standard' ? 0.65 : 0.4
  });
  for (const pass of passes) {
    const smooth = await sharp(current, { raw }).blur(pass.sigma).raw().toBuffer();
    const next = Buffer.from(current);
    for (let p = 0; p < current.length; p += 4) {
      if (current[p + 3] < 250) continue;
      const x = (p / 4) % info.width;
      const y = Math.floor(p / 4 / info.width);
      const neighbours = [];
      if (x > 0) neighbours.push(p-4);
      if (x+1 < info.width) neighbours.push(p+4);
      if (y > 0) neighbours.push(p-info.width*4);
      if (y+1 < info.height) neighbours.push(p+info.width*4);
      if (neighbours.some(q => Math.max(...[0,1,2].map(c => Math.abs(current[p+c]-current[q+c]))) > 40)) continue;
      let distance = 0;
      for (let c = 0; c < 3; c++) distance += (current[p+c] - smooth[p+c]) ** 2;
      const weight = distance > 3 * 24 ** 2 ? 0 : pass.amount * Math.exp(-distance / (3 * pass.threshold ** 2));
      for (let c = 0; c < 3; c++) next[p+c] = Math.round(current[p+c] * (1-weight) + smooth[p+c] * weight);
    }
    current = next;
  }
  await sharp(current, { raw }).removeAlpha().png().toFile(output);
  return { width: info.width, height: info.height };
}

async function finish(input, prepared, rendered, output, options) {
  const meta = await sharp(prepared).metadata();
  const ai = await sharp(rendered).metadata();
  if (ai.width !== meta.width * 4 || ai.height !== meta.height * 4)
    throw new Error('AI 输出尺寸异常，已停止导出以避免错位图片。');
  const width = meta.width * options.scale, height = meta.height * options.scale;
  let pipeline = sharp(rendered).removeAlpha().resize(width, height, { kernel: 'lanczos3' });
  const original = await sharp(input).metadata();
  if (original.hasAlpha && options.format !== 'jpg') {
    const alpha = await sharp(input).rotate().ensureAlpha().extractChannel('alpha')
      .resize(width, height).raw().toBuffer();
    const rgb = await pipeline.raw().toBuffer();
    pipeline = sharp(rgb, { raw: { width, height, channels: 3 } })
      .joinChannel(alpha, { raw: { width, height, channels: 1 } });
  }
  if (options.format === 'jpg') pipeline = pipeline.jpeg({ quality: 95, chromaSubsampling: '4:4:4' });
  else if (options.format === 'webp') pipeline = pipeline.webp({ lossless: true });
  else pipeline = pipeline.png();
  await pipeline.toFile(output);
}
module.exports = { prepare, finish };
