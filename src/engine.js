const path = require('node:path');

const SUPPORTED_INPUTS = new Set(['.jpg', '.jpeg', '.png', '.webp']);
const VALID_SCALES = new Set([2, 3, 4]);
const VALID_FORMATS = new Set(['png', 'jpg', 'webp']);
const MODELS = {
  general: 'realesrgan-x4plus',
  anime: 'realesrgan-x4plus-anime'
};

function sanitizeOptions(options = {}) {
  const scale = Number(options.scale);
  const format = String(options.format || 'png').toLowerCase();
  const model = MODELS[options.model] || MODELS.general;
  return {
    scale: VALID_SCALES.has(scale) ? scale : 4,
    format: VALID_FORMATS.has(format) ? format : 'png',
    model,
    tta: Boolean(options.tta)
  };
}

function isSupportedImage(filePath) {
  return SUPPORTED_INPUTS.has(path.extname(filePath).toLowerCase());
}

function makeOutputPath(inputPath, outputDirectory, options = {}) {
  const clean = sanitizeOptions(options);
  const fileName = String(inputPath).split(/[\\/]/).pop();
  const base = fileName.slice(0, fileName.length - path.extname(fileName).length);
  return path.join(outputDirectory, `${base}_HD_${clean.scale}x.${clean.format}`);
}

function makeEngineArgs(inputPath, outputPath, modelDirectory, options = {}) {
  const clean = sanitizeOptions(options);
  const args = [
    '-i', inputPath,
    '-o', outputPath,
    '-s', String(clean.scale),
    '-m', modelDirectory,
    '-n', clean.model,
    '-f', clean.format,
    '-v'
  ];
  if (clean.tta) args.push('-x');
  return args;
}

module.exports = {
  MODELS,
  isSupportedImage,
  makeEngineArgs,
  makeOutputPath,
  sanitizeOptions
};
