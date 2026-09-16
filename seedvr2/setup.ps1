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

    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'ClearScale processing options'
    $form.Width = 520
    $form.Height = 255
    $form.StartPosition = 'CenterScreen'
    $modeLabel = New-Object System.Windows.Forms.Label
    $modeLabel.Text = 'Detail mode'
    $modeLabel.Left = 24; $modeLabel.Top = 24; $modeLabel.Width = 120
    $mode = New-Object System.Windows.Forms.ComboBox
    $mode.Left = 150; $mode.Top = 20; $mode.Width = 320; $mode.DropDownStyle = 'DropDownList'
    [void]$mode.Items.Add('Fidelity 15% - maximum preservation')
    [void]$mode.Items.Add('Balanced 28% - recommended')
    [void]$mode.Items.Add('Detail 40% - stronger enhancement')
    [void]$mode.Items.Add('Raw SeedVR2 - comparison only')
    $mode.SelectedIndex = 1
    $scaleLabel = New-Object System.Windows.Forms.Label
    $scaleLabel.Text = 'Output scale'
    $scaleLabel.Left = 24; $scaleLabel.Top = 70; $scaleLabel.Width = 120
    $scale = New-Object System.Windows.Forms.ComboBox
    $scale.Left = 150; $scale.Top = 66; $scale.Width = 160; $scale.DropDownStyle = 'DropDownList'
    [void]$scale.Items.Add('1.5x')
    [void]$scale.Items.Add('2x')
    $scale.SelectedIndex = 1
    $saveRaw = New-Object System.Windows.Forms.CheckBox
    $saveRaw.Text = 'Also save raw SeedVR2 result'
    $saveRaw.Left = 150; $saveRaw.Top = 108; $saveRaw.Width = 260
    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = 'Start'; $ok.Left = 270; $ok.Top = 150; $ok.Width = 95
    $ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = 'Cancel'; $cancel.Left = 375; $cancel.Top = 150; $cancel.Width = 95
    $cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $form.Controls.AddRange(@($modeLabel,$mode,$scaleLabel,$scale,$saveRaw,$ok,$cancel))
    $form.AcceptButton = $ok; $form.CancelButton = $cancel
    if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }

    $runArgs = @('run_seedvr2.py', $dialog.FileName, '--scale', $(if ($scale.SelectedIndex -eq 0) {'1.5'} else {'2.0'}))
    switch ($mode.SelectedIndex) {
      0 { $runArgs += @('--fusion-amount', '0.15') }
      1 { $runArgs += @('--fusion-amount', '0.28') }
      2 { $runArgs += @('--fusion-amount', '0.40') }
      3 { $runArgs += '--raw-output-only' }
    }
    if ($saveRaw.Checked -and $mode.SelectedIndex -ne 3) { $runArgs += '--save-raw' }
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'SeedVR2 inference failed' }
    Read-Host 'Processing finished. Press Enter to close'
  }
} catch {
  Write-Host $_ -ForegroundColor Red
  exit 1
} finally {
  Stop-Transcript | Out-Null
}
