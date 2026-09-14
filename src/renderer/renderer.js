const state = { files: [], outputDirectory: null, scale: 4, running: false, results: [] };
const $ = id => document.getElementById(id);
const emptyState = $('emptyState');
const preview = $('preview');
const beforeImage = $('beforeImage');
const afterImage = $('afterImage');

async function pickImages() {
  const files = await window.clearScale.chooseImages();
  if (!files.length) return;
  state.files = files;
  state.results = [];
  showSelection();
}

function fileUrl(filePath) { return `file:///${filePath.replaceAll('\\', '/').replace(/^\//, '')}`; }
function showSelection() {
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
  state.running = true;
  updateAction();
  $('cancelButton').classList.remove('hidden');
  $('progressCard').classList.remove('hidden');
  $('openFolderButton').classList.add('hidden');
  try {
    const result = await window.clearScale.start({
      files: state.files,
      outputDirectory: state.outputDirectory,
      options: {
        scale: state.scale,
        model: document.querySelector('input[name="model"]:checked').value,
        format: $('format').value,
        tta: $('tta').checked
      }
    });
    state.results = result.results;
    if (state.results.length) {
      afterImage.src = state.results[0].outputUrl;
      $('fileMeta').textContent = result.cancelled ? '部分图片已完成' : '高清处理完成';
      $('openFolderButton').classList.remove('hidden');
    }
  } catch (error) {
    alert(error.message || String(error));
  } finally {
    state.running = false;
    $('cancelButton').classList.add('hidden');
    updateAction();
  }
});
$('cancelButton').addEventListener('click', () => window.clearScale.cancel());
$('openFolderButton').addEventListener('click', () => window.clearScale.openFolder(state.outputDirectory));
window.clearScale.onProgress(progress => {
  $('progressText').textContent = progress.message;
  $('progressPercent').textContent = `${progress.percent}%`;
  $('progressBar').style.width = `${progress.percent}%`;
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
$('compare').addEventListener('pointerdown', event => { dragging = true; $('compare').setPointerCapture(event.pointerId); moveDivider(event); });
$('compare').addEventListener('pointermove', moveDivider);
$('compare').addEventListener('pointerup', () => { dragging = false; });

window.clearScale.engineStatus().then(status => {
  $('engineStatus').textContent = status.ready ? 'AI 引擎就绪' : '开发版未装引擎';
  $('engineStatus').classList.toggle('ready', status.ready);
});
