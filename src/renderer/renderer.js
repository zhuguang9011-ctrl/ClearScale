const state = { files: [], outputDirectory: null, scale: 4, running: false, results: [] };
const $ = id => document.getElementById(id);
const emptyState = $('emptyState');
const preview = $('preview');
const beforeImage = $('beforeImage');
const afterImage = $('afterImage');

async function pickImages() {
  if (state.running) return;
  const files = await window.clearScale.chooseImages();
  if (!files.length) return;
  state.files = files;
  state.results = [];
  showSelection();
}

function fileUrl(filePath) { return `file:///${filePath.replaceAll('\\', '/').replace(/^\//, '').split('/').map((part, i) => i === 0 && /^[A-Za-z]:$/.test(part) ? part : encodeURIComponent(part)).join('/')}`; }
function showSelection() {
  state.rect = null;
  emptyState.classList.add('hidden');
  preview.classList.remove('hidden');
  const first = state.files[0];
  beforeImage.src = fileUrl(first);
  afterImage.src = fileUrl(first);
  $('fileName').textContent = first.split(/[\\/]/).pop();
  $('fileMeta').textContent = state.files.length > 1 ? `已选择 ${state.files.length} 张图片` : '等待高清处理';
  const queue = $('queue');
  queue.innerHTML = '';
  state.files.forEach((file, index) => {
    const image = new Image();
    image.src = fileUrl(file);
    image.className = `thumb${index === 0 ? ' active' : ''}`;
    image.title = file.split(/[\\/]/).pop();
    image.addEventListener('click', () => selectPreview(index));
    queue.appendChild(image);
  });
  updateAction();
}

function selectPreview(index) {
  if (state.running || $('processMode').value === 'refine') return;
  document.querySelectorAll('.thumb').forEach((el, i) => el.classList.toggle('active', i === index));
  beforeImage.src = fileUrl(state.files[index]);
  afterImage.src = state.results[index]?.outputUrl || beforeImage.src;
  $('fileName').textContent = state.files[index].split(/[\\/]/).pop();
}

function updateAction() { $('startButton').disabled = !state.files.length || !state.outputDirectory || state.running; }

$('pickButton').addEventListener('click', pickImages);
$('replaceButton').addEventListener('click', pickImages);
$('folderButton').addEventListener('click', async () => {
  const folder = await window.clearScale.chooseFolder();
  if (!folder) return;
  state.outputDirectory = folder;
  $('outputPath').textContent = folder;
  updateAction();
});

document.querySelectorAll('.option').forEach(label => label.addEventListener('click', () => {
  document.querySelectorAll('.option').forEach(el => el.classList.remove('active'));
  label.classList.add('active');
}));
document.querySelectorAll('#scaleGroup button').forEach(button => button.addEventListener('click', () => {
  state.scale = Number(button.dataset.scale);
  document.querySelectorAll('#scaleGroup button').forEach(el => el.classList.toggle('active', el === button));
  $('sizeHint').textContent = `输出尺寸约为原图的 ${state.scale} 倍`;
}));

$('startButton').addEventListener('click', async () => {
  const refining = $('processMode').value === 'refine';
  if (refining && (state.files.length !== 1 || !state.rect)) return alert('局部精修请只选择一张图片，并框选产品区域');
  state.running = true;
  lockControls(true);
  updateAction();
  $('cancelButton').classList.remove('hidden');
  $('progressCard').classList.remove('hidden');
  $('openFolderButton').classList.add('hidden');
  try {
    const result = refining ? await window.clearScale.refine({
      file: state.files[0], outputDirectory: state.outputDirectory,
      options: { checkpoint: $('checkpoint').value, preset: $('material').value, strength: Number($('strength').value), scale: Number($('refineScale').value), rect: state.rect }
    }) : await window.clearScale.start({
      files: state.files,
      outputDirectory: state.outputDirectory,
      options: {
        scale: state.scale,
        model: document.querySelector('input[name="model"]:checked').value,
        format: $('format').value,
        tta: $('tta').checked
        ,denoise: $('denoise').checked,
        evenness: $('evenness').value
      }
    });
    state.results = result.results;
    if (state.results.length) {
      if (refining) { $('regionCanvas').classList.add('hidden'); $('beforeLayer').style.right = '50%'; $('divider').classList.remove('hidden'); }
      afterImage.src = state.results[0].outputUrl;
      $('fileMeta').textContent = result.cancelled ? '部分图片已完成' : '高清处理完成';
      $('openFolderButton').classList.remove('hidden');
    }
  } catch (error) {
    alert(error.message || String(error));
  } finally {
    state.running = false;
    lockControls(false);
    $('cancelButton').classList.add('hidden');
    updateAction();
  }
});
$('cancelButton').addEventListener('click', () => window.clearScale.cancel());
$('openFolderButton').addEventListener('click', () => window.clearScale.openFolder(state.outputDirectory));
window.clearScale.onProgress(progress => {
  $('progressText').textContent = progress.message;
  $('progressPercent').textContent = progress.percent === null ? '处理中' : `${progress.percent}%`;
  $('progressBar').style.width = progress.percent === null ? '0%' : `${progress.percent}%`;
});

let dragging = false;
function moveDivider(event) {
  if (!dragging) return;
  const box = $('compare').getBoundingClientRect();
  const x = Math.max(0, Math.min(box.width, event.clientX - box.left));
  const percent = (x / box.width) * 100;
  $('beforeLayer').style.right = `${100 - percent}%`;
  $('divider').style.left = `${percent}%`;
}
$('compare').addEventListener('pointerdown', event => { if (!$('regionCanvas').classList.contains('hidden')) return; dragging = true; $('compare').setPointerCapture(event.pointerId); moveDivider(event); });
$('compare').addEventListener('pointermove', moveDivider);
$('compare').addEventListener('pointerup', () => { dragging = false; });

window.clearScale.engineStatus().then(status => {
  $('engineStatus').textContent = status.ready ? 'AI 引擎就绪' : '开发版未装引擎';
  $('engineStatus').classList.toggle('ready', status.ready);
});

function lockControls(locked) {
  document.querySelectorAll('.settings select, .settings input, .settings button, #replaceButton, #pickButton').forEach(el => {
    if (!['cancelButton', 'startButton'].includes(el.id)) el.disabled = locked;
  });
}
const canvas = $('regionCanvas');
let startPoint = null;
function imageBox() {
  const w = $('compare').clientWidth, h = $('compare').clientHeight;
  const ratio = Math.min(w / beforeImage.naturalWidth, h / beforeImage.naturalHeight);
  const width = beforeImage.naturalWidth * ratio, height = beforeImage.naturalHeight * ratio;
  return { x: (w - width) / 2, y: (h - height) / 2, width, height };
}
function point(event) {
  const r = canvas.getBoundingClientRect(), box = imageBox();
  return { x: Math.max(0, Math.min(1, (event.clientX - r.left - box.x) / box.width)), y: Math.max(0, Math.min(1, (event.clientY - r.top - box.y) / box.height)) };
}
function drawRegion() {
  canvas.width = $('compare').clientWidth; canvas.height = $('compare').clientHeight;
  beforeImage.style.width = canvas.width + 'px';
  if (!state.rect || !beforeImage.naturalWidth) return;
  const ctx = canvas.getContext('2d'), box = imageBox(), r = state.rect;
  ctx.fillStyle = '#376cf525'; ctx.strokeStyle = '#376cf5'; ctx.lineWidth = 2;
  ctx.fillRect(box.x + r.x * box.width, box.y + r.y * box.height, r.w * box.width, r.h * box.height);
  ctx.strokeRect(box.x + r.x * box.width, box.y + r.y * box.height, r.w * box.width, r.h * box.height);
}
new ResizeObserver(drawRegion).observe($('compare'));
beforeImage.addEventListener('load', drawRegion);
canvas.addEventListener('pointerdown', event => {
  if (state.running || !beforeImage.naturalWidth) return;
  startPoint = point(event); canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener('pointermove', event => {
  if (!startPoint) return;
  const end = point(event);
  state.rect = { x: Math.min(startPoint.x, end.x), y: Math.min(startPoint.y, end.y), w: Math.abs(end.x - startPoint.x), h: Math.abs(end.y - startPoint.y) };
  drawRegion();
});
canvas.addEventListener('pointerup', () => { startPoint = null; });
canvas.addEventListener('pointercancel', () => { startPoint = null; });
$('processMode').addEventListener('change', () => {
  const active = $('processMode').value === 'refine';
  $('refineSettings').classList.toggle('hidden', !active);
  canvas.classList.toggle('hidden', !active);
  $('divider').classList.toggle('hidden', active);
  $('beforeLayer').style.right = active ? '0%' : '50%';
  $('startButton').textContent = active ? '开始局部精修' : '开始高清放大';
  $('cancelButton').textContent = active ? '停止等待（后台任务可能继续）' : '取消任务';
  document.querySelectorAll('.settings fieldset').forEach(el => {
    if (!el.contains($('processMode')) && el.id !== 'refineSettings') el.classList.toggle('hidden', active);
  });
  drawRegion();
});
$('reselectRegion').addEventListener('click', () => {
  if (!state.files.length) return;
  beforeImage.src = fileUrl(state.files[0]);
  $('beforeLayer').style.right = '0%';
  canvas.classList.remove('hidden');
  $('divider').classList.add('hidden');
  state.rect = null;
  drawRegion();
});
$('connectRefine').addEventListener('click', async () => {
  $('refineStatus').textContent = '检测中…';
  try {
    const result = await window.clearScale.refineStatus();
    $('checkpoint').replaceChildren(...result.models.map(name => new Option(name, name)));
    $('refineStatus').textContent = result.ready ? '已连接；请选择 SD1.5 模型（不使用 SDXL / Flux）' : '缺少节点：' + result.missing.join(', ');
  } catch { $('refineStatus').textContent = '连接失败，请先启动本机 ComfyUI，地址 127.0.0.1:8188'; }
});
