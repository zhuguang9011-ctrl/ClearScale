const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { isSupportedImage, makeEngineArgs, makeOutputPath, sanitizeOptions } = require('../src/engine');

test('只接受支持的图片格式', () => {
  assert.equal(isSupportedImage('photo.JPG'), true);
  assert.equal(isSupportedImage('photo.webp'), true);
  assert.equal(isSupportedImage('notes.txt'), false);
});

test('清洗不可信设置', () => {
  assert.deepEqual(sanitizeOptions({ scale: 99, format: 'exe', model: 'bad' }), {
    scale: 4, format: 'png', model: 'realesrgan-x4plus', tta: false, denoise: true, evenness: 'light'
  });
});

test('生成不会覆盖原文件的输出名', () => {
  assert.equal(makeOutputPath('C:\\input\\shoe.jpg', 'D:\\result', { scale: 2, format: 'png' }), path.join('D:\\result', 'shoe_HD_2x.png'));
});

test('生成 Real-ESRGAN 安全参数数组', () => {
  const args = makeEngineArgs('input file.jpg', 'output.png', 'models', { scale: 3, model: 'anime', tta: true });
  assert.deepEqual(args, ['-i','input file.jpg','-o','output.png','-s','4','-m','models','-n','realesrgan-x4plus-anime','-f','png','-v','-x']);
});
