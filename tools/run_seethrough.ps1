param(
  [Parameter(Mandatory)][string]$Src,
  [Parameter(Mandatory)][string]$OutDir,
  [int]$Resolution = 1024,
  [string]$Script = 'inference/scripts/inference_psd_quantized.py',
  [string[]]$Extra = @(),
  [int]$HeadGrow = 0   # extra head passes with a growing crop (tools/head_grow.py), 0 = original
)
$ErrorActionPreference = 'Continue'
$root = if ($env:I2L_ROOT) { $env:I2L_ROOT } else { Split-Path $PSScriptRoot -Parent }  # i2l folder (tools/..)
$py = @("$root\env\Scripts\python.exe", "$root\env\python.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1  # venv / conda
if (-not $py) { throw "python not found in $root\env (see docs/INSTALL.md)" }
$env:HF_HOME = Join-Path $root 'hf_cache'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:HEAD_GROW_ITERS = "$HeadGrow"
$base = [int](nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
New-Item -ItemType Directory -Force $OutDir | Out-Null
$gpuLog = Join-Path $OutDir 'gpu_mem.csv'
$runLog = Join-Path $OutDir 'run.log'

# GPU memory sampler (1s)
$sampler = Start-Job -ArgumentList $gpuLog -ScriptBlock {
  param($p)
  while ($true) {
    $g = nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader,nounits
    $free = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)
    "$g, $free" | Add-Content $p
    Start-Sleep -Milliseconds 1000
  }
}

Set-Location (Join-Path $root 'see-through')
$sw = [Diagnostics.Stopwatch]::StartNew()
& $py (Join-Path $root 'tools\run_patched.py') $Script --srcp $Src --save_to_psd --resolution $Resolution --save_dir $OutDir @Extra *> $runLog
$code = $LASTEXITCODE
$sw.Stop()
Stop-Job $sampler; Remove-Job $sampler

$peak = (Get-Content $gpuLog | ForEach-Object { [int](($_ -split ',')[1].Trim()) } | Measure-Object -Maximum).Maximum
$minFree = (Get-Content $gpuLog | ForEach-Object { [int](($_ -split ',')[2].Trim()) } | Measure-Object -Minimum).Minimum
$summary = "MIN_FREE_RAM_MB=$minFree  " +"EXIT=$code  SECONDS=$([math]::Round($sw.Elapsed.TotalSeconds))  PEAK_GPU_MB=$peak  BASELINE_MB=$base  PEAK_MINUS_BASE_MB=$($peak - $base)  ARGS=$Script $Resolution $($Extra -join ' ') HEAD_GROW=$HeadGrow"
$summary | Out-File -Encoding utf8 (Join-Path $OutDir 'summary.txt')
$summary
Get-Content $runLog -Tail 25
