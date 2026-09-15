const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const sharp = require('sharp');
const { refine } = require('../src/refine');
test('local API upload, queue, history, download and composite end to end (mock inference)', async t => {
  const source = await sharp({ create: { width: 64, height: 64, channels: 3, background: '#204060' } }).png().toBuffer();
  const generated = await sharp({ create: { width: 64, height: 64, channels: 3, background: '#aabbcc' } }).png().toBuffer();
  let posted;
  const server = http.createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/object_info') return res.end(JSON.stringify({ CheckpointLoaderSimple: { input: { required: { ckpt_name: [['test.safetensors']] } } }, CLIPTextEncode: {}, LoadImage: {}, SaveImage: {}, UltimateSDUpscaleNoUpscale: {} }));
    if (req.url === '/upload/image') { assert.match(req.headers['content-type'], /multipart/); return res.end(JSON.stringify({ name: 'crop.png', subfolder: '' })); }
    if (req.url === '/prompt') { posted = JSON.parse(body); return res.end('{"prompt_id":"test-job"}'); }
    if (req.url === '/history/test-job') return res.end(JSON.stringify({ 'test-job': { outputs: { '6': { images: [{ filename: 'result.png', type: 'output', subfolder: '' }] } }, status: { completed: true } } }));
    if (req.url.startsWith('/view?')) { res.setHeader('Content-Type', 'image/png'); return res.end(generated); }
    res.statusCode = 404; res.end('{}');
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(8188, '127.0.0.1', resolve); });
  t.after(() => new Promise(resolve => { server.closeAllConnections(); server.close(resolve); }));
  const result = await refine(source, { checkpoint: 'test.safetensors', preset: 'natural', strength: 0.15, scale: 1, rect: { x: 0, y: 0, w: 1, h: 1 } }, new AbortController().signal, () => {});
  assert.equal((await sharp(result).metadata()).width, 64);
  assert.equal(posted.prompt['1'].inputs.ckpt_name, 'test.safetensors');
  const pixels = await sharp(result).raw().toBuffer();
  assert.deepEqual([...pixels.subarray(0, 3)], [32, 64, 96]);
  assert.deepEqual([...pixels.subarray((32 * 64 + 32) * 4, (32 * 64 + 32) * 4 + 3)], [170, 187, 204]);
});
