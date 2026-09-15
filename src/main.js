const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const os = require('node:os');
const { Worker } = require('node:worker_threads');
const { isSupportedImage, makeEngineArgs, makeOutputPath, sanitizeOptions } = require('./engine');

let mainWindow;
let runningProcess = null;
let cancelled = false;
let busy = false;
let imageWorker = null;
let refineController = null;
ipcMain.handle('surface:start', async (_, payload) => {
  if (busy) throw new Error('已有任务正在运行');
  const files = (payload.files || []).filter(isSupportedImage);
  if (!files.length || !payload.outputDirectory || !fs.existsSync(payload.outputDirectory)) throw new Error('请选择图片和导出文件夹');
  busy = true; cancelled = false;
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'clearscale-surface-'));
  const results = [];
  try {
    for (const input of files) {
      if (cancelled) break;
      mainWindow.webContents.send('upscale:progress', { percent: Math.round(results.length / files.length * 100), message: '保留亮度纹理，清理局部彩色杂点…' });
      const pending = path.join(temp, 'surface.png');
      const size = await processImage('surface', [input, pending, { strength: payload.strength }]);
      if (cancelled) break;
      const name = path.parse(input).name + '_surface';
      let output = path.join(payload.outputDirectory, name + '.png');
      for (let n = 1; fs.existsSync(output); n++) output = path.join(payload.outputDirectory, name + '_' + n + '.png');
      fs.copyFileSync(pending, output, fs.constants.COPYFILE_EXCL);
      results.push({ input, output, outputUrl: pathToFileURL(output).href, ...size });
    }
    mainWindow.webContents.send('upscale:progress', { percent: cancelled ? Math.round(results.length / files.length * 100) : 100, message: cancelled ? '已取消' : '表面清理完成，原尺寸 PNG 已保存' });
    return { cancelled, results };
  } finally { busy = false; fs.rmSync(temp, { recursive: true, force: true }); }
});
ipcMain.handle('refine:status', () => require('./refine').status());
ipcMain.handle('refine:start', async (_, payload) => {
  if (busy) throw new Error('已有任务正在运行');
  if (!isSupportedImage(payload.file) || !fs.existsSync(payload.file)) throw new Error('请选择有效图片');
  if (!payload.outputDirectory || !fs.existsSync(payload.outputDirectory)) throw new Error('请选择导出文件夹');
  busy = true;
  refineController = new AbortController();
  try {
    const buffer = await require('./refine').refine(payload.file, payload.options, refineController.signal,
      message => mainWindow.webContents.send('upscale:progress', { message, percent: null }));
    refineController.signal.throwIfAborted();
    const name = path.parse(payload.file).name + '_精修';
    let output = path.join(payload.outputDirectory, name + '.png');
    for (let n = 1; fs.existsSync(output); n++) output = path.join(payload.outputDirectory, name + '_' + n + '.png');
    fs.writeFileSync(output, buffer, { flag: 'wx' });
    mainWindow.webContents.send('upscale:progress', { message: '精修完成，请检查产品细节', percent: 100 });
    return { results: [{ input: payload.file, output, outputUrl: pathToFileURL(output).href }] };
  } finally { busy = false; refineController = null; }
});
function processImage(action, args) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(path.join(__dirname, 'image-worker.js'), { workerData: { action, args } });
    imageWorker = worker;
    worker.on('message', value => resolve(value.result));
    worker.on('error', reject);
    worker.on('exit', code => {
      if (imageWorker === worker) imageWorker = null;
      if (code !== 0 || cancelled) reject(new Error(cancelled ? '任务已取消' : '图像优化失败'));
    });
  });
}

function projectRoot() {
  return app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
}

function enginePaths() {
  const root = path.join(projectRoot(), 'engine');
  return {
    executable: path.join(root, process.platform === 'win32' ? 'realesrgan-ncnn-vulkan.exe' : 'realesrgan-ncnn-vulkan'),
    models: path.join(root, 'models')
  };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#f3f7fb',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => BrowserWindow.getAllWindows().length === 0 && createWindow());
});
app.on('window-all-closed', () => process.platform !== 'darwin' && app.quit());

ipcMain.handle('images:choose', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择需要变清晰的图片',
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: '图片', extensions: ['jpg', 'jpeg', 'png', 'webp'] }]
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle('folder:choose', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择导出文件夹',
    properties: ['openDirectory', 'createDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('folder:open', (_, folderPath) => shell.openPath(folderPath));
ipcMain.handle('engine:status', () => {
  const engine = enginePaths();
  return { ready: fs.existsSync(engine.executable), executable: engine.executable };
});

ipcMain.handle('upscale:cancel', () => {
  cancelled = true;
  refineController?.abort(new Error('已停止等待；ComfyUI 中的任务可能仍在运行'));
  if (runningProcess) runningProcess.kill();
  if (imageWorker) imageWorker.terminate();
  return true;
});

ipcMain.handle('upscale:start', async (_, payload) => {
  if (busy) throw new Error('已有任务正在运行');
  const files = (payload.files || []).filter(isSupportedImage);
  if (!files.length) throw new Error('请先选择 JPG、PNG 或 WebP 图片');
  if (!payload.outputDirectory || !fs.existsSync(payload.outputDirectory)) throw new Error('请选择有效的导出文件夹');

  const engine = enginePaths();
  if (!fs.existsSync(engine.executable)) {
    throw new Error('AI 引擎尚未安装。开发版请先运行 npm run engine:win；正式安装包已内置引擎。');
  }

  cancelled = false;
  const options = sanitizeOptions(payload.options);
  const results = [];
  busy = true;
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'clearscale-'));
  try {

  for (let index = 0; index < files.length; index += 1) {
    if (cancelled) break;
    const input = files[index];
    let output = makeOutputPath(input, payload.outputDirectory, options);
    const parsed = path.parse(output);
    for (let n = 1; fs.existsSync(output); n++) output = path.join(parsed.dir, parsed.name + '_' + n + parsed.ext);
    const prepared = path.join(temp, 'prepared.png');
    const rendered = path.join(temp, 'rendered.png');
    fs.rmSync(rendered, { force: true });
    mainWindow.webContents.send('upscale:progress', {
      index, total: files.length, percent: Math.round((index / files.length) * 100),
      message: `降噪与色泽优化：${path.basename(input)}`
    });

    await processImage('prepare', [input, prepared, options]);
    if (cancelled) break;
    mainWindow.webContents.send('upscale:progress', { percent: Math.round(index / files.length * 100), message: 'AI 高清放大中…' });
    await new Promise((resolve, reject) => {
      const args = makeEngineArgs(prepared, rendered, engine.models, options);
      runningProcess = spawn(engine.executable, args, { windowsHide: true });
      let errorText = '';
      runningProcess.stderr.on('data', data => { errorText += data.toString(); });
      runningProcess.on('error', error => { runningProcess = null; reject(error); });
      runningProcess.on('close', code => {
        runningProcess = null;
        if (cancelled) return resolve();
        if (code === 0 && fs.existsSync(rendered)) return resolve();
        reject(new Error(errorText.trim() || `处理失败，错误代码 ${code}`));
      });
    });

    if (!cancelled) {
      const finalTemp = path.join(temp, 'final.' + options.format);
      await processImage('finish', [input, prepared, rendered, finalTemp, options]);
      if (!cancelled) {
        fs.copyFileSync(finalTemp, output, fs.constants.COPYFILE_EXCL);
        results.push({ input, output, outputUrl: pathToFileURL(output).href });
      }
    }
  }

  mainWindow.webContents.send('upscale:progress', {
    index: results.length, total: files.length,
    percent: cancelled ? Math.round((results.length / files.length) * 100) : 100,
    message: cancelled ? '任务已取消' : '全部处理完成'
  });
  return { cancelled, results };
  } finally {
    busy = false;
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
