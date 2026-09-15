param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot 'runtime\python'
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot 'runtime\uv-cache'
$env:HF_HOME = Join-Path $PSScriptRoot 'models'
$env:GRADIO_ANALYTICS_ENABLED = 'False'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
New-Item -ItemType Directory -Force runtime | Out-Null
Start-Transcript -Path (Join-Path $PSScriptRoot 'setup.log') -Append | Out-Null
try {
  Write-Host 'Finegrain launcher: first setup downloads Python, packages and models.'
  Write-Host 'Use a writable local folder with at least 20 GB free. No ComfyUI required.'
  $uv = Join-Path $PSScriptRoot 'runtime\uv.exe'
  if (!(Test-Path $uv)) {
    $zip = Join-Path $PSScriptRoot 'runtime\uv.zip'
    Invoke-WebRequest -UseBasicParsing 'https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-pc-windows-msvc.zip' -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'a86c9dc7bad9b03f388583b7187c05fe9951c2e0d392217e8fd43d97787f6ec2') { throw 'uv download checksum mismatch' }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $PSScriptRoot 'runtime\uv-unpacked') -Force
    $found = Get-ChildItem (Join-Path $PSScriptRoot 'runtime\uv-unpacked') -Filter uv.exe -Recurse | Select-Object -First 1
    if (!$found) { throw 'uv.exe not found in archive' }
    Copy-Item $found.FullName $uv
  }
  & $uv python install 3.11.9
  if ($LASTEXITCODE -ne 0) { throw 'Python installation failed' }
  if (!(Test-Path 'runtime\venv\Scripts\python.exe')) {
    & $uv venv --python 3.11.9 'runtime\venv'
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
  }
  $python = Join-Path $PSScriptRoot 'runtime\venv\Scripts\python.exe'
  & $python bootstrap.py --uv $uv
  if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed' }
  & $python smoke_test.py
  if ($LASTEXITCODE -ne 0) { throw 'Application interface check failed' }
  if (!$CheckOnly) {
    & $python -c "import torch; assert torch.cuda.is_available(), 'No working NVIDIA CUDA GPU. Update your NVIDIA driver and retry.'; print(torch.cuda.get_device_name(0)); x=torch.ones((64,64),device='cuda'); print((x@x).sum().item())"
    if ($LASTEXITCODE -ne 0) { throw 'GPU check failed; no model inference was started' }
    Write-Host 'Starting. First launch downloads model weights; keep this window open.'
    Push-Location 'runtime\source\app'
    try { & $python app.py; if ($LASTEXITCODE -ne 0) { throw 'Finegrain exited with an error' } }
    finally { Pop-Location }
  }
} catch {
  Write-Host $_ -ForegroundColor Red
  exit 1
} finally { Stop-Transcript | Out-Null }
