const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { isSupportedImage, makeEngineArgs, makeOutputPath, sanitizeOptions } = require('./engine');

let mainWindow;
let runningProcess = null;
let cancelled = false;

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
  if (runningProcess) runningProcess.kill();
  return true;
});

ipcMain.handle('upscale:start', async (_, payload) => {
  if (runningProcess) throw new Error('已有任务正在运行');
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

  for (let index = 0; index < files.length; index += 1) {
    if (cancelled) break;
    const input = files[index];
    const output = makeOutputPath(input, payload.outputDirectory, options);
    mainWindow.webContents.send('upscale:progress', {
      index, total: files.length, percent: Math.round((index / files.length) * 100),
      message: `正在处理 ${path.basename(input)}`
    });

    await new Promise((resolve, reject) => {
      const args = makeEngineArgs(input, output, engine.models, options);
      runningProcess = spawn(engine.executable, args, { windowsHide: true });
      let errorText = '';
      runningProcess.stderr.on('data', data => { errorText += data.toString(); });
      runningProcess.on('error', reject);
      runningProcess.on('close', code => {
        runningProcess = null;
        if (cancelled) return resolve();
        if (code === 0 && fs.existsSync(output)) return resolve();
        reject(new Error(errorText.trim() || `处理失败，错误代码 ${code}`));
      });
    });

    if (!cancelled) results.push({ input, output, outputUrl: pathToFileURL(output).href });
  }

  mainWindow.webContents.send('upscale:progress', {
    index: results.length, total: files.length,
    percent: cancelled ? Math.round((results.length / files.length) * 100) : 100,
    message: cancelled ? '任务已取消' : '全部处理完成'
  });
  return { cancelled, results };
});
