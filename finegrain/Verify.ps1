$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'runtime\venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host 'Please run Start.cmd first to install the environment.' -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
    exit 1
}

function Select-Image([string]$title) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = $title
    $dialog.Filter = 'Image files|*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff;*.bmp|All files|*.*'
    $dialog.Multiselect = $false
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        return $dialog.FileName
    }
    return $null
}

$source = if ($args.Count -ge 1) { $args[0] } else { Select-Image 'Step 1/2 - Select ORIGINAL image (same crop)' }
if (-not $source) { exit 2 }
$result = if ($args.Count -ge 2) { $args[1] } else { Select-Image 'Step 2/2 - Select ENHANCED image (same crop)' }
if (-not $result) { exit 2 }

& $python (Join-Path $root 'verify_result.py') $source $result
$code = $LASTEXITCODE
Write-Host ''
if ($code -eq 0) {
    Write-Host 'Verification report created in verification_reports.' -ForegroundColor Green
} else {
    Write-Host 'Verification failed. Read the error above.' -ForegroundColor Red
}
Read-Host 'Press Enter to close'
exit $code
