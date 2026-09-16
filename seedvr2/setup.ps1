param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot 'runtime\python'
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot 'runtime\uv-cache'
$env:HF_HOME = Join-Path $PSScriptRoot 'models'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
New-Item -ItemType Directory -Force runtime | Out-Null
Start-Transcript -Path (Join-Path $PSScriptRoot 'seedvr2.log') -Append | Out-Null
try {
  Write-Host 'ClearScale SeedVR2 test: standalone installation, no ComfyUI required.'
  Write-Host 'First setup downloads Python, CUDA PyTorch, source and model weights. Reserve at least 25 GB.'
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
  & $uv python install 3.12.10
  if ($LASTEXITCODE -ne 0) { throw 'Python installation failed' }
  if (!(Test-Path 'runtime\venv\Scripts\python.exe')) {
    & $uv venv --python 3.12.10 'runtime\venv'
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
  }
  $python = Join-Path $PSScriptRoot 'runtime\venv\Scripts\python.exe'
  $arguments = @('bootstrap.py', '--uv', $uv)
  if ($CheckOnly) { $arguments += '--check-only' }
  & $python @arguments
  if ($LASTEXITCODE -ne 0) { throw 'SeedVR2 preparation failed' }
  & $python smoke_test.py
  if ($LASTEXITCODE -ne 0) { throw 'SeedVR2 source validation failed' }
  if (!$CheckOnly) {
    & $python -c "import torch; assert torch.cuda.is_available(), 'CUDA GPU unavailable'; print('GPU:',torch.cuda.get_device_name(0)); print('VRAM GB:',round(torch.cuda.get_device_properties(0).total_memory/1073741824,2)); x=torch.ones((64,64),device='cuda'); assert (x@x)[0,0].item()==64"
    if ($LASTEXITCODE -ne 0) { throw 'GPU check failed before model inference' }
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Select one product image or a representative crop'
    $dialog.Filter = 'Image files|*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff;*.bmp|All files|*.*'
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }
    & $python run_seedvr2.py $dialog.FileName
    if ($LASTEXITCODE -ne 0) { throw 'SeedVR2 inference failed' }
  }
} catch {
  Write-Host $_ -ForegroundColor Red
  exit 1
} finally {
  Stop-Transcript | Out-Null
}
