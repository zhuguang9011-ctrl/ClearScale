const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const { execFileSync } = require('node:child_process');

const url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip';
const root = path.join(__dirname, '..');
const engine = path.join(root, 'engine');
const archive = path.join(root, '.engine-windows.zip');

function download(source, destination, redirects = 0) {
  if (redirects > 5) throw new Error('下载重定向次数过多');
  return new Promise((resolve, reject) => {
    https.get(source, response => {
      if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
        response.resume();
        return resolve(download(response.headers.location, destination, redirects + 1));
      }
      if (response.statusCode !== 200) return reject(new Error(`下载失败：HTTP ${response.statusCode}`));
      const output = fs.createWriteStream(destination);
      response.pipe(output);
      output.on('finish', () => output.close(resolve));
      output.on('error', reject);
    }).on('error', reject);
  });
}

(async () => {
  if (fs.existsSync(path.join(engine, 'realesrgan-ncnn-vulkan.exe'))) {
    console.log('Real-ESRGAN Windows 引擎已就绪。');
    return;
  }
  console.log('正在下载官方 Real-ESRGAN Windows 引擎…');
  await download(url, archive);
  fs.mkdirSync(engine, { recursive: true });
  if (process.platform === 'win32') {
    execFileSync('powershell.exe', ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${archive.replaceAll("'", "''")}' -DestinationPath '${engine.replaceAll("'", "''")}' -Force`], { stdio: 'inherit' });
  } else {
    execFileSync('unzip', ['-q', '-o', archive, '-d', engine], { stdio: 'inherit' });
  }
  fs.rmSync(archive, { force: true });
  const nested = fs.readdirSync(engine).map(name => path.join(engine, name)).find(item => fs.statSync(item).isDirectory() && fs.existsSync(path.join(item, 'realesrgan-ncnn-vulkan.exe')));
  if (nested) for (const name of fs.readdirSync(nested)) fs.renameSync(path.join(nested, name), path.join(engine, name));
  console.log('引擎安装完成。');
})().catch(error => { console.error(error); process.exitCode = 1; });
