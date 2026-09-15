const sharp = require('sharp');
const { randomUUID } = require('node:crypto');
const { setTimeout: delay } = require('node:timers/promises');
const BASE = 'http://127.0.0.1:8188';
const PRESETS = {
  silk: 'photograph of silk PLA 3D printed object, fine subtle printed layer texture, original colors, soft silk sheen, natural soft reflections, realistic polymer surface',
  black: 'photograph of black injection molded plastic, subtle fine molded surface grain, restrained satin reflections, realistic black polymer',
  natural: 'professional product photograph, realistic subtle surface microtexture, natural soft lighting, fine material details'
};
async function api(route, options = {}, signal) {
  const response = await fetch(BASE + route, { ...options, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(5000), redirect: 'error' });
  if (!response.ok) throw new Error(`ComfyUI ${response.status}: ${(await response.text()).slice(0, 500)}`);
  return response;
}
async function status() {
  const info = await (await api('/object_info')).json();
  const required = ['CheckpointLoaderSimple', 'CLIPTextEncode', 'LoadImage', 'SaveImage', 'UltimateSDUpscaleNoUpscale'];
  const missing = required.filter(key => !info[key]);
  return { ready: !missing.length, missing, models: info.CheckpointLoaderSimple?.input?.required?.ckpt_name?.[0] || [] };
}
function graph(image, model, preset, strength, seed) {
  return {
    '1': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: model } },
    '2': { class_type: 'CLIPTextEncode', inputs: { clip: ['1', 1], text: PRESETS[preset] || PRESETS.natural } },
    '3': { class_type: 'CLIPTextEncode', inputs: { clip: ['1', 1], text: 'waxy, melted, chrome, excessive gloss, oversharpened, noisy, distorted geometry, extra parts, text, watermark' } },
    '4': { class_type: 'LoadImage', inputs: { image } },
    '5': { class_type: 'UltimateSDUpscaleNoUpscale', inputs: {
      upscaled_image: ['4', 0], model: ['1', 0], positive: ['2', 0], negative: ['3', 0], vae: ['1', 2],
      seed, steps: 20, cfg: 5, sampler_name: 'dpmpp_2m', scheduler: 'karras', denoise: strength,
      mode_type: 'Linear', tile_width: 512, tile_height: 512, mask_blur: 8, tile_padding: 32,
      seam_fix_mode: 'None', seam_fix_denoise: 0.1, seam_fix_width: 64, seam_fix_mask_blur: 8,
      seam_fix_padding: 16, force_uniform_tiles: true, tiled_decode: true, batch_size: 1
    } },
    '6': { class_type: 'SaveImage', inputs: { images: ['5', 0], filename_prefix: 'ClearScale/refine' } }
  };
}
function region(rect, width, height) {
  if (!rect || !['x', 'y', 'w', 'h'].every(k => Number.isFinite(rect[k])) || rect.x < 0 || rect.y < 0 || rect.w <= 0 || rect.h <= 0 || rect.x + rect.w > 1.000001 || rect.y + rect.h > 1.000001) throw new Error('请在图片上框选产品区域，避开文字');
  const left = Math.floor(rect.x * width), top = Math.floor(rect.y * height);
  const w = Math.min(width - left, Math.round(rect.w * width)), h = Math.min(height - top, Math.round(rect.h * height));
  if (w < 32 || h < 32) throw new Error('选区太小，请扩大到至少 32 × 32 像素');
  return { left, top, width: w, height: h };
}
async function composite(base, generated, roi) {
  const { data, info } = await sharp(base).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const pixels = await sharp(generated).extract({ left: 0, top: 0, width: roi.width, height: roi.height }).removeAlpha().raw().toBuffer();
  const feather = Math.min(24, roi.width / 8, roi.height / 8);
  for (let y = 0; y < roi.height; y++) for (let x = 0; x < roi.width; x++) {
    const a = Math.min(1, Math.min(x, y, roi.width - 1 - x, roi.height - 1 - y) / feather);
    const dst = ((y + roi.top) * info.width + x + roi.left) * 4, src = (y * roi.width + x) * 3;
    for (let c = 0; c < 3; c++) data[dst + c] = Math.round(data[dst + c] * (1 - a) + pixels[src + c] * a);
  }
  return sharp(data, { raw: info }).png().toBuffer();
}
async function refine(input, options, signal, progress) {
  const connection = await status();
  if (!connection.ready) throw new Error('ComfyUI 缺少节点：' + connection.missing.join(', '));
  if (!connection.models.includes(options.checkpoint)) throw new Error('请选择已安装的 SD1.5 模型');
  const strength = Number(options.strength);
  if (!Number.isFinite(strength) || strength < 0.1 || strength > 0.3) throw new Error('重绘强度应为 0.10–0.30');
  const source = await sharp(input, { limitInputPixels: 40000000 }).rotate().toColourspace('srgb').png().toBuffer();
  const meta = await sharp(source).metadata();
  const scale = options.scale === 1 ? 1 : 2;
  const width = meta.width * scale, height = meta.height * scale;
  if (width * height > 16000000) throw new Error('精修输出限制 1600 万像素，请选择 1× 或缩小原图');
  const roi = region(options.rect, width, height);
  const base = await sharp(source).resize(width, height).png().toBuffer();
  const paddedW = Math.ceil(roi.width / 8) * 8, paddedH = Math.ceil(roi.height / 8) * 8;
  const crop = await sharp(base).extract(roi).removeAlpha().extend({ top: 0, left: 0, right: paddedW - roi.width, bottom: paddedH - roi.height, extendWith: 'copy' }).png().toBuffer();
  signal.throwIfAborted();
  const form = new FormData();
  form.append('image', new Blob([crop], { type: 'image/png' }), `clearscale-${randomUUID()}.png`);
  const uploaded = await (await api('/upload/image', { method: 'POST', body: form }, signal)).json();
  const image = uploaded.subfolder ? uploaded.subfolder + '/' + uploaded.name : uploaded.name;
  const seed = Math.floor(Math.random() * 2147483647);
  const prompt = graph(image, options.checkpoint, options.preset, strength, seed);
  const queued = await (await api('/prompt', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, client_id: randomUUID() }) }, signal)).json();
  if (!queued.prompt_id) throw new Error('ComfyUI 未返回任务编号');
  progress('已提交分块精修，等待 ComfyUI 完成。停止等待不会中断其他 ComfyUI 任务。');
  const deadline = Date.now() + 3600000;
  while (Date.now() < deadline) {
    await delay(1500, undefined, { signal });
    const history = await (await api('/history/' + encodeURIComponent(queued.prompt_id), {}, signal)).json();
    const job = history[queued.prompt_id];
    if (!job) continue;
    if (job.status?.status_str === 'error') throw new Error('ComfyUI 精修失败：' + JSON.stringify(job.status.messages).slice(-800));
    const output = job.outputs?.['6']?.images?.[0];
    if (!output) { if (job.status?.completed) throw new Error('ComfyUI 未生成图片'); continue; }
    const rendered = Buffer.from(await (await api('/view?' + new URLSearchParams(output), {}, signal)).arrayBuffer());
    const resultMeta = await sharp(rendered).metadata();
    if (resultMeta.width !== paddedW || resultMeta.height !== paddedH) throw new Error('精修输出尺寸异常，未保存结果');
    signal.throwIfAborted();
    return composite(base, rendered, roi);
  }
  throw new Error('等待精修超过 60 分钟，请检查 ComfyUI 控制台');
}
module.exports = { graph, region, composite, status, refine };
